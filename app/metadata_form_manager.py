from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .api_client import ApiError
from .app_logging import app_log, app_log_exception
from .database import add_history
from .file_service import append_metadata_history, detect_document_type, is_image_file, is_writable_folder, make_upload_id, save_metadata_file
from .models import HistoryEntry
from .person_tagger import PersonTagger


class MetadataFormManagerMixin:
    def load_file_view_metadata_form(self) -> None:
        self._loading_file_view_metadata = True
        path = self.file_view_current_path
        item = self.file_view_current_metadata or {}
        try:
            writable = self.can_edit_file_view_metadata(path, item)
            if writable:
                self.file_view_write_hint_var.set("Metadaten bearbeitbar" if item else "Datei noch nicht in ODV aufgenommen – Metadaten können angelegt werden")
            else:
                if item and item.get("upload_id") and not (str(item.get("uploaded_by_user_id") or item.get("user_id") or "").strip() or str(item.get("uploaded_by") or item.get("uploaded_by_name") or "").strip()) and not self.is_current_admin():
                    self.file_view_write_hint_var.set("Nur Anzeige: kein Erfasser hinterlegt – Bearbeitung nur durch Admin/Superadmin")
                else:
                    self.file_view_write_hint_var.set("Nur Anzeige: keine Bearbeitungsberechtigung für diese Datei")
            self.refresh_file_view_uploaded_by_options()
            if "uploaded_by" in self.file_view_meta_vars:
                uid = str(item.get("uploaded_by_user_id") or "")
                name = str(item.get("uploaded_by") or item.get("uploaded_by_name") or "")
                if not name and not item:
                    name = self.display_name_var.get().strip() or ""
                    uid = str(self.current_user.get("id", "") if self.current_user else "")
                label = next((lbl for lbl, u in self.file_view_uploaded_by_user_map.items() if str(u.get("id") or "") == uid), "")
                if not label:
                    label = next((lbl for lbl, u in self.file_view_uploaded_by_user_map.items() if str(u.get("display_name") or u.get("name") or "") == name), name)
                try:
                    self.file_view_meta_vars["uploaded_by"].set(label)
                except Exception:
                    pass
            for key, var in self.file_view_meta_vars.items():
                if key == "uploaded_by" and self.is_current_admin():
                    continue
                value = item.get(key, "")
                if key == "document_type" and not value and path and path.is_file():
                    value = detect_document_type(path)
                if key == "transcription_done" and isinstance(var, tk.BooleanVar):
                    var.set(str(value).strip().lower() in {"1", "ja", "yes", "true", "x"})
                else:
                    var.set(str(value or ""))
        finally:
            self._loading_file_view_metadata = False
            self._file_view_uploaded_by_user_interaction = False
        try:
            self.file_view_description_text.configure(state="normal")
            self.file_view_note_text.configure(state="normal")
        except tk.TclError:
            pass
        self.file_view_description_text.delete("1.0", "end")
        self.file_view_description_text.insert("1.0", str(item.get("description", "") or ""))
        if self.file_view_description_counter_var:
            self.update_description_counter(self.file_view_description_text, self.file_view_description_counter_var)
        self.file_view_note_text.delete("1.0", "end")
        self.file_view_note_text.insert("1.0", str(item.get("note", "") or ""))
        state = "normal" if writable else "disabled"
        for widget in self.file_view_meta_widgets:
            try:
                if widget is self.file_view_uploaded_by_combo:
                    widget.configure(state=("readonly" if writable and self.is_current_admin() else "disabled"))
                elif isinstance(widget, ttk.Combobox) and str(widget.cget("state")) == "readonly":
                    widget.configure(state=("readonly" if writable else "disabled"))
                else:
                    widget.configure(state=state)
            except tk.TclError:
                pass
        self.file_view_json_text.configure(state="normal")
        self.file_view_json_text.delete("1.0", "end")
        if item:
            view_item = {k: v for k, v in item.items() if k != "_metadata_file"}
            self.file_view_json_text.insert("1.0", self.format_metadata_plain(view_item))
        else:
            self.file_view_json_text.insert("1.0", "Keine JSON-Metadaten vorhanden. Beim Speichern werden neue Metadaten angelegt.")
        self.file_view_json_text.configure(state="disabled")
        try:
            self.file_view_meta_canvas.yview_moveto(0)
        except Exception:
            pass
        self.update_file_view_ocr_button()

    def ensure_file_view_metadata_item(self, path: Path) -> tuple[dict, Path]:
        """Liefert vorhandene Metadaten zur Datei oder bereitet einen neuen Datensatz vor.

        Wichtig: Für physisch vorhandene Dateien ohne ODV-Metadaten wird hier noch
        nichts gespeichert. Erst ein echter Speichervorgang mit geänderten Feldern
        legt JSON/MySQL-Daten an.
        """
        metadata_folder = self.metadata_folder_path()
        path_key = str(path)
        item = self.file_view_metadata_by_path.get(path_key)
        if item and item.get("_metadata_file"):
            return item, Path(str(item["_metadata_file"]))

        upload_id = make_upload_id()
        display_name = self.display_name_var.get().strip() or "Benutzer"
        item = {
            "upload_id": upload_id,
            "original_filename": path.name,
            "stored_filename": path.name,
            "current_filename": path.name,
            "current_path": str(path),
            "status": "hochgeladen",
            "odv_capture_mode": "existing_file_metadata",
            "odv_captured_by_admin": bool(self.is_current_admin()),
            "uploaded_by": display_name,
            "uploaded_by_name": display_name,
            "uploaded_by_user_id": str((self.current_user or {}).get("id", "")),
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            "target_folder": str(path.parent),
            "document_type": detect_document_type(path),
            "primary_source": "",
            "secondary_source": "",
            "source": "",
            "original_location": "",
            "document_date": "",
            "event": "",
            "place": self.place_var.get().strip(),
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
            "_pending_existing_file_metadata": True,
        }
        metadata_file = metadata_folder / f"{upload_id}.metadata.json"
        item["_metadata_file"] = str(metadata_file)
        return item, metadata_file

    def find_admin_deposit_folder(self) -> Path | None:
        """Sucht einen beschreibbaren Ablageordner für Kopien aus schreibgeschützten Bereichen."""
        base_text = self.base_folder_var.get().strip()
        if not base_text:
            return None
        base = Path(base_text).expanduser()
        preferred_names = ["01_ABLAGE_ORTSCHRONIK", "01_Ablage_Ortschronik", "01_ablage_ortschronik"]
        configured = list(self.admin_work_folder_names)
        names = preferred_names + [n for n in configured if n not in preferred_names]
        for name in names:
            direct = base / name
            if direct.exists() and direct.is_dir() and is_writable_folder(direct):
                return direct
        try:
            for folder in base.rglob("*"):
                if not folder.is_dir():
                    continue
                if folder.name.lower() in {n.lower() for n in names} and is_writable_folder(folder):
                    return folder
        except OSError:
            return None
        return None

    def create_person_tagging_copy_for_admin(self, source_path: Path, source_item: dict, persons: list[PersonMark]) -> tuple[Path, Path, dict] | None:
        """Erstellt bei fehlenden Schreibrechten eine Kopie in 01_ABLAGE_ORTSCHRONIK und speichert dort die neue Personenzuordnung."""
        deposit_folder = self.find_admin_deposit_folder()
        if not deposit_folder:
            messagebox.showerror(
                "Kein Ablageordner gefunden",
                "Es wurde kein beschreibbarer Ordner 01_ABLAGE_ORTSCHRONIK gefunden.\n"
                "Bitte den Nextcloud-Stammordner und die Admin-Einstellungen prüfen.",
            )
            return None

        upload_id = make_upload_id()
        if "upload_id" in self.meta_vars:
            self.meta_vars["upload_id"].set(upload_id)
        if "status" in self.meta_vars:
            self.meta_vars["status"].set("hochgeladen")
        if "uploaded_at" in self.meta_vars:
            self.meta_vars["uploaded_at"].set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_name = safe_filename(f"{timestamp}_personen_{source_path.name}")
        target_file = unique_path_with_counter(deposit_folder / target_name)
        try:
            shutil.copy2(source_path, target_file)
        except Exception as exc:
            messagebox.showerror("Kopie konnte nicht erstellt werden", str(exc))
            return None

        display_name = self.display_name_var.get().strip() or "Benutzer"
        new_item = dict(source_item or {})
        new_item.pop("_metadata_file", None)
        new_item["upload_id"] = upload_id
        new_item["original_filename"] = source_item.get("original_filename") or source_path.name
        new_item["stored_filename"] = target_file.name
        new_item["current_filename"] = target_file.name
        new_item["current_path"] = str(target_file)
        new_item["target_folder"] = str(deposit_folder)
        new_item["status"] = "hochgeladen"
        new_item["uploaded_by"] = display_name
        new_item["uploaded_at"] = datetime.now().isoformat(timespec="seconds")
        new_item["document_type"] = new_item.get("document_type") or detect_document_type(source_path)
        new_item["source_copy_of_path"] = str(source_path)
        new_item["copy_reason"] = "Personenzuordnung aus schreibgeschütztem Ordner"
        new_item["persons"] = [p.to_dict() for p in persons]
        new_item["person_status"] = "identified" if persons else "none"
        new_item["history"] = []
        append_metadata_history(new_item, display_name, "Kopie erstellt", f"Aus schreibgeschütztem Ordner: {source_path}")
        append_metadata_history(new_item, display_name, "Personenzuordnung geändert", f"{len(persons)} Personenmarkierungen")

        metadata_file = self.metadata_folder_path() / f"{upload_id}.metadata.json"
        save_metadata_file(metadata_file, new_item)
        new_item["_metadata_file"] = str(metadata_file)
        return target_file, metadata_file, new_item

    def edit_persons_for_current_file(self) -> None:
        path = self.file_view_current_path
        if not path or not path.exists() or path.is_dir() or not is_image_file(path):
            return
        source_item = self.file_view_current_metadata or {}
        tagger = PersonTagger(self, path, initial_persons=source_item.get("persons", []) or [])
        result = tagger.show_modal()
        if result is None:
            return

        display_name = self.display_name_var.get().strip() or "Benutzer"
        if is_writable_folder(path.parent):
            item, metadata_file = self.ensure_file_view_metadata_item(path)
            item["persons"] = [p.to_dict() for p in result]
            item["person_status"] = "identified" if result else "none"
            append_metadata_history(item, display_name, "Personenzuordnung geändert", f"{len(result)} Personenmarkierungen")
            save_metadata_file(metadata_file, item)
            item["_metadata_file"] = str(metadata_file)
            if self.api_token and item.get("upload_id"):
                try:
                    # Falls der Datensatz schon in MySQL existiert: Personen dort ebenfalls aktualisieren.
                    self.api.update_persons(self.api_token, str(item.get("upload_id")), item["persons"])
                except ApiError:
                    pass
            self.file_view_current_metadata = item
            add_history(HistoryEntry.now(display_name, "Personenzuordnung geändert", f"{path.name}: {len(result)} Personenmarkierungen", item.get("upload_id")))
            self.load_file_view_metadata_form()
            self.show_file_preview()
        else:
            if not messagebox.askyesno(
                "Keine Schreibberechtigung",
                "In diesem Ordner bestehen keine Schreibrechte.\n\n"
                "Soll eine Kopie mit der Personenzuordnung in 01_ABLAGE_ORTSCHRONIK abgelegt werden, "
                "damit ein Admin die Datei weiter bearbeiten kann?",
            ):
                return
            created = self.create_person_tagging_copy_for_admin(path, source_item, result)
            if not created:
                return
            target_file, metadata_file, new_item = created
            if self.api_token:
                try:
                    self.api.create_document(self.api_token, self.document_create_payload_from_item(new_item))
                    if new_item.get("persons"):
                        self.api.update_persons(self.api_token, str(new_item.get("upload_id")), new_item.get("persons", []))
                except ApiError as exc:
                    append_metadata_history(new_item, display_name, "MySQL nicht gespeichert", str(exc))
                    save_metadata_file(metadata_file, new_item)
            self.file_view_metadata_items.append(new_item)
            self.file_view_metadata_by_path[str(target_file)] = new_item
            add_history(HistoryEntry.now(display_name, "Kopie für Admin-Bearbeitung erstellt", f"{path.name} → {target_file}; {len(result)} Personenmarkierungen", new_item.get("upload_id")))
            messagebox.showinfo(
                "Kopie erstellt",
                "Die Personenzuordnung wurde nicht am Original gespeichert.\n\n"
                f"Kopie für Admin-Bearbeitung:\n{target_file}\n\n"
                f"Metadaten:\n{metadata_file}",
            )
            self.refresh_document_work_area(show_message=False)
        self.refresh_history()

    def edit_persons_for_admin_file(self) -> None:
        if not self.require_admin():
            return
        item = self.selected_admin_upload()
        if not item:
            return
        path_text = item.get("current_path") or ""
        path = Path(path_text) if path_text else None
        if not path or not path.exists() or not is_image_file(path):
            return
        if not is_writable_folder(path.parent):
            messagebox.showwarning("Keine Schreibberechtigung", "Personen können nur bearbeitet werden, wenn im Ordner Schreibrecht besteht.")
            return
        tagger = PersonTagger(self, path, initial_persons=item.get("persons", []) or [])
        result = tagger.show_modal()
        if result is None:
            return
        item["persons"] = [p.to_dict() for p in result]
        item["person_status"] = "identified" if result else "none"
        display_name = self.display_name_var.get().strip() or "Admin"
        append_metadata_history(item, display_name, "Personenzuordnung geändert", f"{len(result)} Personenmarkierungen")
        api_msg = ""
        if self.api_token and item.get("upload_id"):
            try:
                self.api.update_persons(self.api_token, str(item.get("upload_id")), item["persons"])
                api_msg = "MySQL-Personen aktualisiert"
            except ApiError as exc:
                api_msg = f"MySQL nicht aktualisiert: {exc}"
                messagebox.showwarning("API", api_msg)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Personenzuordnung geändert", f"{path.name}: {len(result)} Personenmarkierungen | {api_msg}", item.get("upload_id")))
        self.file_view_current_metadata = item
        self.load_file_view_metadata_form()
        self.refresh_document_work_area(show_message=False)
        self.refresh_history()

    def save_file_view_metadata(self, auto: bool = False) -> None:
        path = self.file_view_current_path
        if not path or not path.exists() or path.is_dir():
            return
        writable = self.can_edit_file_view_metadata(path, self.file_view_current_metadata)
        if not writable:
            if not auto:
                messagebox.showwarning("Keine Berechtigung", "Metadaten können nur mit Schreibrecht auf den Ordner, bei eigenen Dateien oder durch Admin/Superadmin geändert werden. Bei fehlendem Erfasser reicht Schreibrecht auf den Ordner; sonst nur Admin/Superadmin.")
            return
        item, metadata_file = self.ensure_file_view_metadata_item(path)
        changed = []
        technical_edit_keys = {"edited_by", "edited_at"}
        for key, var in self.file_view_meta_vars.items():
            if key in technical_edit_keys:
                continue
            if key == "uploaded_by" and self.is_current_admin():
                continue
            old = str(item.get(key, "") or "")
            raw_value = var.get()
            new = "1" if isinstance(var, tk.BooleanVar) and bool(raw_value) else ("0" if isinstance(var, tk.BooleanVar) else str(raw_value).strip())
            if old != new:
                item[key] = new
                changed.append(key)
        for key, widget in [("description", self.file_view_description_text), ("note", self.file_view_note_text)]:
            old = str(item.get(key, "") or "")
            new = widget.get("1.0", "end").strip()
            if key == "description":
                new = self.normalize_description_text(new)
                current_widget_text = widget.get("1.0", "end").strip()
                if new != current_widget_text:
                    widget.delete("1.0", "end")
                    widget.insert("1.0", new)
            if old != new:
                item[key] = new
                changed.append(key)
        if not changed:
            return
        display_name = self.display_name_var.get().strip() or "Benutzer"
        edited_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item["edited_by"] = display_name
        item["edited_at"] = edited_at
        if "edited_by" in self.file_view_meta_vars:
            self.file_view_meta_vars["edited_by"].set(display_name)
        if "edited_at" in self.file_view_meta_vars:
            self.file_view_meta_vars["edited_at"].set(edited_at)
        is_new_existing_file = bool(item.pop("_pending_existing_file_metadata", False))
        if is_new_existing_file:
            append_metadata_history(item, display_name, "Vorhandene Nextcloud-Datei in ODV aufgenommen", f"Dateiansicht: {path.name}; Felder: {', '.join(changed)}")
        else:
            append_metadata_history(item, display_name, "Metadaten geändert", f"Dateiansicht: {path.name}; Felder: {', '.join(changed)}")
        api_ok, api_msg = self.save_file_view_item_to_storage(item, metadata_file, is_new_existing_file)
        if not api_ok:
            app_log("warning", "Dateiansicht-Metadaten nur lokal gespeichert", upload_id=item.get("upload_id"), api_message=api_msg)
        self.file_view_json_text.configure(state="normal")
        self.file_view_json_text.delete("1.0", "end")
        self.file_view_json_text.insert("1.0", self.format_metadata_plain({k: v for k, v in item.items() if k != "_metadata_file"}))
        self.file_view_json_text.configure(state="disabled")
        add_history(HistoryEntry.now(display_name, "Metadaten geändert", f"{path.name}: {', '.join(changed)}", item.get("upload_id")))
        self.refresh_history()
        if not auto:
            messagebox.showinfo("Metadaten", "Metadaten wurden gespeichert.")


    def load_active_user_options(self) -> tuple[list[str], dict[str, dict]]:
        """Lädt aktive Benutzer für Auswahlfelder; Rückgabe: Labels und Label->User."""
        labels: list[str] = []
        mapping: dict[str, dict] = {}
        if not self.api_token:
            return labels, mapping
        try:
            resp = self.api.list_users(self.api_token)
            for u in resp.get("users", []) or []:
                try:
                    if int(u.get("is_active", u.get("active", 1)) or 0) != 1:
                        continue
                except Exception:
                    pass
                label = f"{u.get('display_name') or u.get('name') or u.get('username')} ({u.get('username') or u.get('id')})"
                labels.append(label)
                mapping[label] = u
        except Exception as exc:
            app_log_exception("Benutzerliste für Auswahl konnte nicht geladen werden", exc)
        return labels, mapping

    def refresh_admin_uploaded_by_options(self) -> None:
        labels, mapping = self.load_active_user_options()
        self.admin_uploaded_by_user_map = mapping
        try:
            self.admin_uploaded_by_combo.configure(values=labels)
        except Exception:
            pass

    def refresh_file_view_uploaded_by_options(self) -> None:
        labels, mapping = self.load_active_user_options()
        self.file_view_uploaded_by_user_map = mapping
        try:
            self.file_view_uploaded_by_combo.configure(values=labels)
        except Exception:
            pass

    def save_file_view_item_to_storage(self, item: dict, metadata_file: Path, is_new_existing_file: bool) -> tuple[bool, str]:
        """Speichert ein Dateiansicht-Item als JSON und über die API.

        Bei vorhandenen Dateien ohne ODV-Datensatz wird erst hier bewusst ein
        Dokument erzeugt. Nur Anzeigen, Vorschau oder Doppelklick bleiben ohne
        DB-Schreibzugriff.
        """
        if is_new_existing_file:
            item.pop("_pending_existing_file_metadata", None)
        save_metadata_file(metadata_file, item)
        item["_metadata_file"] = str(metadata_file)
        path_key = str(item.get("current_path") or "")
        if path_key and path_key not in self.file_view_metadata_by_path:
            self.file_view_metadata_by_path[path_key] = item
            self.file_view_metadata_items.append(item)
        if not (self.api_token and item.get("upload_id")):
            return False, "Kein API-Token oder keine Upload-ID vorhanden"
        try:
            if is_new_existing_file:
                self.api.create_document(self.api_token, self.item_create_payload_for_api(item))
                return True, "MySQL-Dokument angelegt"
            try:
                self.api.lock_document(self.api_token, str(item.get("upload_id")))
            except ApiError as lock_exc:
                return False, str(lock_exc)
            self.api.update_document(self.api_token, str(item.get("upload_id")), self.item_payload_for_api(item))
            return True, "MySQL aktualisiert"
        except ApiError as exc:
            app_log_exception("Dateiansicht-Metadaten konnten nicht in MySQL gespeichert werden", exc, upload_id=item.get("upload_id"))
            return False, str(exc)

    def file_view_uploaded_by_changed(self, _event=None) -> None:
        if self._loading_file_view_metadata:
            return
        if not self._file_view_uploaded_by_user_interaction:
            return
        self._file_view_uploaded_by_user_interaction = False
        if not self.is_current_admin():
            return
        path = self.file_view_current_path
        if not path or not path.exists() or path.is_dir() or not self.can_edit_file_view_metadata(path, self.file_view_current_metadata):
            return
        label = self.file_view_meta_vars.get("uploaded_by").get() if "uploaded_by" in self.file_view_meta_vars else ""
        user = self.file_view_uploaded_by_user_map.get(label)
        if not user:
            return
        item, metadata_file = self.ensure_file_view_metadata_item(path)
        old_name = str(item.get("uploaded_by") or item.get("uploaded_by_name") or "")
        old_id = str(item.get("uploaded_by_user_id") or "")
        new_id = str(user.get("id") or "")
        new_name = str(user.get("display_name") or user.get("name") or user.get("username") or "")
        if old_id == new_id and old_name == new_name:
            return
        is_new_existing_file = bool(item.get("_pending_existing_file_metadata", False))
        item["uploaded_by_user_id"] = new_id
        item["uploaded_by_name"] = new_name
        item["uploaded_by"] = new_name
        display_name = self.display_name_var.get().strip() or "Admin"
        if is_new_existing_file:
            append_metadata_history(item, display_name, "Vorhandene Nextcloud-Datei in ODV aufgenommen", f"Erfasst von: {new_name}")
        else:
            append_metadata_history(item, display_name, "Erfasst von geändert", f"{old_name} → {new_name}")
        api_ok, api_msg = self.save_file_view_item_to_storage(item, metadata_file, is_new_existing_file)
        if not api_ok:
            messagebox.showwarning("Erfasst von", api_msg)
            return
        self.file_view_current_metadata = item
        add_history(HistoryEntry.now(display_name, "Erfasst von geändert", f"{old_name} → {new_name}", item.get("upload_id")))
        self.load_file_view_metadata_form()
        self.refresh_history()

    def admin_uploaded_by_changed(self, _event=None) -> None:
        if self._loading_admin_details:
            return
        if not self._admin_uploaded_by_user_interaction:
            return
        self._admin_uploaded_by_user_interaction = False
        if not self.is_current_admin():
            return
        item = self.selected_admin_upload()
        if not item:
            return
        label = self.admin_meta_vars.get("uploaded_by").get() if "uploaded_by" in self.admin_meta_vars else ""
        user = self.admin_uploaded_by_user_map.get(label)
        if not user:
            return
        old_name = str(item.get("uploaded_by") or item.get("uploaded_by_name") or "")
        old_id = str(item.get("uploaded_by_user_id") or "")
        new_id = str(user.get("id") or "")
        new_name = str(user.get("display_name") or user.get("name") or user.get("username") or "")
        if old_id == new_id and old_name == new_name:
            return
        item["uploaded_by_user_id"] = new_id
        item["uploaded_by_name"] = new_name
        item["uploaded_by"] = new_name
        api_ok, api_msg = self.save_item_to_api(item)
        if not api_ok:
            messagebox.showwarning("Erfasst von", api_msg)
            return
        add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Admin", "Erfasst von geändert", f"{old_name} → {new_name}", item.get("upload_id")))
        self.refresh_document_work_area(show_message=False)
        self.file_view_current_metadata = item
        self.load_file_view_metadata_form()

    def open_document_in_admin_by_upload_id(self, upload_id: str) -> None:
        if not upload_id:
            return
        try:
            self.notebook.select(self.viewer_tab)
        except Exception:
            pass
        try:
            item = self.api_get_document_item(upload_id) if self.api_token else None
        except Exception:
            item = None
        if item:
            self.normalize_admin_item_path_for_current_pc(item)
            path = self.resolve_document_local_path(item)
            if path and path.exists():
                self.file_view_current_path = path
                self.file_view_current_metadata = item
                self.refresh_file_view_tree()
                self.load_file_view_metadata_form()
                return
        self.refresh_file_view_tree()
        messagebox.showwarning("Dokument öffnen", "Das Dokument konnte in der aktuellen Dateiansicht nicht direkt ausgewählt werden.")

