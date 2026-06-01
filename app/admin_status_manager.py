from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, simpledialog
import shutil

from .database import add_history
from .models import HistoryEntry
from .ui_helpers import clear_text_widget
from .file_service import append_metadata_history, unique_path_with_counter


class AdminStatusManagerMixin:
    def normalize_document_status(self, status: str) -> str:
        return (status or "").strip().lower()

    def move_linked_ocr_pdf_for_item(self, item: dict, new_document_path: Path) -> str:
        ocr_path = self.resolve_item_ocr_pdf_path(item)
        if not ocr_path:
            return ""
        target = new_document_path.with_name(f"{new_document_path.stem}_ocr.pdf")
        if ocr_path.resolve() == target.resolve():
            item["ocr_pdf_path"] = str(target)
            item["ocr_pdf_filename"] = target.name
            return ""
        target = unique_path_with_counter(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ocr_path), str(target))
        item["ocr_pdf_path"] = str(target)
        item["ocr_pdf_filename"] = target.name
        return f"; OCR-PDF: {ocr_path} -> {target}"

    def move_admin_item_for_status(self, item: dict, old_status: str, new_status: str) -> tuple[bool, str]:
        """Verschiebt Dateien bei archiviert in den Ablage-Archivbereich."""
        new_status = self.normalize_document_status(new_status)
        old_status = self.normalize_document_status(old_status)
        current_path = self.resolve_document_local_path(item)
        if not current_path or not current_path.exists() or not current_path.is_file():
            return True, "Keine physische Datei verschoben."

        if new_status == "archiviert":
            if not self.is_path_under_named_folder(current_path, "01_ABLAGE_ORTSCHRONIK"):
                return False, "Archivieren ist nur für Dateien aus 01_ABLAGE_ORTSCHRONIK erlaubt."
            target_dir = self.status_archive_target(new_status)
            if target_dir is None:
                return True, ""
            target_dir.mkdir(parents=True, exist_ok=True)
            if not item.get("archived_from_path"):
                item["archived_from_path"] = str(current_path)
            target_path = unique_path_with_counter(target_dir / current_path.name)
            if target_path != current_path:
                shutil.move(str(current_path), str(target_path))
                item["current_filename"] = target_path.name
                item["current_path"] = str(target_path)
                item["target_folder"] = str(target_dir)
                ocr_msg = self.move_linked_ocr_pdf_for_item(item, target_path)
            else:
                ocr_msg = ""
            return True, f"Datei nach {target_dir.name} verschoben{ocr_msg}."

        if new_status == "hochgeladen" and old_status == "archiviert":
            old_path_text = str(item.get("archived_from_path") or "").strip()
            if old_path_text:
                old_path = Path(old_path_text).expanduser()
                old_path.parent.mkdir(parents=True, exist_ok=True)
                target_path = unique_path_with_counter(old_path)
                if target_path != current_path:
                    shutil.move(str(current_path), str(target_path))
                    item["current_filename"] = target_path.name
                    item["current_path"] = str(target_path)
                    item["target_folder"] = str(target_path.parent)
                    self.move_linked_ocr_pdf_for_item(item, target_path)
                item["archived_from_path"] = ""
                return True, "Datei aus Archiv/Papierkorb reaktiviert."
            return True, "Kein ursprünglicher Pfad gespeichert; bitte Zielordner ggf. manuell wählen."
        return True, ""

    def admin_set_status(self, silent: bool = False) -> None:
        if not self.require_admin():
            return
        item = self.selected_admin_upload()
        if not item:
            if not silent:
                messagebox.showwarning("Keine Auswahl", "Bitte zuerst einen Upload auswählen.")
            return
        new_status = self.new_status_var.get().strip()
        old_status = self.normalize_document_status(item.get("status", "hochgeladen"))
        if new_status == old_status:
            return
        display_name = self.display_name_var.get().strip() or "Admin"

        if new_status == "rueckfrage":
            question = simpledialog.askstring(
                "Rückfrage erfassen",
                "Bitte die Rückfrage oder den Korrekturhinweis eingeben:",
                parent=self,
            )
            if question is None:
                self.new_status_var.set(str(old_status))
                return
            question = question.strip()
            if not question:
                self.new_status_var.set(str(old_status))
                messagebox.showwarning("Dokumentstatus", "Für eine Rückfrage muss ein Hinweis erfasst werden.")
                return
            item["status_note"] = question

        moved_ok, move_msg = self.move_admin_item_for_status(item, str(old_status), str(new_status))
        if not moved_ok:
            self.new_status_var.set(str(old_status))
            if not silent:
                messagebox.showwarning("Dokumentstatus", move_msg)
            return

        item["status"] = new_status
        details = f"{old_status} -> {new_status}" + (f"; Hinweis: {item.get('status_note')}" if new_status == "rueckfrage" and str(item.get("status_note") or "").strip() else "")
        details += (f"; {move_msg}" if move_msg else "")
        append_metadata_history(item, display_name, "Dokumentstatus geändert", details, old_value=old_status, new_value=new_status)
        api_ok, api_msg = self.save_item_to_api(item)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Dokumentstatus geändert", f"{item.get('upload_id')}: {details} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        if not silent:
            messagebox.showinfo("Dokumentstatus", "Dokumentstatus wurde gespeichert." if api_ok else f"Dokumentstatus lokal gespeichert; MySQL nicht aktualisiert:\n{api_msg}")
