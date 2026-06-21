from __future__ import annotations

from pathlib import Path
from typing import Any

from tkinter import messagebox

from .app_logging import app_log_exception
from .file_service import detect_document_type, is_image_file
from .person_tagger import PersonTagger

try:
    from PIL import Image, ImageOps, ImageTk
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageOps = None
    ImageTk = None


UPLOAD_METADATA_REQUIRED_FIELDS = ("document_date", "event", "place", "keywords")


def set_upload_status(manager: Any, color: str, text: str) -> None:
    manager.upload_status_canvas.delete("all")
    manager.upload_status_canvas.create_oval(1, 1, 13, 13, fill=color, outline=color)
    manager.upload_status_text_var.set(text)


def is_upload_metadata_ready(manager: Any) -> bool:
    for key in UPLOAD_METADATA_REQUIRED_FIELDS:
        value = manager.meta_vars.get(key)
        if value is None or not str(value.get() or "").strip():
            return False
    return True


def evaluate_upload_status(manager: Any) -> tuple[str, str]:
    if manager.selected_folder is not None:
        return "yellow", "Ordnerupload"
    if manager.selected_file is None:
        return "red", "Keine Datei"
    if not manager.selected_file.exists():
        return "red", "Datei fehlt"
    detected_type = detect_document_type(manager.selected_file)
    ready = is_upload_metadata_ready(manager)
    if detected_type == "Sonstiges":
        return "yellow", "Dateityp unklar"
    if not ready:
        return "yellow", "Metadaten ergänzen"
    return "green", "Bereit zum Upload"


def update_upload_status_indicator(manager: Any) -> None:
    color, text = evaluate_upload_status(manager)
    set_upload_status(manager, color, text)


def update_upload_image_preview(manager: Any, path: Path | None) -> None:
    if manager.upload_image_preview_label is None:
        return
    if path is None or not path.exists():
        manager.upload_image_preview_label.configure(text="", image="")
        manager._upload_preview_photo = None
        return

    if not is_image_file(path):
        manager.upload_image_preview_label.configure(text="", image="")
        manager._upload_preview_photo = None
        return

    if Image is None or ImageTk is None:
        manager.upload_image_preview_label.configure(text="Pillow nicht installiert - Vorschau nicht verfügbar.", image="")
        manager._upload_preview_photo = None
        return

    try:
        image = Image.open(path)
        try:
            if ImageOps is not None:
                image = ImageOps.exif_transpose(image)
        except Exception:
            pass
        image = image.convert("RGB")
        image.thumbnail((420, 420))
        photo = ImageTk.PhotoImage(image)
        manager.upload_image_preview_label.configure(image=photo, text="")
        manager._upload_preview_photo = photo
    except Exception as exc:
        app_log_exception("Upload-Bildvorschau konnte nicht geladen werden", exc)
        manager.upload_image_preview_label.configure(text="Vorschau nicht möglich.", image="")
        manager._upload_preview_photo = None


def open_person_tagger(manager: Any) -> None:
    if not manager.selected_file:
        messagebox.showwarning("Keine Datei", "Bitte zuerst eine Bilddatei auswählen.")
        return
    if not is_image_file(manager.selected_file):
        messagebox.showwarning("Keine Bilddatei", "Personenmarkierung ist im MVP nur für Bilddateien vorgesehen.")
        return
    tagger = PersonTagger(manager, manager.selected_file)
    result = tagger.show_modal()
    if result is not None:
        manager.persons = result
        manager.person_status_var.set("identified" if manager.persons else "none")
        manager.person_summary_var.set(f"{len(manager.persons)} Personen markiert.")
