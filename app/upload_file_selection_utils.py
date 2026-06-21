from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import threading
import urllib.parse

import tkinter as tk
from tkinter import filedialog, messagebox

from .app_logging import app_log, app_log_exception
from .file_service import detect_document_type


def choose_file(manager: Any) -> None:
    filename = filedialog.askopenfilename(title="Datei auswählen")
    if filename:
        manager.set_selected_upload_file(Path(filename), source="dialog")


def clear_selected_upload_file(manager: Any) -> None:
    manager._upload_file_selection_token += 1
    manager._stop_upload_file_loading_indicator()
    manager.clear_upload_form(keep_target_folder=True)
    manager.upload_drop_hint_var.set("Datei aus dem Explorer hierher ziehen oder über ‚Datei auswählen‘ wählen.")


def _start_upload_file_loading_indicator(manager: Any, token: int) -> None:
    manager._upload_file_selection_token = token
    manager._upload_file_loading_active = True
    manager._upload_file_loading_dot_count = 0
    manager._set_upload_file_loading_text("Datei wird geladen: Initialisierung", token)


def _set_upload_file_loading_text(manager: Any, text: str, token: int) -> None:
    if token != manager._upload_file_selection_token or not manager._upload_file_loading_active:
        return
    manager.file_var.set(text)


def _tick_upload_file_loading_indicator(manager: Any, token: int) -> None:
    if token != manager._upload_file_selection_token or not manager._upload_file_loading_active:
        return
    dot_count = manager._upload_file_loading_dot_count % 2
    manager.file_var.set("Datei wird geladen..." if dot_count == 0 else "Datei wird geladen")
    manager._upload_file_loading_dot_count += 1
    manager._upload_file_loading_job = manager.after(350, lambda: _tick_upload_file_loading_indicator(manager, token))


def _stop_upload_file_loading_indicator(manager: Any) -> None:
    manager._upload_file_loading_active = False
    if manager._upload_file_loading_job is not None:
        try:
            manager.after_cancel(manager._upload_file_loading_job)
        except Exception:
            pass
    manager._upload_file_loading_job = None


def _finalize_selected_upload_file(
    manager: Any,
    path: Path,
    source: str,
    previous_selected: Path | None,
    source_sha256: str,
    duplicate_documents: list[dict],
    token: int,
) -> None:
    if token != manager._upload_file_selection_token:
        return
    _set_upload_file_loading_text(manager, "Datei wird geladen: Duplikatprüfung ausgewertet", token)
    manager.update_idletasks()
    if not path.exists() or not path.is_file():
        messagebox.showwarning("Datei auswählen", f"Die Datei wurde nicht gefunden oder ist kein Dokument:\n{path}")
        manager.clear_upload_form(keep_target_folder=True)
        return

    if source_sha256 and duplicate_documents is not None and not manager.confirm_upload_for_duplicate(path, source_sha256, duplicate_documents=duplicate_documents):
        _set_upload_file_loading_text(manager, "Datei wurde bereits hochgeladen", token)
        manager.update_idletasks()
        manager.clear_upload_form(keep_target_folder=True)
        manager.upload_drop_hint_var.set("Auswahl abgebrochen: Datei wurde bereits in ODV hochgeladen (wurde nicht übernommen).")
        messagebox.showinfo(
            "Duplikatprüfung",
            "Die Datei wurde bereits in ODV erkannt.\n\n"
            "Der Upload wurde abgebrochen. Bitte eine andere Datei wählen oder im Warnungsdialog \"Trotzdem hochladen\" entscheiden.",
        )
        return

    _set_upload_file_loading_text(manager, "Datei wird geladen: Formular wird vorbereitet", token)
    manager.update_idletasks()
    manager._selected_upload_duplicate_checked = True
    manager.reset_upload_metadata_for_new_file()
    _set_upload_file_loading_text(manager, "Datei wird geladen: Dateityp wird erkannt", token)
    manager.update_idletasks()
    manager.selected_file = path
    manager.selected_folder = None
    manager._selected_upload_source_file = path
    manager._selected_upload_source_sha256 = source_sha256
    if source != "keep_ocr_link":
        manager.upload_ocr_pdf_path = None
    _set_upload_file_loading_text(manager, "Datei wird geladen: Dateivorschau wird geladen", token)
    manager.update_idletasks()
    manager.update_upload_image_preview(path)
    manager.update_upload_technical_fields(selected_file=path)
    detected_type = detect_document_type(manager.selected_file)
    manager.meta_vars["document_type"].set(detected_type)
    manager.remember_document_type(detected_type)
    if not manager.meta_vars.get("place").get().strip():
        manager.meta_vars["place"].set(manager.place_var.get().strip())
    _set_upload_file_loading_text(manager, "Datei wird geladen: Metadaten werden vorbereitet", token)
    manager.update_idletasks()
    manager.apply_image_metadata_suggestions(path)
    manager.apply_filename_keyword_suggestions(path)
    manager.refresh_planned_upload_filename(path)
    manager.refresh_upload_metadata_option_comboboxes()
    _set_upload_file_loading_text(manager, "Datei wird geladen: Formular finalisieren", token)
    manager.update_idletasks()
    manager.persons = []
    manager.person_status_var.set("none")
    manager.person_summary_var.set("Keine Personen markiert.")
    manager.upload_drop_hint_var.set(f"Ausgewählte Datei: {path.name}")
    manager.update_upload_status_indicator()
    manager.reset_openai_status()
    color, _text = manager.update_openai_precheck_indicator()
    ocr_path = manager.current_upload_ocr_pdf_path()
    if ocr_path:
        manager.upload_drop_hint_var.set(f"Ausgewählte Datei: {path.name} | OCR: {ocr_path.name}")
    manager.clear_pdf_text_searchability_cache(previous_selected)
    _set_upload_file_loading_text(manager, "Datei geladen", token)
    manager.update_idletasks()
    manager.after(
        300,
        lambda t=token: manager._commit_selected_upload_file_text(
            path=path,
            source=source,
            previous_selected=previous_selected,
            precheck_color=color,
            token=t,
        ),
    )
    _stop_upload_file_loading_indicator(manager)
    app_log("info", "Upload-Datei ausgewählt", path=str(path), source=source)


def _commit_selected_upload_file_text(
    manager: Any,
    path: Path,
    source: str,
    previous_selected: Path | None,
    precheck_color: str,
    token: int,
) -> None:
    if token != manager._upload_file_selection_token:
        return
    manager.file_var.set(manager.normalize_local_path_text(path))
    manager.upload_drop_hint_var.set(f"Ausgewählte Datei: {path.name}")
    if source != "keep_ocr_link":
        ocr_path = manager.current_upload_ocr_pdf_path()
        if ocr_path:
            manager.upload_drop_hint_var.set(f"Ausgewählte Datei: {path.name} | OCR: {ocr_path.name}")
    if precheck_color != "green":
        return
    manager.after(150, lambda: manager.queue_openai_check(auto_apply=True, allow_yellow=True))


def _load_selected_upload_file_async(
    manager: Any,
    path: Path,
    source: str,
    previous_selected: Path | None,
    source_sha256_hint: str,
    token: int,
) -> None:
    source_sha256 = source_sha256_hint
    duplicate_documents: list[dict] = []
    manager.after(0, lambda t=token: _set_upload_file_loading_text(manager, "Datei wird geladen: SHA-256 wird berechnet", t))
    if not source_sha256:
        source_sha256 = manager.compute_source_sha256(path)
        manager.after(0, lambda t=token: _set_upload_file_loading_text(manager, "Datei wird geladen: Duplikatprüfung läuft", t))
    else:
        manager.after(0, lambda t=token: _set_upload_file_loading_text(manager, "Datei wird geladen: SHA-256 vorhanden – Duplikate prüfen", t))
    if source_sha256:
        try:
            duplicate_documents = manager.find_duplicates_by_file_sha256(source_sha256)
        except Exception as exc:
            app_log_exception("Datei-Auswahl: Duplikatsprüfung via SHA-256 fehlgeschlagen", exc, path=str(path))
            duplicate_documents = []
    manager.after(
        0,
        lambda: _finalize_selected_upload_file(
            manager,
            path,
            source,
            previous_selected,
            source_sha256,
            duplicate_documents,
            token,
        ),
    )


def set_selected_upload_file(manager: Any, path: Path, source: str = "dialog") -> None:
    """Übernimmt eine einzelne Datei in den Upload-Reiter.

    Wird sowohl vom klassischen Datei-Auswahldialog als auch von Drag & Drop
    genutzt. Drag & Drop startet bewusst keinen Upload, sondern wählt nur die
    Datei aus; der Benutzer muss weiterhin „Datei hochladen“ klicken.
    """
    previous_selected = manager.selected_file
    path = Path(path).expanduser()
    if not path.exists() or not path.is_file():
        messagebox.showwarning("Datei auswählen", f"Die Datei wurde nicht gefunden oder ist kein Dokument:\n{path}")
        return
    manager._upload_file_selection_token += 1
    token = manager._upload_file_selection_token
    _start_upload_file_loading_indicator(manager, token)
    thread = threading.Thread(
        target=_load_selected_upload_file_async,
        args=(manager, path, source, previous_selected, "", token),
        daemon=True,
    )
    thread.start()


def reset_upload_metadata_for_new_file(manager: Any) -> None:
    """Leert fachliche Upload-Metadaten beim Wechsel auf ein neues Dokument."""
    manager._upload_filename_auto_value = ""
    keep_empty_or_system = {"upload_id", "status", "current_filename", "uploaded_at", "uploaded_by"}
    for key, var in manager.meta_vars.items():
        if isinstance(var, tk.BooleanVar):
            var.set(False)
        elif key in keep_empty_or_system:
            var.set("")
        elif key == "place":
            var.set(manager.place_var.get().strip())
        else:
            var.set("")
    manager.description_text.delete("1.0", "end")
    manager.note_text.delete("1.0", "end")
    manager.update_description_counter(manager.description_text, manager.upload_description_counter_var)
    manager.persons = []
    manager.person_status_var.set("none")
    manager.person_summary_var.set("Keine Personen markiert.")


def link_upload_ocr_pdf(manager: Any, path: Path) -> None:
    path = Path(path).expanduser()
    if not path.exists() or not path.is_file():
        messagebox.showwarning("PDF OCR", f"Das OCR-PDF wurde nicht gefunden:\n{path}")
        return
    manager.upload_ocr_pdf_path = path
    manager.clear_pdf_text_searchability_cache(manager.selected_file)
    manager.clear_upload_ocr_path_cache(manager.selected_file)
    manager.clear_upload_text_sample_cache(path)
    if manager.selected_file:
        manager.upload_drop_hint_var.set(f"Ausgewählte Datei: {manager.selected_file.name} | OCR: {path.name}")
    manager.update_openai_precheck_indicator()
    manager.after(150, lambda: manager.queue_openai_check(auto_apply=True, allow_yellow=True))


def parse_dropped_files(manager: Any, data: str) -> list[Path]:
    """Parst Dateipfade aus tkinterdnd2-Dropdaten, auch mit Leerzeichen."""
    if not data:
        return []
    try:
        parts = manager.tk.splitlist(data)
    except Exception:
        parts = [data]
    paths: list[Path] = []
    for part in parts:
        text = str(part).strip().strip("{}")
        if text.startswith("file://"):
            text = urllib.parse.unquote(text[7:])
            if os.name == "nt" and text.startswith("/") and len(text) > 2 and text[2] == ":":
                text = text[1:]
        if text:
            paths.append(Path(text))
    return paths


def handle_upload_file_drop(manager: Any, event) -> str:
    dropped_data = ""
    try:
        dropped_data = event.data
    except Exception:
        dropped_data = ""
    paths = [p for p in manager.parse_dropped_files(dropped_data) if p.exists()]
    files = [p for p in paths if p.is_file()]
    folders = [p for p in paths if p.is_dir()]
    if files:
        if len(files) > 1:
            messagebox.showinfo("Drag & Drop", "Es wurde mehr als eine Datei gezogen. Für diesen Upload wird die erste Datei übernommen.")
        manager.set_selected_upload_file(files[0], source="drag_drop")
    elif folders:
        messagebox.showinfo("Drag & Drop", "Bitte für Drag & Drop eine einzelne Datei ablegen. Ordner bitte weiterhin über „Ordner auswählen“ wählen.")
    else:
        messagebox.showwarning("Drag & Drop", "Es konnte keine gültige Datei übernommen werden.")
    return "break"


def enable_upload_drag_and_drop(manager: Any, *widgets: Any) -> None:
    """Aktiviert Drag & Drop im Upload-Reiter, sofern tkinterdnd2 verfügbar ist."""
    if manager.DND_FILES is None:
        manager.upload_drop_hint_var.set("Drag & Drop ist in diesem Build nicht verfügbar. Bitte „Datei auswählen“ verwenden.")
        return
    for widget in widgets + (manager.upload_file_entry, manager.upload_drop_hint, manager.upload_tab):
        try:
            widget.drop_target_register(manager.DND_FILES)
            widget.dnd_bind("<<Drop>>", manager.handle_upload_file_drop)
        except Exception as exc:
            app_log_exception("Drag & Drop konnte für Upload-Widget nicht aktiviert werden", exc)


def choose_upload_folder(manager: Any) -> None:
    folder = filedialog.askdirectory(title="Ordner mit Dateien auswählen")
    if folder:
        manager.selected_folder = Path(folder)
        manager.selected_file = None
        manager.file_var.set(manager.normalize_local_path_text(folder))
        manager.update_upload_image_preview(None)
        manager.meta_vars["document_type"].set("Mehrere Dateien")
        manager.remember_document_type("Mehrere Dateien")
        if not manager.meta_vars.get("place").get().strip():
            manager.meta_vars["place"].set(manager.place_var.get().strip())
        manager.persons = []
        manager.person_status_var.set("none")
        manager.person_summary_var.set("Ordnerupload: Personenmarkierung je Datei nicht aktiv.")
        manager.update_upload_status_indicator()
        manager.reset_openai_status()
