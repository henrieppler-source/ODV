from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
import shutil

from .app_logging import app_log_exception
from .database import add_history
from .file_service import append_metadata_history, make_normalized_archive_filename, unique_path_with_counter
from .models import HistoryEntry


class AdminFileOpsManagerMixin:
    @staticmethod
    def _log_file_op_metadata_history(
        item: dict,
        display_name: str,
        action: str,
        description: str,
        upload_id: str | None = None,
    ) -> None:
        try:
            append_metadata_history(item, display_name, action, description)
        except Exception as exc:
            app_log_exception("Metadatenhistorie konnte nicht geschrieben werden", exc, upload_id=upload_id)

    def refresh_file_view_destination_choices(self) -> None:
        base = self.nextcloud_base_path(show_message=False)
        self.file_view_destination_map = {}
        values: list[str] = []
        if base and base.exists():
            folder_names = {str(folder).strip() for folder in self.admin_work_folder_names if str(folder).strip()}
            folder_names.add("00_ORTSCHRONIK")
            for folder_name in sorted(folder_names, key=str.lower):
                folder = self.admin_root_for_folder_filter(folder_name)
                if folder and folder.exists() and folder.is_dir():
                    self.file_view_destination_map[folder_name] = folder
                    values.append(folder_name)
        try:
            self.file_view_destination_combo.configure(values=values)
        except Exception:
            pass

    def choose_file_view_destination(self) -> None:
        if not self.is_current_admin():
            return
        self.refresh_file_view_destination_choices()
        folders = list(self.file_view_destination_map.values())
        selected = self.open_folder_tree_dialog("Zielordner auswählen", folders, self.file_view_destination_var.get())
        if selected:
            label = str(selected)
            for existing_label, path in self.file_view_destination_map.items():
                if Path(path) == selected:
                    label = existing_label
                    break
            if label not in self.file_view_destination_map:
                self.file_view_destination_map[label] = selected
                values = list(self.file_view_destination_combo["values"])
                if label not in values:
                    values.append(label)
                    self.file_view_destination_combo.configure(values=values)
            self.file_view_destination_var.set(label)

    def update_file_view_admin_actions_for_selection(self) -> None:
        if not self.is_current_admin():
            self.file_view_actions_frame.grid_remove()
            return
        self.file_view_actions_frame.grid()
        path = self.file_view_current_path
        state = "normal" if path and path.exists() and path.is_file() else "disabled"
        item = self.file_view_current_metadata if state == "normal" else None
        has_real_odv_entry = bool(item and item.get("upload_id") and not item.get("_missing_odv_entry"))
        self.new_status_var.set(str((item or {}).get("status") or ("ohne" if state == "normal" else "")))
        self.new_status_combo.configure(state=("readonly" if has_real_odv_entry else "disabled"))
        for widget in (self.file_view_destination_combo, self.file_view_rename_button):
            widget.configure(state=("readonly" if widget is self.file_view_destination_combo and state == "normal" else state))
        if state == "normal":
            item = item or {"current_filename": path.name, "current_path": str(path), "target_folder": str(path.parent), "status": "ohne"}
            self.update_admin_document_points_display(str(item.get("upload_id") or ""))
            self.file_view_new_filename_var.set(make_normalized_archive_filename(item, path.name))
            current_folder = path.parent
            selected_label = str(current_folder)
            for label, folder in self.file_view_destination_map.items():
                try:
                    if Path(folder).resolve() == current_folder.resolve():
                        selected_label = label
                        break
                except Exception:
                    if Path(folder) == current_folder:
                        selected_label = label
                        break
            if selected_label not in self.file_view_destination_map:
                self.file_view_destination_map[selected_label] = current_folder
                values = list(self.file_view_destination_combo["values"])
                if selected_label not in values:
                    values.append(selected_label)
                    self.file_view_destination_combo.configure(values=values)
            self.file_view_destination_var.set(selected_label)
        else:
            self.admin_document_points_var.set("keine Datei ausgewählt")

    def file_view_rename_or_move(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Admin/Superadmin sichtbar.")
            return
        current_path = self.file_view_current_path
        if current_path is None or not current_path.exists() or not current_path.is_file():
            messagebox.showwarning("Keine Datei", "Bitte zuerst im Baum eine Datei auswählen.")
            return
        destination_text = self.file_view_destination_var.get().strip()
        destination_folder = self.file_view_destination_map.get(destination_text)
        if destination_folder is None:
            destination_folder = Path(destination_text).expanduser() if destination_text else current_path.parent
        requested_filename = self.file_view_new_filename_var.get().strip() or current_path.name
        item = self.file_view_current_metadata or {
            "current_filename": current_path.name,
            "stored_filename": current_path.name,
            "original_filename": current_path.name,
            "current_path": str(current_path),
            "target_folder": str(current_path.parent),
            "document_type": self.file_view_meta_vars.get("document_type").get() if "document_type" in self.file_view_meta_vars else "",
        }
        new_filename = make_normalized_archive_filename(item, requested_filename)
        destination_folder.mkdir(parents=True, exist_ok=True)
        candidate_path = destination_folder / new_filename
        new_path = candidate_path if candidate_path == current_path else unique_path_with_counter(candidate_path)
        self.file_view_new_filename_var.set(new_path.name)
        if new_path == current_path:
            messagebox.showinfo("Keine Dateiänderung", "Dateiname und Ordner sind unverändert.")
            return
        if not messagebox.askyesno("Datei verschieben/umbenennen", f"Datei verschieben/umbenennen?\n\nVon:\n{current_path}\n\nNach:\n{new_path}"):
            return
        try:
            shutil.move(str(current_path), str(new_path))
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))
            return

        old_value = str(current_path)
        new_value = str(new_path)
        item["current_filename"] = new_path.name
        item["current_path"] = str(new_path)
        item["target_folder"] = str(destination_folder)
        ocr_msg = self.move_linked_ocr_pdf_for_item(item, new_path)
        display_name = self.display_name_var.get().strip() or "Admin"
        api_ok = True
        api_msg = "kein ODV-Datensatz vorhanden"
        if self.file_view_current_metadata:
            self._log_file_op_metadata_history(
                item,
                display_name,
                "Datei verschoben/umbenannt",
                f"{old_value} → {new_value}{ocr_msg}",
                upload_id=item.get("upload_id"),
            )
            api_ok, api_msg = self.save_item_to_api(item)
            self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Datei verschoben/umbenannt", f"{old_value} → {new_value} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        self.file_view_current_path = new_path
        if self.file_view_current_metadata:
            self.file_view_current_metadata = item
        try:
            self.refresh_file_view_tree()
            self.refresh_admin_uploads(show_message=False)
        except Exception:
            pass
        messagebox.showinfo("Datei", "Datei wurde verschoben/umbenannt." if api_ok else f"Datei wurde lokal geändert; MySQL nicht aktualisiert:\n{api_msg}")

    def admin_rename_or_move(self) -> None:
        item = self.selected_admin_upload()
        if not item:
            messagebox.showwarning("Keine Auswahl", "Bitte zuerst einen Upload auswählen.")
            return
        if not self.can_edit_admin_item(item):
            messagebox.showwarning("Keine Berechtigung", "Dieses Dokument kann nicht bearbeitet werden.")
            return
        if not self.is_current_admin():
            self.rename_own_pending_document(item)
            return

        self.normalize_admin_item_path_for_current_pc(item)
        current_path = self.resolve_document_local_path(item)
        if not current_path:
            messagebox.showerror("Fehler", "Die Datei konnte im lokalen Nextcloud-Stammverzeichnis nicht gefunden werden.")
            return
        if not current_path.exists():
            messagebox.showerror("Datei nicht gefunden", f"Die Datei wurde im Dateisystem nicht gefunden:\n{current_path}")
            return

        destination_folder_text = self.admin_destination_var.get().strip()
        destination_folder = self.admin_destination_map.get(destination_folder_text)
        if destination_folder is None:
            destination_folder = Path(destination_folder_text).expanduser() if destination_folder_text else current_path.parent
        requested_filename = self.admin_new_filename_var.get().strip() or current_path.name
        new_filename = make_normalized_archive_filename(item, requested_filename)
        destination_folder.mkdir(parents=True, exist_ok=True)
        candidate_path = destination_folder / new_filename
        new_path = candidate_path if candidate_path == current_path else unique_path_with_counter(candidate_path)
        self.admin_new_filename_var.set(new_path.name)

        if new_path == current_path:
            self.admin_save_metadata_fields(auto=True)
            messagebox.showinfo("Keine Dateiänderung", "Dateiname und Ordner sind unverändert. Metadaten wurden geprüft/gespeichert.")
            return

        confirm = messagebox.askyesno("Admin-Aktion bestätigen", f"Datei verschieben/umbenennen?\n\nVon:\n{current_path}\n\nNach:\n{new_path}\n\nDer Dateiname wurde normiert. Bei Namensgleichheit wird automatisch _#1, _#2 usw. ergänzt.")
        if not confirm:
            return

        try:
            shutil.move(str(current_path), str(new_path))
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))
            return

        display_name = self.display_name_var.get().strip() or "Admin"
        old_value = str(current_path)
        new_value = str(new_path)
        item["current_filename"] = new_path.name
        item["current_path"] = str(new_path)
        item["target_folder"] = str(destination_folder)
        ocr_msg = self.move_linked_ocr_pdf_for_item(item, new_path)
        old_status = str(item.get("status", "") or "")
        item["status"] = "erfasst"
        self.new_status_var.set("erfasst")
        append_text = f"{old_value} → {new_value}{ocr_msg}; Status: {old_status} → erfasst"
        self._log_file_op_metadata_history(
            item,
            display_name,
            "Datei verschoben/umbenannt",
            append_text,
            upload_id=item.get("upload_id"),
        )
        api_ok, api_msg = self.save_item_to_api(item)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Datei verschoben/umbenannt", f"{old_value} → {new_value} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        messagebox.showinfo("Admin", "Datei wurde verschoben/umbenannt und Metadaten wurden aktualisiert." if api_ok else f"Datei wurde lokal verschoben; MySQL nicht aktualisiert:\n{api_msg}")

    def rename_own_pending_document(self, item: dict) -> None:
        self.normalize_admin_item_path_for_current_pc(item)
        current_path = self.resolve_document_local_path(item)
        if not current_path or not current_path.exists():
            messagebox.showerror("Datei nicht gefunden", "Die Datei konnte lokal nicht gefunden werden.")
            return
        requested_filename = self.admin_new_filename_var.get().strip() or current_path.name
        new_filename = make_normalized_archive_filename(item, requested_filename)
        new_path = current_path.parent / new_filename
        if new_path != current_path:
            new_path = unique_path_with_counter(new_path)
        self.admin_new_filename_var.set(new_path.name)
        if new_path == current_path:
            self.admin_save_metadata_fields(auto=True)
            messagebox.showinfo("Keine Dateiänderung", "Dateiname ist unverändert. Metadaten wurden geprüft/gespeichert.")
            return
        if not messagebox.askyesno("Dateiname ändern", f"Datei umbenennen?\n\nVon:\n{current_path.name}\n\nNach:\n{new_path.name}"):
            return
        try:
            current_path.rename(new_path)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))
            return
        display_name = self.display_name_var.get().strip() or "Bearbeiter"
        old_value = str(current_path)
        new_value = str(new_path)
        item["current_filename"] = new_path.name
        item["current_path"] = str(new_path)
        item["target_folder"] = str(new_path.parent)
        ocr_msg = self.move_linked_ocr_pdf_for_item(item, new_path)
        self._log_file_op_metadata_history(
            item,
            display_name,
            "Datei umbenannt",
            f"{old_value} → {new_value}{ocr_msg}",
            upload_id=item.get("upload_id"),
        )
        api_ok, api_msg = self.save_item_to_api(item)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Datei umbenannt", f"{old_value} → {new_value} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        messagebox.showinfo("Dateiname", "Dateiname wurde gespeichert." if api_ok else f"Dateiname wurde lokal geändert; MySQL nicht aktualisiert:\n{api_msg}")
