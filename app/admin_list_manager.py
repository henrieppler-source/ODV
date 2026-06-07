from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .api_client import ApiError
from .app_logging import app_log_exception
from .file_service import detect_document_type, load_metadata_files


class AdminListManagerMixin:
    def refresh_document_work_area(self, show_message: bool = False) -> None:
        """Aktualisiert den Dokument-Arbeitsbereich in der Dateiansicht."""
        try:
            self.refresh_file_view_tree()
            return
        except Exception as exc:
            app_log_exception("Dateiansicht konnte nicht aktualisiert werden", exc)

    def refresh_admin_uploads(self, show_message: bool = True) -> None:
        """Lädt im API-/Produktivmodus ausschließlich aktive MySQL/API-Datensätze.

        Lokale JSON-Dateien bleiben Sicherung, werden hier aber nicht mehr als
        aktive Bearbeitungsliste eingemischt. Verwaiste Sicherungen werden über
        Admin > Lokale Sicherungsdateien prüfen/bereinigen geprüft.
        """
        self.configure_admin_actions_for_role()

        for row in self.admin_tree.get_children():
            self.admin_tree.delete(row)

        wanted_status = self.admin_status_var.get()
        wanted_folder = self.admin_folder_var.get().strip()
        visible: list[dict] = []
        self.admin_uploads = []

        if not self.api_token:
            if show_message:
                messagebox.showwarning("API", "Keine API-Anmeldung vorhanden. Dateien bearbeiten zeigt im Produktivmodus nur MySQL/API-Datensätze.")
            return

        try:
            only_own = not self.is_current_admin()
            response = self.api.list_documents(self.api_token, status=wanted_status if wanted_status != "alle" else None, only_own=only_own)
            self.admin_uploads = [self.api_document_to_item(doc) for doc in response.get("documents", [])]
            self.refresh_document_type_options_from_documents(self.admin_uploads)
            if not self.is_current_admin():
                self.admin_uploads = [it for it in self.admin_uploads if self.is_selected_document_owner(it)]
            for _item in self.admin_uploads:
                self.normalize_admin_item_path_for_current_pc(_item)
                _p = self.resolve_document_local_path(_item)
                if _p and not _item.get("document_type"):
                    _item["document_type"] = detect_document_type(_p)
            include_missing = wanted_status in {"alle", "ohne"}
            if self.is_missing_odv_folder_filter(wanted_folder):
                visible = self.missing_odv_items_for_admin_folder(wanted_folder) if include_missing else []
            else:
                visible = [it for it in self.admin_uploads if self.admin_upload_matches_folder(it, wanted_folder)]
                if include_missing and self.is_current_admin() and wanted_folder and wanted_folder.casefold() != "alle":
                    visible.extend(self.missing_odv_items_for_admin_folder(wanted_folder))
        except ApiError as exc:
            app_log_exception("Admin-Dokumentliste konnte nicht aus MySQL/API geladen werden", exc)
            if show_message:
                messagebox.showwarning(
                    "API nicht erreichbar",
                    "Dateien bearbeiten zeigt im Produktivmodus nur MySQL/API-Datensätze.\n"
                    "Lokale JSON-Sicherungen werden hier nicht automatisch angezeigt.\n\n"
                    f"{exc}",
                )
            return

        self.admin_uploads = visible
        self.update_admin_tree_headings(missing_mode=self.is_missing_odv_folder_filter(wanted_folder))
        visible = self.sorted_admin_uploads_for_current_heading(visible)

        for item in visible:
            upload_id = str(item.get("upload_id", ""))
            if not upload_id:
                continue
            item["_tree_iid"] = upload_id
            self.admin_tree.insert(
                "",
                "end",
                iid=upload_id,
                values=(
                    item.get("_display_upload_id") or upload_id,
                    item.get("_display_status") or item.get("status", "hochgeladen"),
                    item.get("current_filename") or item.get("stored_filename") or item.get("original_filename", ""),
                    item.get("_display_by") if "_display_by" in item else (item.get("uploaded_by") or item.get("uploaded_by_name", "")),
                    item.get("_display_date") if "_display_date" in item else item.get("uploaded_at", ""),
                    item.get("document_type", ""),
                ),
            )
        if show_message:
            messagebox.showinfo("Dateien bearbeiten", f"{len(visible)} Uploads aus MySQL/API angezeigt.")

    def refresh_admin_folder_choices(self) -> None:
        folder_names = {str(folder).strip() for folder in self.admin_work_folder_names if str(folder).strip()}
        if self.is_current_admin():
            folder_names.add("00_ORTSCHRONIK")
        values = ["alle"] + sorted(folder_names, key=str.lower)
        self.admin_folder_combo["values"] = values
        current = self.admin_folder_var.get().strip()
        if current not in values:
            self.admin_folder_var.set("alle")

    def selected_admin_upload(self) -> dict | None:
        if self.is_unified_file_view_active():
            return self.selected_file_view_item_for_admin_actions()
        selection = self.admin_tree.selection()
        if not selection:
            return None
        upload_id = selection[0]
        for item in self.admin_uploads:
            if item.get("upload_id") == upload_id or item.get("_tree_iid") == upload_id:
                return item
        return None

    def selected_file_view_item_for_admin_actions(self) -> dict | None:
        path = self.file_view_current_path
        if path is None or not path.exists() or not path.is_file():
            return None
        item = self.file_view_current_metadata or self.item_for_local_path(path)
        if item:
            return item
        root = Path(self.base_folder_var.get().strip()).expanduser()
        try:
            rel_parent = str(path.parent.relative_to(root))
        except Exception:
            rel_parent = str(path.parent)
        try:
            tree_iid = self.file_tree.selection()[0] if self.file_tree.selection() else str(path)
        except Exception:
            tree_iid = str(path)
        return {
            "upload_id": f"__missing_odv__{path}",
            "_tree_iid": tree_iid,
            "_missing_odv_entry": True,
            "_display_upload_id": "neu",
            "_display_status": "ohne",
            "status": "ohne",
            "original_filename": path.name,
            "stored_filename": path.name,
            "current_filename": path.name,
            "current_path": str(path),
            "target_folder": str(path.parent),
            "uploaded_by": "",
            "uploaded_by_name": "",
            "uploaded_at": "",
            "_display_by": rel_parent if rel_parent and rel_parent != "." else root.name,
            "_display_date": "",
            "document_type": detect_document_type(path),
            "person_status": "none",
            "persons": [],
            "history": [],
            "odv_capture_mode": "existing_file_metadata",
        }

    def is_unified_file_view_active(self) -> bool:
        try:
            return self.notebook.select() == str(self.viewer_tab)
        except Exception:
            return False

    def update_admin_tree_headings(self, missing_mode: bool = False) -> None:
        if not self.admin_tree:
            return
        labels = dict(self.admin_tree_heading_labels)
        if missing_mode:
            labels.update({"by": "Ordner", "date": ""})
        else:
            labels.update({"by": "Erfasst von", "date": "Datum"})
        sort_col = self.admin_sort_column
        sort_reverse = self.admin_sort_reverse
        for col, label in labels.items():
            suffix = " ↓" if col == sort_col and sort_reverse else (" ↑" if col == sort_col else "")
            try:
                self.admin_tree.heading(col, text=f"{label}{suffix}", anchor="w", command=lambda c=col: self.sort_admin_tree_by_column(c))
            except Exception:
                pass

    def admin_sort_value(self, item: dict, column: str) -> str:
        if column == "upload_id":
            return str(item.get("_display_upload_id") or item.get("upload_id") or "")
        if column == "status":
            return str(item.get("_display_status") or item.get("status") or "")
        if column == "filename":
            return str(item.get("current_filename") or item.get("stored_filename") or item.get("original_filename") or "")
        if column == "by":
            return str(item.get("_display_by") if "_display_by" in item else (item.get("uploaded_by") or item.get("uploaded_by_name") or ""))
        if column == "date":
            return str(item.get("_display_date") if "_display_date" in item else item.get("uploaded_at") or "")
        if column == "type":
            return str(item.get("document_type") or "")
        return ""

    def sorted_admin_uploads_for_current_heading(self, items: list[dict]) -> list[dict]:
        column = self.admin_sort_column
        if not column:
            return items
        reverse = self.admin_sort_reverse
        return sorted(items, key=lambda item: self.admin_sort_value(item, column).casefold(), reverse=reverse)

    def sort_admin_tree_by_column(self, column: str) -> None:
        current = self.admin_sort_column
        self.admin_sort_reverse = not self.admin_sort_reverse if current == column else False
        self.admin_sort_column = column
        self.refresh_admin_uploads(show_message=False)

    def is_missing_odv_folder_filter(self, folder_name: str) -> bool:
        return self.normalize_folder_token(str(folder_name or "")) == self.normalize_folder_token("00_ORTSCHRONIK")

    def admin_root_for_folder_filter(self, folder_name: str) -> Path | None:
        folder_name = str(folder_name or "").strip()
        if not folder_name or folder_name.casefold() == "alle":
            return None
        token = self.normalize_folder_token(folder_name)
        base = self.nextcloud_base_path(show_message=False) or Path(self.base_folder_var.get().strip()).expanduser()
        direct = base / folder_name
        if direct.exists() and direct.is_dir():
            return direct
        try:
            for path in base.rglob("*"):
                if path.is_dir() and self.normalize_folder_token(path.name) == token:
                    return path
        except OSError:
            return None
        return None

    def missing_odv_items_for_admin_folder(self, folder_name: str) -> list[dict]:
        """Listet vorhandene Dateien ohne ODV-Eintrag für den gewählten Admin-Ordner."""
        if not self.is_current_admin():
            return []
        root = self.admin_root_for_folder_filter(folder_name)
        if root is None or not root.exists() or not root.is_dir():
            return []

        known_paths: set[str] = set()
        for item in self.admin_uploads or []:
            path_text = str(item.get("current_path") or "").strip()
            if path_text:
                try:
                    known_paths.add(str(Path(path_text).resolve()).lower())
                except Exception:
                    known_paths.add(str(Path(path_text)).lower())
        try:
            response = self.api.list_documents(self.api_token, only_own=False)
            for item in response.get("documents", []) or []:
                path_text = str(item.get("current_path") or "").strip()
                if path_text:
                    try:
                        known_paths.add(str(Path(path_text).resolve()).lower())
                    except Exception:
                        known_paths.add(str(Path(path_text)).lower())
        except Exception as exc:
            app_log_exception("Bekannte Dokumentpfade konnten nicht vollständig geladen werden", exc)
        try:
            for item in load_metadata_files(self.metadata_folder_path()):
                path_text = str(item.get("current_path") or "").strip()
                if path_text:
                    try:
                        known_paths.add(str(Path(path_text).resolve()).lower())
                    except Exception:
                        known_paths.add(str(Path(path_text)).lower())
        except Exception:
            pass

        metadata_folder = self.metadata_folder_path()
        paths: list[Path] = []
        try:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if metadata_folder in path.parents or path == metadata_folder:
                    continue
                if path.name.lower().endswith(".metadata.json"):
                    continue
                if any(str(part).upper() in {"_ARCHIV", "ARCHIV", "ARCHIVIERT", "ABGELEHNT", "GELOESCHT", "GELÖSCHT"} for part in path.parts):
                    continue
                if any(part.startswith(".ortschronik_") for part in path.parts):
                    continue
                if self.is_hidden_system_path(path) or self.is_linked_ocr_file_path(path):
                    continue
                try:
                    path_key = str(path.resolve()).lower()
                except Exception:
                    path_key = str(path).lower()
                if path_key in known_paths:
                    continue
                paths.append(path)
        except OSError:
            return []

        items: list[dict] = []
        for index, path in enumerate(sorted(paths, key=lambda p: (str(p.parent).lower(), p.name.lower()))):
            rel_parent = ""
            try:
                rel_parent = str(path.parent.relative_to(root))
            except ValueError:
                rel_parent = str(path.parent)
            items.append({
                "upload_id": f"__missing_odv__{index}",
                "_missing_odv_entry": True,
                "_display_upload_id": "neu",
                "_display_status": "ohne",
                "status": "ohne",
                "original_filename": path.name,
                "stored_filename": path.name,
                "current_filename": path.name,
                "current_path": str(path),
                "target_folder": str(path.parent),
                "uploaded_by": "",
                "uploaded_by_name": "",
                "uploaded_at": "",
                "_display_by": rel_parent if rel_parent and rel_parent != "." else root.name,
                "_display_date": "",
                "document_type": detect_document_type(path),
                "person_status": "none",
                "persons": [],
                "history": [],
                "odv_capture_mode": "existing_file_metadata",
                "odv_captured_by_admin": True,
            })
        return items

    def admin_upload_matches_folder(self, item: dict, folder_name: str) -> bool:
        folder_name = str(folder_name or "").strip()
        if not folder_name or folder_name.casefold() == "alle":
            return True
        for path_text in (item.get("current_path"), item.get("target_folder")):
            if not path_text:
                continue
            try:
                if self.is_path_under_named_folder(Path(str(path_text)), folder_name):
                    return True
            except Exception:
                continue
        return False

    def refresh_admin_destination_choices(self) -> None:
        # Zielordner sind die bereits ermittelten, lokal beschreibbaren Nextcloud-Ordner.
        # Wichtig: Hier NICHT erneut load_writable_folders() aufrufen, sonst entsteht beim Start
        # eine Rekursion: load_writable_folders -> refresh_admin_destination_choices -> load_writable_folders.
        base = Path(self.base_folder_var.get().strip()).expanduser()
        folders = list(self.writable_folders or [])
        self.admin_destination_map = {self.display_path_for_folder(path, base): path for path in folders}
        values = sorted(self.admin_destination_map.keys(), key=str.lower)
        self.admin_destination_combo["values"] = values
        if values and self.admin_destination_var.get() not in values:
            self.admin_destination_var.set(values[0])
        elif not values:
            self.admin_destination_var.set("")

    def choose_admin_destination(self) -> None:
        self.refresh_admin_destination_choices()
        selected = self.open_folder_tree_dialog("Datei ablegen in", self.writable_folders, self.admin_destination_var.get())
        if selected:
            self.select_combobox_path(self.admin_destination_var, self.admin_destination_combo, self.admin_destination_map, selected)

    def status_archive_target(self, status: str) -> Path | None:
        """Zielordner für Archivstatus unter 01_ABLAGE_ORTSCHRONIK."""
        status = self.normalize_document_status(status)
        folder_name = {"archiviert": "ARCHIVIERT"}.get(status)
        if not folder_name:
            return None
        base = self.nextcloud_base_path(show_message=False) or Path(self.base_folder_var.get().strip()).expanduser()
        return base / "01_ABLAGE_ORTSCHRONIK" / "_ARCHIV" / folder_name

    def is_path_under_named_folder(self, path: Path, folder_name: str) -> bool:
        token = self.normalize_folder_token(folder_name)
        try:
            return any(self.normalize_folder_token(part) == token for part in path.parts)
        except Exception:
            return False

