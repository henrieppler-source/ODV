from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
import shutil

from .app_logging import app_log_exception
from .database import add_history
from .file_service import make_normalized_archive_filename, unique_path_with_counter
from .models import HistoryEntry


class AdminFileOpsManagerMixin:
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
        destination_folder = getattr(self, "admin_destination_map", {}).get(destination_folder_text)
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
        item["status"] = "uebernommen"
        if hasattr(self, "new_status_var"):
            self.new_status_var.set("uebernommen")
        append_text = f"{old_value} → {new_value}{ocr_msg}; Status: {old_status} → uebernommen"
        try:
            from .metadata_helpers import append_metadata_history
            append_metadata_history(item, display_name, "Datei verschoben/umbenannt", append_text, old_value=old_value, new_value=new_value)
        except Exception as exc:
            app_log_exception("Metadatenhistorie für Umbenennen/Verschieben konnte nicht geschrieben werden", exc, upload_id=item.get("upload_id"))
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
        try:
            from .metadata_helpers import append_metadata_history
            append_metadata_history(item, display_name, "Datei umbenannt", f"{old_value} → {new_value}{ocr_msg}", old_value=old_value, new_value=new_value)
        except Exception as exc:
            app_log_exception("Metadatenhistorie für Umbenennen konnte nicht geschrieben werden", exc, upload_id=item.get("upload_id"))
        api_ok, api_msg = self.save_item_to_api(item)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Datei umbenannt", f"{old_value} → {new_value} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        messagebox.showinfo("Dateiname", "Dateiname wurde gespeichert." if api_ok else f"Dateiname wurde lokal geändert; MySQL nicht aktualisiert:\n{api_msg}")
