from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import threading

from tkinter import messagebox

from .app_logging import app_log_exception
from .file_service import append_metadata_history, unique_path_with_counter


def admin_create_ocr_for_selected_document(manager: Any) -> None:
    item = manager.selected_admin_upload()
    path = manager.admin_selected_document_path()
    if not item or path is None or path.suffix.lower() != ".pdf":
        messagebox.showwarning("PDF OCR", "Bitte zuerst ein PDF-Dokument auswählen.")
        return
    ocr_backend = manager.find_pdf_ocr_backend()
    if not ocr_backend:
        messagebox.showerror("PDF OCR", "Es wurde kein PDF-OCR-Werkzeug gefunden.")
        return
    target = unique_path_with_counter(path.with_name(f"{path.stem}_ocr.pdf"))
    manager.admin_openai_status_var.set("PDF OCR läuft ...")
    manager.admin_ocr_pdf_button.configure(state="disabled")

    def run() -> None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            backend_name, backend_config = ocr_backend
            if backend_name == "pymupdf":
                manager._run_pdf_ocr_with_pymupdf(path, target, backend_config)
            else:
                manager._run_pdf_ocr_with_ocrmypdf(path, target, backend_config)

            def finish() -> None:
                item["ocr_pdf_path"] = str(target)
                item["ocr_pdf_filename"] = target.name
                item["ocr_source_filename"] = path.name
                item["ocr_created_at"] = datetime.now().isoformat(timespec="seconds")
                append_metadata_history(item, manager.display_name_var.get().strip() or "Admin", "PDF OCR erstellt", target.name)
                manager.save_item_to_api(item)
                manager.save_item_json_if_present(item)
                if path.suffix.lower() == ".pdf":
                    manager.file_view_current_metadata = item
                    manager.load_file_view_metadata_form()
                manager.update_admin_openai_controls()
                manager.admin_openai_status_var.set("PDF OCR fertig - OpenAI kann jetzt prüfen")
                messagebox.showinfo("PDF OCR", f"Durchsuchbares PDF wurde erstellt:\n{target}")

            manager.after(0, finish)
        except Exception as exc:
            app_log_exception("Admin-PDF-OCR konnte nicht ausgeführt werden", exc, source=str(path), target=str(target))
            manager.after(0, lambda: manager.admin_openai_status_var.set("PDF OCR fehlgeschlagen"))
            manager.after(0, lambda: messagebox.showerror("PDF OCR", f"OCR konnte nicht ausgeführt werden:\n{exc}"))
            manager.after(0, manager.update_admin_openai_controls)

    threading.Thread(target=run, daemon=True).start()


def create_ocr_for_document_path(manager: Any, path: Path | None, item: dict | None = None, on_success=None) -> None:
    """Erzeugt OCR für eine einzelne PDF-Datei und verknüpft sie optional mit einem Datensatz."""
    if path is None or path.suffix.lower() != ".pdf":
        messagebox.showwarning("PDF OCR", "Bitte zuerst ein PDF-Dokument auswählen.")
        return
    ocr_backend = manager.find_pdf_ocr_backend()
    if not ocr_backend:
        messagebox.showerror("PDF OCR", "Es wurde kein PDF-OCR-Werkzeug gefunden.")
        return
    item = item if isinstance(item, dict) else (manager.item_for_local_path(path) or None)
    source = path
    target = unique_path_with_counter(source.with_name(f"{source.stem}_ocr.pdf"))

    def run() -> None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            backend_name, backend_config = ocr_backend
            if backend_name == "pymupdf":
                manager._run_pdf_ocr_with_pymupdf(source, target, backend_config)
            else:
                manager._run_pdf_ocr_with_ocrmypdf(source, target, backend_config)

            if item is not None:
                item["ocr_pdf_path"] = str(target)
                item["ocr_pdf_filename"] = target.name
                item["ocr_source_filename"] = source.name
                item["ocr_created_at"] = datetime.now().isoformat(timespec="seconds")
                append_metadata_history(item, manager.display_name_var.get().strip() or "Admin", "PDF OCR erstellt", f"{source.name} → {target.name}")
                if str(source) in manager.file_view_metadata_by_path:
                    manager.file_view_metadata_by_path[str(source)] = item
                if manager.file_view_current_path == source:
                    manager.file_view_current_metadata = item
                metadata_file = str(item.get("_metadata_file") or "").strip()
                if metadata_file and not item.get("_pending_existing_file_metadata"):
                    try:
                        manager.save_file_view_item_to_storage(item, Path(metadata_file), False)
                    except Exception:
                        pass

            if on_success:
                manager.after(0, on_success)
            manager.after(0, lambda: messagebox.showinfo("PDF OCR", f"Durchsuchbares PDF wurde erstellt:\n{target}"))
        except Exception as exc:
            app_log_exception("PDF-OCR konnte nicht ausgeführt werden", exc, source=str(source), target=str(target))
            manager.after(
                0,
                lambda: messagebox.showerror("PDF OCR", f"PDF OCR konnte nicht ausgeführt werden:\n{exc}"),
            )

    threading.Thread(target=run, daemon=True).start()
