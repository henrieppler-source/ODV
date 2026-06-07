from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from .api_client import ApiError
from .app_logging import app_log, app_log_exception
from .config import save_config
from .database import add_history
from .file_service import (
    append_metadata_history,
    detect_document_type,
    load_metadata_files,
    make_upload_id,
    save_metadata_file,
)
from .models import HistoryEntry


class MasterdataManagerMixin:
    def open_place_folder_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Die Ortsordner-Stammdaten sind nur für Superadmins freigegeben.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Ortsordner-Stammdaten")
        try: self.track_window_geometry(dialog, "Ortsordner-Stammdaten")
        except Exception: pass
        dialog.transient(self)
        dialog.geometry("760x520")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        frame = ttk.LabelFrame(dialog, text="Ort → Ordner im Nextcloud-Stammverzeichnis", padding=10)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=("place", "folder"), show="headings")
        tree.heading("place", text="Ort", anchor="w")
        tree.heading("folder", text="Ordner", anchor="w")
        tree.column("place", width=220, anchor="w")
        tree.column("folder", width=420, anchor="w")
        tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=4, sticky="ns")

        place_var = tk.StringVar()
        folder_var = tk.StringVar()
        ttk.Label(frame, text="Ort:").grid(row=1, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(frame, textvariable=place_var).grid(row=2, column=0, sticky="ew", padx=(0, 6))
        ttk.Label(frame, text="Ordner:").grid(row=1, column=1, sticky="w", pady=(8, 2))
        ttk.Entry(frame, textvariable=folder_var).grid(row=2, column=1, sticky="ew", padx=(0, 6))

        def load_rows():
            for item in tree.get_children():
                tree.delete(item)
            rows = []
            try:
                if self.api_token:
                    rows = self.api.list_place_folders(self.api_token).get("places", [])
            except ApiError as exc:
                messagebox.showerror("Ortsordner", f"Stammdaten konnten nicht geladen werden:\n{exc}", parent=dialog)
                rows = []
            for idx, row in enumerate(rows):
                tree.insert("", "end", iid=str(idx), values=(row.get("place", ""), row.get("folder_name", "")))

        def select_row(_event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if len(vals) >= 2:
                place_var.set(vals[0])
                folder_var.set(vals[1])

        def add_or_update():
            place = place_var.get().strip()
            folder = folder_var.get().strip()
            if not place or not folder:
                messagebox.showwarning("Unvollständig", "Bitte Ort und Ordner erfassen.", parent=dialog)
                return
            # In der Anzeige aktualisieren oder hinzufügen.
            for iid in tree.get_children():
                vals = tree.item(iid, "values")
                if vals and self.normalize_folder_token(vals[0]) == self.normalize_folder_token(place):
                    tree.item(iid, values=(place, folder))
                    return
            tree.insert("", "end", values=(place, folder))

        def delete_selected():
            for iid in tree.selection():
                tree.delete(iid)

        def save_rows():
            rows = []
            for iid in tree.get_children():
                vals = tree.item(iid, "values")
                if len(vals) >= 2 and str(vals[0]).strip() and str(vals[1]).strip():
                    rows.append({"place": str(vals[0]).strip(), "folder_name": str(vals[1]).strip()})
            try:
                self.api.update_place_folders(self.api_token, rows)
                self.place_folder_map = {self.normalize_folder_token(r["place"]): r["folder_name"] for r in rows}
                self.config_data["place_folder_map"] = self.place_folder_map
                save_config(self.config_data)
                self.load_writable_folders(show_message=False)
                messagebox.showinfo("Ortsordner", "Ortsordner-Stammdaten wurden gespeichert.", parent=dialog)
                dialog.destroy()
            except ApiError as exc:
                messagebox.showerror("Ortsordner", str(exc), parent=dialog)

        ttk.Button(frame, text="Hinzufügen / Aktualisieren", command=add_or_update).grid(row=2, column=2, sticky="ew", padx=4)
        ttk.Button(frame, text="Entfernen", command=delete_selected).grid(row=2, column=3, sticky="ew", padx=4)
        buttons = ttk.Frame(dialog)
        buttons.grid(row=1, column=0, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Speichern", command=save_rows).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        tree.bind("<<TreeviewSelect>>", select_row)
        load_rows()

    def update_archive_collection_references(self, old_values: list[str], new_value: str) -> int:
        old_keys = {str(value or "").strip().casefold() for value in old_values if str(value or "").strip()}
        if not old_keys:
            return 0
        replacement = str(new_value or "").strip()
        changed = 0
        try:
            items = load_metadata_files(self.metadata_folder_path())
        except Exception:
            items = []
        for item in items:
            current = str(item.get("archive_name") or item.get("archiv") or "").strip()
            if current.casefold() not in old_keys:
                continue
            item["archive_name"] = replacement
            item["archiv"] = replacement
            metadata_file = item.get("_metadata_file")
            if metadata_file:
                try:
                    save_metadata_file(Path(str(metadata_file)), item)
                    changed += 1
                except Exception as exc:
                    app_log_exception("Archiv/Sammlung konnte in Metadaten nicht vereinheitlicht werden", exc, metadata_file=str(metadata_file))
        return changed

    def open_archive_collection_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Archiv/Sammlung-Stammdaten sind nur für Superadmins sichtbar.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Archiv/Sammlung-Stammdaten")
        try: self.track_window_geometry(dialog, "Archiv/Sammlung-Stammdaten")
        except Exception: pass
        dialog.transient(self)
        dialog.geometry("720x520")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        ttk.Label(dialog, text="Archiv/Sammlung-Stammdaten", font=("", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        tree = ttk.Treeview(dialog, columns=("name",), show="headings", selectmode="browse")
        tree.heading("name", text="Archiv / Sammlung", anchor="w")
        tree.column("name", width=640, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=1, column=1, sticky="ns", pady=6)

        value_var = tk.StringVar()
        form = ttk.Frame(dialog, padding=(10, 4))
        form.grid(row=2, column=0, columnspan=2, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Bezeichnung:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(form, textvariable=value_var).grid(row=0, column=1, sticky="ew")

        def load_rows() -> None:
            for iid in tree.get_children():
                tree.delete(iid)
            for value in self.archive_collection_options():
                tree.insert("", "end", values=(value,))

        def selected_value() -> str:
            sel = tree.selection()
            if not sel:
                return ""
            return str(tree.item(sel[0], "values")[0] or "").strip()

        def select_row(_event=None) -> None:
            value_var.set(selected_value())

        def save_value() -> None:
            old = selected_value()
            new = value_var.get().strip()
            if not new:
                messagebox.showwarning("Archiv/Sammlung", "Bitte eine Bezeichnung erfassen.", parent=dialog)
                return
            values = [value for value in self.archive_collection_options() if value.casefold() != old.casefold()]
            if new.casefold() not in {value.casefold() for value in values}:
                values.append(new)
            values.sort(key=str.casefold)
            self.config_data["archive_collection_options"] = values
            changed = self.update_archive_collection_references([old], new) if old and old.casefold() != new.casefold() else 0
            save_config(self.config_data)
            self.refresh_upload_metadata_option_comboboxes()
            load_rows()
            messagebox.showinfo("Archiv/Sammlung", f"Gespeichert. Aktualisierte lokale Dokumentbezüge: {changed}", parent=dialog)

        def delete_value() -> None:
            old = selected_value()
            if not old:
                return
            if not messagebox.askyesno("Archiv/Sammlung", f"Eintrag aus der Auswahlliste entfernen?\n\n{old}\n\nDokumentbezüge bleiben unverändert.", parent=dialog):
                return
            self.config_data["archive_collection_options"] = [value for value in self.archive_collection_options() if value.casefold() != old.casefold()]
            save_config(self.config_data)
            self.refresh_upload_metadata_option_comboboxes()
            value_var.set("")
            load_rows()

        def merge_value() -> None:
            old = selected_value()
            if not old:
                messagebox.showwarning("Archiv/Sammlung", "Bitte zuerst einen Eintrag auswählen.", parent=dialog)
                return
            choices = [value for value in self.archive_collection_options() if value.casefold() != old.casefold()]
            if not choices:
                messagebox.showinfo("Verschmelzen", "Es gibt keinen weiteren Eintrag als Ziel.", parent=dialog)
                return
            merge_dialog = tk.Toplevel(dialog)
            merge_dialog.title("Verschmelzen")
            merge_dialog.transient(dialog)
            merge_dialog.columnconfigure(0, weight=1)
            target_var = tk.StringVar(value=choices[0])
            info_var = tk.StringVar()

            def update_info(*_args) -> None:
                info_var.set(f"Der Eintrag {old} wird mit {target_var.get()} verschmolzen.\nNeue Bezeichnung: {target_var.get()}")

            ttk.Label(merge_dialog, textvariable=info_var, wraplength=520).grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
            combo = ttk.Combobox(merge_dialog, textvariable=target_var, values=choices, state="readonly", width=56)
            combo.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
            buttons2 = ttk.Frame(merge_dialog)
            buttons2.grid(row=2, column=0, sticky="e", padx=14, pady=(0, 14))
            result = {"target": ""}

            def accept() -> None:
                result["target"] = target_var.get().strip()
                merge_dialog.destroy()

            ttk.Button(buttons2, text="Verschmelzen", command=accept).pack(side="left", padx=4)
            ttk.Button(buttons2, text="Abbrechen", command=merge_dialog.destroy).pack(side="left", padx=4)
            target_var.trace_add("write", update_info)
            update_info()
            combo.focus_set()
            dialog.wait_window(merge_dialog)
            target = result["target"]
            if not target:
                return
            values = [value for value in self.archive_collection_options() if value.casefold() != old.casefold()]
            if target.casefold() not in {value.casefold() for value in values}:
                values.append(target)
            values.sort(key=str.casefold)
            self.config_data["archive_collection_options"] = values
            changed = self.update_archive_collection_references([old], target)
            save_config(self.config_data)
            self.refresh_upload_metadata_option_comboboxes()
            value_var.set(target)
            load_rows()
            messagebox.showinfo("Archiv/Sammlung", f"Einträge verschmolzen. Aktualisierte lokale Dokumentbezüge: {changed}", parent=dialog)

        tree.bind("<<TreeviewSelect>>", select_row)
        buttons = ttk.Frame(dialog, padding=10)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Speichern / Umbenennen", command=save_value).pack(side="left", padx=4)
        ttk.Button(buttons, text="Verschmelzen...", command=merge_value).pack(side="left", padx=4)
        ttk.Button(buttons, text="Aus Liste entfernen", command=delete_value).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        load_rows()

    def open_import_existing_files_dialog(self) -> None:
        """Importiert bereits manuell in Nextcloud abgelegte Dateien in JSON/API.

        Gedacht für Fälle, in denen Dateien z. B. per Explorer nach
        01_ABLAGE_ORTSCHRONIK kopiert wurden. Die Datei bleibt an Ort und Stelle,
        es werden nur Metadatensatz, JSON-Sicherung und MySQL-Datensatz angelegt.
        """
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Nur Superadmins können vorhandene Dateien einlesen.")
            return
        if not self.api_token:
            messagebox.showwarning("API", "Bitte zuerst an der API anmelden.")
            return
        base_text = self.base_folder_var.get().strip()
        if not base_text:
            messagebox.showwarning("Nextcloud", "Bitte zuerst das Nextcloud-Stammverzeichnis in den Stammdaten festlegen.")
            return
        base = Path(base_text).expanduser()
        if not base.exists() or not base.is_dir():
            messagebox.showwarning("Nextcloud", f"Nextcloud-Stammverzeichnis nicht gefunden:\n{base}")
            return

        # Für den Import sind Schreibrechte maßgeblich, weil ein neuer Metadatensatz angelegt wird.
        if not self.writable_folders:
            self.load_writable_folders(show_message=False)
        folders = [p for p in self.writable_folders if p.exists() and p.is_dir()]
        if not folders:
            messagebox.showwarning("Ordner", "Es wurden keine erlaubten Schreibordner gefunden.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Vorhandene Dateien einlesen")
        try: self.track_window_geometry(dialog, "Vorhandene Dateien einlesen")
        except Exception: pass
        dialog.geometry("860x620")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(3, weight=1)

        ttk.Label(dialog, text="Bereits vorhandene Dateien werden nicht verschoben. Es werden Metadaten/JSON und ein MySQL-Datensatz angelegt.", wraplength=820).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        top = ttk.Frame(dialog)
        top.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        top.columnconfigure(1, weight=1)
        folder_var = tk.StringVar()
        folder_map = {self.display_path_for_folder(p, base): p for p in folders}
        labels = sorted(folder_map.keys(), key=str.lower)
        preferred = next((label for label, p in folder_map.items() if p.name.upper() == "01_ABLAGE_ORTSCHRONIK"), None)
        folder_var.set(preferred or (labels[0] if labels else ""))
        ttk.Label(top, text="Ordner:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        folder_combo = ttk.Combobox(top, textvariable=folder_var, values=labels, state="readonly")
        folder_combo.grid(row=0, column=1, sticky="ew")
        recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Unterordner einbeziehen", variable=recursive_var).grid(row=0, column=2, sticky="w", padx=(12, 0))

        import_users: list[dict] = []
        user_label_var = tk.StringVar()
        user_map: dict[str, dict] = {}
        try:
            user_response = self.api.list_users(self.api_token)
            for user in user_response.get("users", []) or []:
                if int(user.get("is_active", user.get("active", 1)) or 0) != 1:
                    continue
                label = f"{user.get('display_name','')} ({user.get('username','')}) – {user.get('place','')}"
                user_map[label] = user
                import_users.append(user)
            current_label = next((label for label, u in user_map.items() if str(u.get('display_name','')) == self.display_name_var.get().strip()), None)
            user_label_var.set(current_label or (next(iter(user_map.keys()), "")))
        except Exception as exc:
            app_log_exception("Benutzerliste für Import konnte nicht geladen werden", exc)
        ttk.Label(top, text="Dateien sind von:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        user_combo = ttk.Combobox(top, textvariable=user_label_var, values=list(user_map.keys()), state="readonly")
        user_combo.grid(row=1, column=1, sticky="ew", pady=(6, 0))

        status_var = tk.StringVar(value="Noch nicht geprüft.")
        ttk.Label(dialog, textvariable=status_var).grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 4))

        columns = ("path", "document_type", "status")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", selectmode="extended")
        tree.heading("path", text="Datei")
        tree.heading("document_type", text="Dokumenttyp")
        tree.heading("status", text="Status")
        tree.column("path", width=560, anchor="w")
        tree.column("document_type", width=140, anchor="w")
        tree.column("status", width=120, anchor="w")
        tree.grid(row=3, column=0, sticky="nsew", padx=12, pady=6)
        ysb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        ysb.grid(row=3, column=1, sticky="ns", pady=6)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=4, column=0, sticky="ew", padx=12, pady=(6, 12))
        buttons.columnconfigure(0, weight=1)

        scan_results: list[Path] = []

        def load_known_paths() -> set[str]:
            known: set[str] = set()
            # lokale JSON-Sicherungen
            try:
                for item in load_metadata_files(self.metadata_folder_path()):
                    cp = item.get("current_path")
                    if cp:
                        known.add(str(Path(str(cp)).resolve()).lower())
            except Exception:
                pass
            # zentrale MySQL/API-Datensätze
            try:
                response = self.api.list_documents(self.api_token, only_own=False)
                for doc in response.get("documents", []) or []:
                    cp = doc.get("current_path")
                    if cp:
                        known.add(str(Path(str(cp)).resolve()).lower())
            except Exception as exc:
                app_log_exception("Bekannte Dokumentpfade konnten nicht vollständig geladen werden", exc)
            return known

        def is_relevant_file(path: Path) -> bool:
            if not path.is_file():
                return False
            if self.is_hidden_system_path(path):
                return False
            if any(str(part).upper() in {"_ARCHIV", "ARCHIV", "ARCHIVIERT", "ABGELEHNT", "GELOESCHT", "GELÖSCHT"} for part in path.parts):
                return False
            name = path.name
            if name.startswith("."):
                return False
            if name.lower().endswith(".metadata.json"):
                return False
            if any(part.startswith(".ortschronik_") for part in path.parts):
                return False
            return True

        def scan() -> None:
            nonlocal scan_results
            for iid in tree.get_children():
                tree.delete(iid)
            scan_results = []
            label = folder_var.get()
            root = folder_map.get(label)
            if not root or not root.exists():
                status_var.set("Ordner nicht gefunden.")
                return
            known = load_known_paths()
            iterator = root.rglob("*") if recursive_var.get() else root.iterdir()
            try:
                for path in sorted(iterator, key=lambda p: str(p).lower()):
                    if not is_relevant_file(path):
                        continue
                    key = str(path.resolve()).lower()
                    if key in known:
                        continue
                    scan_results.append(path)
                    rel = self.display_path_for_folder(path, base)
                    tree.insert("", "end", iid=str(path), values=(rel, detect_document_type(path), "neu"))
            except Exception as exc:
                app_log_exception("Import-Scan fehlgeschlagen", exc)
                messagebox.showerror("Einlesen", f"Der Ordner konnte nicht vollständig durchsucht werden:\n{exc}", parent=dialog)
            status_var.set(f"{len(scan_results)} neue Datei(en) gefunden.")

        def import_selected() -> None:
            selected = [Path(iid) for iid in tree.selection()]
            if not selected:
                messagebox.showinfo("Einlesen", "Bitte zuerst Dateien auswählen.", parent=dialog)
                return
            owner = user_map.get(user_label_var.get().strip()) or {}
            owner_id = int(owner.get("id", 0) or 0)
            display_name = str(owner.get("display_name") or self.display_name_var.get().strip() or "Admin")
            owner_place = str(owner.get("place") or self.place_var.get().strip())
            if not owner_id:
                messagebox.showwarning("Benutzerzuordnung", "Bitte auswählen, von wem die Dateien sind.", parent=dialog)
                return
            imported = 0
            failed = 0
            for path in selected:
                try:
                    upload_id = make_upload_id()
                    now = datetime.now().isoformat(timespec="seconds")
                    item = {
                        "upload_id": upload_id,
                        "original_filename": path.name,
                        "stored_filename": path.name,
                        "current_filename": path.name,
                        "current_path": str(path),
                        "target_folder": str(path.parent),
                        "uploaded_by": display_name,
                        "import_uploaded_by_user_id": owner_id,
                        "uploaded_at": now,
                        "status": "hochgeladen",
                        "odv_capture_mode": "existing_file_metadata",
                        "odv_captured_by_admin": True,
                        "document_type": detect_document_type(path),
                        "source": "",
                        "original_location": "",
                        "document_date": "",
                        "event": "",
                        "place": owner_place,
                        "gps_coordinates": "",
                        "gps_place": "",
                        "description": "",
                        "note": "",
                        "rights_note": "",
                        "copyright_author": "",
                        "rights_holder": "",
                        "usage_permission": "",
                        "license_note": "",
                        "archive_name": "",
                        "archive_signature": "",
                        "archive_accessed_at": "",
                        "person_status": "none",
                        "persons": [],
                        "history": [],
                    }
                    append_metadata_history(item, display_name, "Vorhandene Nextcloud-Datei in ODV aufgenommen", str(path))
                    metadata_file = self.metadata_folder_path() / f"{upload_id}.metadata.json"
                    save_metadata_file(metadata_file, item)
                    item["_metadata_file"] = str(metadata_file)
                    self.api.create_document(self.api_token, self.document_create_payload_from_item(item))
                    add_history(HistoryEntry.now(display_name, "Vorhandene Nextcloud-Datei in ODV aufgenommen", str(path), upload_id))
                    imported += 1
                    try:
                        tree.set(str(path), "status", "eingelesen")
                    except Exception:
                        pass
                except Exception as exc:
                    failed += 1
                    app_log_exception("Vorhandene Datei konnte nicht eingelesen werden", exc)
                    try:
                        tree.set(str(path), "status", "Fehler")
                    except Exception:
                        pass
            self.refresh_history()
            self.refresh_admin_uploads(show_message=False)
            messagebox.showinfo("Einlesen", f"Eingelesen: {imported}\nFehler: {failed}", parent=dialog)
            scan()

        ttk.Button(buttons, text="Ausgewählte einlesen", command=import_selected).grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).grid(row=0, column=2, sticky="e", padx=(8, 0))
        folder_combo.bind("<<ComboboxSelected>>", lambda _e: scan())

        scan()

    def open_local_backup_cleanup_dialog(self) -> None:
        """Prüft lokale JSON-Sicherungsdateien gegen die zentrale MySQL/API-Liste.

        Im Produktivmodus sind JSON-Dateien nur Sicherung. Dieser Dialog hilft,
        verwaiste lokale Sicherungen zu finden, die keinen passenden MySQL-
        Datensatz mehr besitzen, und sie gezielt zu verschieben oder zu löschen.
        """
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Lokale Sicherungsdateien prüfen/bereinigen")
        try: self.track_window_geometry(dialog, "Lokale Sicherungsdateien prüfen/bereinigen")
        except Exception: pass
        dialog.transient(self)
        dialog.geometry("1150x620")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        info = ttk.Label(
            dialog,
            text=(
                "Lokale JSON-Dateien sind nur Sicherung. Dateien bearbeiten zeigt im Produktivmodus ausschließlich MySQL/API-Datensätze.\n"
                "Verwaiste Sicherungen sind JSON-Dateien ohne passenden MySQL-Datensatz. Sie können verschoben oder gelöscht werden."
            ),
            wraplength=1050,
        )
        info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        frame = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            frame,
            columns=("status", "upload_id", "file", "json_file"),
            show="headings",
            selectmode="extended",
        )
        for col, label, width in [
            ("status", "Status", 120),
            ("upload_id", "Upload-ID", 210),
            ("file", "Datei", 260),
            ("json_file", "JSON-Datei", 520),
        ]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.tag_configure("orphan", background="#ffe0e0")
        tree.tag_configure("ok", background="#e8f5e9")
        tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        status_var = tk.StringVar(value="Noch nicht geprüft.")
        ttk.Label(dialog, textvariable=status_var).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))

        rows_by_iid: dict[str, dict] = {}

        def load_backup_rows() -> None:
            rows_by_iid.clear()
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                response = self.api.list_documents(self.api_token, only_own=False)
                api_ids = {str(doc.get("upload_id", "")) for doc in response.get("documents", []) if doc.get("upload_id")}
            except ApiError as exc:
                messagebox.showerror("API", f"MySQL/API-Dokumentliste konnte nicht geladen werden:\n{exc}", parent=dialog)
                return

            folder = self.metadata_folder_path()
            local_items = load_metadata_files(folder)
            orphan_count = 0
            ok_count = 0
            for idx, item in enumerate(local_items):
                upload_id = str(item.get("upload_id", "") or "")
                json_file = str(item.get("_metadata_file", "") or "")
                filename = str(item.get("current_filename") or item.get("stored_filename") or item.get("original_filename") or "")
                exists_in_api = bool(upload_id and upload_id in api_ids)
                status = "in MySQL vorhanden" if exists_in_api else "verwaist"
                tag = "ok" if exists_in_api else "orphan"
                if exists_in_api:
                    ok_count += 1
                else:
                    orphan_count += 1
                iid = f"row-{idx}"
                tree.insert("", "end", iid=iid, values=(status, upload_id, filename, json_file), tags=(tag,))
                rows_by_iid[iid] = item
            status_var.set(f"{len(local_items)} JSON-Sicherungen geprüft: {ok_count} vorhanden, {orphan_count} verwaist.")

        def selected_orphans() -> list[dict]:
            result = []
            for iid in tree.selection():
                item = rows_by_iid.get(iid)
                if not item:
                    continue
                vals = tree.item(iid, "values")
                if vals and vals[0] == "verwaist":
                    result.append({"iid": iid, "item": item})
            return result

        def move_selected_orphans() -> None:
            selected = selected_orphans()
            if not selected:
                messagebox.showinfo("Bereinigung", "Bitte zuerst verwaiste JSON-Dateien auswählen.", parent=dialog)
                return
            target_dir = self.metadata_folder_path() / "_verwaiste_sicherungen"
            target_dir.mkdir(parents=True, exist_ok=True)
            moved = 0
            errors = []
            for row in selected:
                item = row["item"]
                source = Path(str(item.get("_metadata_file", "") or ""))
                if not source.exists():
                    errors.append(f"Nicht gefunden: {source}")
                    continue
                target = target_dir / source.name
                counter = 1
                while target.exists():
                    target = target_dir / f"{source.stem}_{counter}{source.suffix}"
                    counter += 1
                try:
                    source.rename(target)
                    moved += 1
                except Exception as exc:
                    errors.append(f"{source}: {exc}")
            app_log("info", "Verwaiste JSON-Sicherungen verschoben", count=moved, target=str(target_dir))
            load_backup_rows()
            msg = f"{moved} verwaiste Sicherungsdatei(en) verschoben nach:\n{target_dir}"
            if errors:
                msg += "\n\nFehler:\n" + "\n".join(errors[:5])
            messagebox.showinfo("Bereinigung", msg, parent=dialog)

        def delete_selected_orphans() -> None:
            selected = selected_orphans()
            if not selected:
                messagebox.showinfo("Bereinigung", "Bitte zuerst verwaiste JSON-Dateien auswählen.", parent=dialog)
                return
            if not messagebox.askyesno(
                "Verwaiste Sicherungen löschen",
                f"{len(selected)} verwaiste JSON-Sicherungsdatei(en) endgültig löschen?\n\n"
                "Sicherer ist meist zuerst 'Verschieben'.",
                parent=dialog,
            ):
                return
            deleted = 0
            errors = []
            for row in selected:
                item = row["item"]
                source = Path(str(item.get("_metadata_file", "") or ""))
                try:
                    if source.exists():
                        source.unlink()
                        deleted += 1
                except Exception as exc:
                    errors.append(f"{source}: {exc}")
            app_log("info", "Verwaiste JSON-Sicherungen gelöscht", count=deleted)
            load_backup_rows()
            msg = f"{deleted} verwaiste Sicherungsdatei(en) gelöscht."
            if errors:
                msg += "\n\nFehler:\n" + "\n".join(errors[:5])
            messagebox.showinfo("Bereinigung", msg, parent=dialog)

        buttons = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Button(buttons, text="Aktualisieren", command=load_backup_rows).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Ausgewählte verwaiste verschieben", command=move_selected_orphans).pack(side="left", padx=6)
        ttk.Button(buttons, text="Ausgewählte verwaiste löschen", command=delete_selected_orphans).pack(side="left", padx=6)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load_backup_rows()

    def delete_orphan_local_metadata_backups(self) -> dict[str, int | list[str]]:
        """Löscht lokale Metadaten-Sicherungen ohne passenden API-Datensatz."""
        response = self.api.list_documents(self.api_token, only_own=False)
        api_ids = {str(doc.get("upload_id", "")) for doc in response.get("documents", []) if doc.get("upload_id")}
        deleted = 0
        skipped = 0
        errors: list[str] = []
        for item in load_metadata_files(self.metadata_folder_path()):
            upload_id = str(item.get("upload_id", "") or "")
            if upload_id and upload_id in api_ids:
                skipped += 1
                continue
            source = Path(str(item.get("_metadata_file", "") or ""))
            try:
                if source.exists() and source.suffix.lower() == ".json" and source.name.lower().endswith(".metadata.json"):
                    source.unlink()
                    deleted += 1
            except Exception as exc:
                errors.append(f"{source}: {exc}")
        app_log("info", "Verwaiste JSON-Sicherungen automatisch gelöscht", deleted=deleted, skipped=skipped, errors=len(errors))
        return {"deleted": deleted, "skipped": skipped, "errors": errors}
