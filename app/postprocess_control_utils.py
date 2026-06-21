from __future__ import annotations

from typing import Any


def update_admin_openai_controls(manager: Any) -> None:
    path = manager.admin_selected_document_path()
    for button in (
        manager.admin_openai_button,
        manager.admin_openai_places_button,
        manager.admin_place_contexts_button,
        manager.admin_ocr_pdf_button,
    ):
        button.grid_remove()
    if path is None or not path.exists() or not path.is_file():
        manager.admin_openai_status_var.set("OpenAI: keine Datei ausgewählt")
        return
    suffix = path.suffix.lower()
    if suffix not in manager._OPENAI_SUPPORTED_SUFFIXES:
        manager.admin_openai_status_var.set("OpenAI: Datei ist kein lesbares Textdokument/PDF")
        return
    analysis_path = manager.existing_ocr_pdf_for_path(path) or path
    sample = manager.extract_upload_text_sample(
        analysis_path,
        max_chars=manager.openai_text_sample_chars(),
        max_pdf_pages=manager.openai_pdf_sample_pages(),
    )
    item = manager.selected_admin_upload() or {}
    can_edit = manager.can_edit_file_view_metadata(path, item)
    contexts_button = manager.admin_place_contexts_button
    contexts_available = bool(item.get("openai_place_contexts"))
    if contexts_available:
        contexts_button.grid()
        contexts_button.configure(state="normal")
    if sample:
        manager.admin_openai_button.grid()
        manager.admin_openai_button.configure(state=("normal" if can_edit else "disabled"))
        manager.admin_openai_places_button.grid()
        manager.admin_openai_places_button.configure(state=("normal" if can_edit else "disabled"))
        if manager.existing_ocr_pdf_for_path(path):
            manager.admin_openai_status_var.set("OpenAI: OCR-PDF vorhanden und lesbar")
        else:
            manager.admin_openai_status_var.set("OpenAI: Text lokal lesbar")
    elif suffix == ".pdf":
        manager.admin_ocr_pdf_button.grid()
        manager.admin_ocr_pdf_button.configure(state=("normal" if can_edit else "disabled"))
        manager.admin_openai_status_var.set("OpenAI: PDF ohne lesbaren Text - bitte PDF OCR erstellen")
    else:
        manager.admin_openai_status_var.set("OpenAI: Inhalt lokal nicht lesbar")
