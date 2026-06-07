from __future__ import annotations

from pathlib import Path
import importlib.util
import re
import threading
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import urllib.parse
import os
from datetime import datetime
from typing import Any

try:
    from tkinterdnd2 import DND_FILES
except Exception:
    DND_FILES = None

try:
    from PIL import Image, ImageOps, ImageTk
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageOps = None
    ImageTk = None

from .app_logging import app_log, app_log_exception
from .config import (
    APP_DIR,
    OPENAI_DEFAULT_MODEL,
    OPENAI_MODEL_OPTIONS,
    OPENAI_PDF_SAMPLE_PAGES,
    OPENAI_TEXT_SAMPLE_CHARS,
    OPENAI_USAGE_MODELS,
)
from .file_service import detect_document_type, is_image_file, make_normalized_archive_filename, unique_path_with_counter
from .openai_client import OpenAIClient, OpenAIError
from .person_tagger import PersonTagger
from .ui_helpers import reset_tk_var, clear_text_widget
from .upload_wizard import UploadWizard
from .upload_tab_metadata_utils import (
    append_openai_description as _utm_append_openai_description,
    local_places_from_text as _utm_local_places_from_text,
    merge_metadata_values as _utm_merge_metadata_values,
    merge_place_values as _utm_merge_place_values,
    normalize_upload_text_sample as _utm_normalize_upload_text_sample,
    limit_openai_keywords as _utm_limit_openai_keywords,
)
from .upload_tab_openai_cache_utils import (
    add_openai_metadata_cache_entry as _utauc_add_openai_metadata_cache_entry,
    cached_openai_metadata_for_key as _utauc_cached_openai_metadata_for_key,
    openai_metadata_cache_key as _utauc_openai_metadata_cache_key,
    openai_metadata_cache_path as _utauc_openai_metadata_cache_path,
    load_openai_metadata_cache as _utauc_load_openai_metadata_cache,
    save_openai_metadata_cache as _utauc_save_openai_metadata_cache,
)

LOCAL_PLACE_NAMES = [
    "Bedheim", "Eicha", "Gleicherwiesen", "Gleichamberg", "Hindfeld", "Milz",
    "Mendhausen", "Roth", "Haina", "Römhild", "Sülzdorf", "Westenfeld",
    "Zeilfeld", "Mönchshof", "Simmershausen",
]

UPLOAD_METADATA_REQUIRED_FIELDS = ("document_date", "event", "place", "keywords")


class UploadTabMixin:
    def create_upload_tab(self) -> None:
        """Upload-Reiter mit geführtem Wizard."""
        self.upload_tab.columnconfigure(0, weight=1)
        top = ttk.LabelFrame(self.upload_tab, text="Datei / Ziel", padding=8)
        top.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 8))
        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)

        upload_split = ttk.PanedWindow(top, orient=tk.HORIZONTAL)
        upload_split.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        upload_left = ttk.Frame(upload_split)
        upload_left.columnconfigure(0, weight=0)
        upload_left.columnconfigure(1, weight=0)
        upload_left.columnconfigure(2, weight=1)
        upload_left.rowconfigure(0, weight=0)
        upload_left.rowconfigure(1, weight=0)
        upload_left.rowconfigure(2, weight=0)
        upload_left.rowconfigure(3, weight=0)
        upload_left.rowconfigure(4, weight=0)
        upload_left.rowconfigure(5, weight=0)
        upload_left.rowconfigure(6, weight=0)
        upload_left.rowconfigure(7, weight=0)
        upload_left.rowconfigure(8, weight=1)

        upload_right = ttk.Frame(upload_split)
        upload_right.columnconfigure(0, weight=1)
        upload_right.rowconfigure(0, weight=1)

        self.upload_drop_hint_var = tk.StringVar(value="Datei aus dem Explorer hierher ziehen oder über ‚Datei auswählen‘ wählen.")
        self.file_var = tk.StringVar()
        self.upload_filename_var = tk.StringVar()
        self._upload_filename_auto_value = ""
        self._upload_preview_photo = None

        file_select_button_width = 16
        upload_button_width = 24
        target_tree_button_width = 34
        file_button_frame = ttk.Frame(upload_left)
        file_button_frame.grid(row=1, column=1, sticky="se", padx=(6, 6), pady=(0, 6))
        ttk.Button(
            file_button_frame,
            text="Datei auswählen",
            command=self.choose_file,
            width=file_select_button_width,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            file_button_frame,
            text="Datei entfernen",
            command=self.clear_selected_upload_file,
            width=file_select_button_width - 2,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        file_button_frame.columnconfigure(0, weight=1)

        self.open_file_openai_button = ttk.Button(
            upload_left,
            text="OpenAI prüfen",
            command=self.queue_openai_check,
            width=target_tree_button_width,
        )
        self.open_file_openai_button.grid(row=2, column=1, sticky="ew", padx=(6, 6), pady=(0, 6))
        self.upload_openai_metadata_button = ttk.Button(upload_left, text="Metadaten übernehmen", command=self.on_apply_openai_metadata, state="disabled", width=upload_button_width)
        self.upload_openai_metadata_button.grid(row=3, column=1, sticky="nw", padx=(6, 6), pady=(0, 6))
        self.upload_ocr_pdf_button = ttk.Button(upload_left, text="PDF OCR erstellen", command=self.create_searchable_pdf_for_upload, width=upload_button_width)
        self.upload_ocr_pdf_button.grid(row=4, column=1, sticky="nw", padx=(6, 6), pady=(0, 6))
        self.upload_show_ocr_pdf_button = ttk.Button(upload_left, text="OCR anzeigen", command=self.open_upload_ocr_pdf, state="disabled", width=upload_button_width)
        self.upload_show_ocr_pdf_button.grid(row=5, column=1, sticky="nw", padx=(6, 6), pady=(0, 6))

        ttk.Label(upload_left, text="Datei:").grid(row=1, column=0, sticky="sw", pady=(0, 0))
        self.upload_drop_hint = ttk.Label(upload_left, textvariable=self.upload_drop_hint_var, foreground="#555555")
        self.upload_drop_hint.grid(row=0, column=2, sticky="w", padx=(0, 6), pady=(6, 2))
        self.upload_file_entry = ttk.Entry(upload_left, textvariable=self.file_var)
        self.upload_file_entry.grid(row=1, column=2, sticky="sew", padx=(0, 6), pady=(0, 6))

        status_container = ttk.Frame(upload_left)
        self.upload_status_container = status_container
        status_container.grid(row=2, column=2, sticky="nw", padx=(0, 6), pady=(0, 6))
        self.upload_status_canvas = tk.Canvas(status_container, width=14, height=14, highlightthickness=0)
        self.upload_status_canvas.grid(row=0, column=0, sticky="w")
        self.upload_status_text_var = tk.StringVar(value="Keine Datei")
        ttk.Label(status_container, textvariable=self.upload_status_text_var, foreground="#555555").grid(row=0, column=1, sticky="w", padx=(6, 8))
        self.upload_openai_text_var = tk.StringVar(value="OpenAI: nicht konfiguriert")
        ttk.Label(status_container, textvariable=self.upload_openai_text_var, foreground="#555555").grid(row=0, column=2, sticky="w", padx=(8, 8))
        self.upload_openai_usage_var = tk.StringVar(value="Verbrauch: k.A.")
        ttk.Label(status_container, textvariable=self.upload_openai_usage_var, foreground="#555555").grid(row=0, column=3, sticky="w", padx=(8, 0))

        precheck_container = ttk.Frame(upload_left)
        self.upload_precheck_container = precheck_container
        precheck_container.grid(row=3, column=2, sticky="nw", padx=(0, 6), pady=(0, 6))
        self.upload_openai_precheck_canvas = tk.Canvas(precheck_container, width=14, height=14, highlightthickness=0)
        self.upload_openai_precheck_canvas.grid(row=0, column=0, sticky="w")
        self.upload_openai_precheck_var = tk.StringVar(value="OpenAI-Ampel: keine Datei")
        ttk.Label(precheck_container, textvariable=self.upload_openai_precheck_var, foreground="#555555", wraplength=760).grid(row=0, column=1, sticky="w", padx=(6, 0))

        self.upload_ocr_progress_var = tk.StringVar(value="")
        self.upload_ocr_progress_frame = ttk.Frame(upload_left)
        self.upload_ocr_progress_frame.grid(row=4, column=2, sticky="ew", padx=(0, 6), pady=(0, 6))
        self.upload_ocr_progress_frame.columnconfigure(0, weight=1)
        self.upload_ocr_progress = ttk.Progressbar(self.upload_ocr_progress_frame, mode="indeterminate", length=260)
        self.upload_ocr_progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(self.upload_ocr_progress_frame, textvariable=self.upload_ocr_progress_var, foreground="#555555").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.upload_ocr_progress_frame.grid_remove()

        self.target_folder_var = tk.StringVar()
        target_row_padding = (6, 0)
        ttk.Label(upload_left, text="Zielordner Nextcloud:").grid(row=6, column=0, sticky="sw", pady=target_row_padding)
        target_button_frame = ttk.Frame(upload_left)
        target_button_frame.grid(row=6, column=1, sticky="s", padx=(6, 6), pady=target_row_padding)
        ttk.Button(
            target_button_frame,
            text="Baum...",
            command=self.choose_upload_target_tree,
            width=target_tree_button_width,
        ).grid(row=0, column=0, sticky="ew")
        self.target_combo = ttk.Combobox(upload_left, textvariable=self.target_folder_var, state="readonly")
        self.target_combo.grid(row=6, column=2, sticky="sew", padx=(0, 6), pady=target_row_padding)
        ttk.Label(upload_left, text="Ziel-Dateiname:").grid(row=7, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(upload_left, textvariable=self.upload_filename_var).grid(row=7, column=1, columnspan=2, sticky="ew", padx=(6, 6), pady=(6, 0))

        self.upload_preview_frame = ttk.LabelFrame(upload_right, text="Vorschau", padding=(6, 4))
        self.upload_preview_frame.grid(row=0, column=0, sticky="nsew")
        upload_right.rowconfigure(0, weight=1)
        upload_right.columnconfigure(0, weight=1)
        self.upload_image_preview_label = ttk.Label(self.upload_preview_frame, text="", anchor="center", justify="center", width=34)
        self.upload_image_preview_label.grid(row=0, column=0, sticky="nsew")
        self.upload_preview_frame.rowconfigure(0, weight=1)
        self.upload_preview_frame.columnconfigure(0, weight=1)
        self.upload_image_preview_label.configure(width=34)

        upload_split.add(upload_left, weight=3)
        upload_split.add(upload_right, weight=1)
        for _option in ("minsize", "width"):
            try:
                if _option == "width":
                    upload_split.pane(upload_right, width=320)
                else:
                    upload_split.paneconfigure(upload_right, minsize=260)
                break
            except Exception:
                continue
        self.enable_upload_drag_and_drop(upload_left)

        wizard_frame = ttk.Frame(upload_left)
        wizard_frame.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=(0, 6), pady=(6, 0))
        self.upload_wizard = UploadWizard(self, wizard_frame)
        self.update_upload_technical_fields(selected_file=None)
        self.update_upload_status_indicator()
        self.update_openai_precheck_indicator()
        self.refresh_upload_ai_controls_visibility()

    def update_upload_technical_fields(self, selected_file: Path | None = None) -> None:
        """Befüllt die technischen Upload-Felder im Upload-Reiter."""
        display_name = self.display_name_var.get().strip() or self.username_var.get().strip() or ""
        if "uploaded_by" in self.meta_vars:
            self.meta_vars["uploaded_by"].set(display_name)
        if "status" in self.meta_vars:
            self.meta_vars["status"].set("noch nicht hochgeladen")
        if "upload_id" in self.meta_vars:
            self.meta_vars["upload_id"].set("")
        if selected_file is not None and "current_filename" in self.meta_vars:
            planned = self.planned_upload_filename(selected_file)
            self.meta_vars["current_filename"].set(planned)
            self._upload_filename_auto_value = planned
        elif "current_filename" in self.meta_vars:
            self.meta_vars["current_filename"].set("")
            self._upload_filename_auto_value = ""
        if selected_file is not None and "uploaded_at" in self.meta_vars:
            self.meta_vars["uploaded_at"].set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        elif "uploaded_at" in self.meta_vars:
            self.meta_vars["uploaded_at"].set("")

    def planned_upload_filename(self, source: Path, requested_name: str | None = None) -> str:
        metadata = {key: var.get() for key, var in self.meta_vars.items()}
        metadata["current_filename"] = (requested_name or metadata.get("current_filename") or source.name).strip()
        metadata["stored_filename"] = metadata.get("stored_filename") or metadata["current_filename"]
        metadata["original_filename"] = metadata.get("original_filename") or source.name
        return make_normalized_archive_filename(metadata, metadata["current_filename"])

    def refresh_planned_upload_filename(self, source: Path | None = None, force: bool = False) -> None:
        if "current_filename" not in self.meta_vars:
            return
        source = source or self.selected_file
        if source is None:
            return
        current_value = str(self.meta_vars["current_filename"].get() or "").strip()
        should_update = force or not current_value or current_value == self._upload_filename_auto_value
        if not should_update:
            return
        planned = self.planned_upload_filename(source, current_value or source.name)
        self._upload_filename_auto_value = planned
        self.meta_vars["current_filename"].set(planned)

    def openai_available(self) -> bool:
        return bool(self.config_data.get("openai_api_key", "").strip())

    def _read_int_config(self, key: str, default: int, min_value: int = 0, max_value: int | None = None) -> int:
        try:
            value = int(self.config_data.get(key, default))
        except Exception:
            return default
        if min_value is not None:
            value = max(min_value, value)
        if max_value is not None:
            value = min(max_value, value)
        return value

    def openai_client(self, model_name: str | None = None) -> OpenAIClient | None:
        api_key = self.config_data.get("openai_api_key", "").strip()
        if not api_key:
            return None
        if str(self.current_role()).strip().lower() in {"admin", "superadmin"}:
            model = str(model_name or self.config_data.get("openai_model", OPENAI_DEFAULT_MODEL) or OPENAI_DEFAULT_MODEL).strip()
        else:
            model = OPENAI_DEFAULT_MODEL
        return OpenAIClient(api_key=api_key, model=model or OPENAI_DEFAULT_MODEL)

    def upload_openai_model_choices(self, cached_model: str | None = None) -> list[str]:
        models: list[str] = []
        current = str(self.config_data.get("openai_model", OPENAI_DEFAULT_MODEL) or OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL
        for model in (current, *OPENAI_MODEL_OPTIONS, str(cached_model or "").strip()):
            if not model:
                continue
            if model not in models:
                models.append(model)
        return models

    def choose_upload_openai_model(self, cached_model: str | None = None) -> str:
        current_model = str(self.config_data.get("openai_model", OPENAI_DEFAULT_MODEL) or OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL
        cached_model = str(cached_model or "").strip()
        model_values = self.upload_openai_model_choices(cached_model)
        if not model_values:
            model_values = [current_model]

        dialog = tk.Toplevel(self)
        dialog.title("OpenAI-Modell wählen")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("540x200")
        dialog.columnconfigure(0, weight=1)

        intro_parts = [f"Aktuelles Standardmodell: {current_model}"]
        if cached_model:
            intro_parts.append(f"Gespeichertes Ergebnis ist mit Modell: {cached_model}")
        intro_parts.append("Wählen Sie das Modell für die Prüfung.")
        ttk.Label(dialog, text=" | ".join(intro_parts), wraplength=500).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        ttk.Label(dialog, text="OpenAI-Modell:").grid(row=1, column=0, sticky="w", padx=12)
        model_var = tk.StringVar(value=current_model if current_model in model_values else model_values[0])
        ttk.Combobox(dialog, textvariable=model_var, values=model_values, state="readonly").grid(row=2, column=0, sticky="ew", padx=12)
        dialog.columnconfigure(0, weight=1)

        info_var = tk.StringVar(value="")
        info_label = ttk.Label(dialog, textvariable=info_var, foreground="#555555", wraplength=500)
        info_label.grid(row=3, column=0, sticky="w", padx=12, pady=(8, 8))

        result = {"model": ""}

        def apply_choice() -> None:
            result["model"] = model_var.get().strip()
            dialog.destroy()

        def update_info(*_args) -> None:
            chosen = model_var.get().strip()
            if cached_model and chosen == cached_model:
                info_var.set("Gespeicherte Vorschläge werden verwendet (falls vorhanden).")
                action_button.configure(text="Gespeicherte Vorschläge anzeigen")
            else:
                if chosen:
                    info_var.set(f"Es wird ein neuer OpenAI-Lauf mit „{chosen}“ gestartet.")
                    action_button.configure(text="Mit OpenAI prüfen")
                else:
                    info_var.set("Bitte wählen Sie ein Modell.")
                    action_button.configure(text="Modell wählen")

        buttons = ttk.Frame(dialog)
        buttons.grid(row=4, column=0, sticky="e", padx=12, pady=(2, 12))
        action_button = ttk.Button(buttons, text="Modell wählen", command=apply_choice)
        action_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)

        model_var.trace_add("write", update_info)
        update_info()
        self.wait_window(dialog)
        return result["model"]

    def is_upload_text_or_pdf_document(self, path: Path | None = None) -> bool:
        path = path or self.selected_file
        if path is None:
            return False
        return path.suffix.lower() in {".pdf", ".txt", ".md", ".csv", ".log", ".docx", ".odt", ".xlsx"}

    def is_upload_image_pdf(self, path: Path | None = None) -> bool:
        path = path or self.selected_file
        if path is None or path.suffix.lower() != ".pdf":
            return False
        if path.name.lower().endswith("_ocr.pdf"):
            return False
        ocr_path = self.current_upload_ocr_pdf_path()
        if ocr_path and ocr_path.exists():
            return True
        return not self.pdf_is_non_searchable_text(path, max_chars=500, max_pdf_pages=2)

    def _pdf_text_cache_key(self, path: Path) -> str | None:
        try:
            stat = path.stat()
        except Exception:
            return None
        return f"{path}|{stat.st_size}|{stat.st_mtime_ns}"

    def pdf_is_non_searchable_text(self, path: Path | None, max_chars: int = 500, max_pdf_pages: int = 2, has_linked_ocr: bool = False) -> bool:
        if path is None or path.suffix.lower() != ".pdf":
            return False
        if path.name.lower().endswith("_ocr.pdf"):
            return False
        if has_linked_ocr:
            return False
        path = path.expanduser()
        cache_key = self._pdf_text_cache_key(path)
        if not cache_key:
            return False
        cached = self._pdf_text_searchability_cache.get(str(path))
        if cached and cached[0] == cache_key:
            return cached[1]
        has_text = bool(self.extract_upload_text_sample(path, max_chars=max_chars, max_pdf_pages=max_pdf_pages))
        result = not has_text
        self._pdf_text_searchability_cache[str(path)] = (cache_key, result)
        return result

    def clear_pdf_text_searchability_cache(self, path: Path | None = None) -> None:
        if path is None:
            self._pdf_text_searchability_cache = {}
            return
        for key in (str(path), str(path.expanduser()), str(path.resolve())):
            self._pdf_text_searchability_cache.pop(key, None)

    def refresh_upload_ai_controls_visibility(self) -> None:
        show_ai = self.is_upload_text_or_pdf_document()
        widgets = [
            self.open_file_openai_button,
            self.upload_status_container,
            self.upload_precheck_container,
        ]
        for widget in widgets:
            widget.grid() if show_ai else widget.grid_remove()
        self.upload_openai_metadata_button.grid_remove()

        show_ocr_create = self.is_upload_image_pdf() and not self.current_upload_ocr_pdf_path()
        show_ocr_open = self.is_upload_image_pdf() and bool(self.current_upload_ocr_pdf_path())
        self.upload_ocr_pdf_button.grid() if show_ocr_create else self.upload_ocr_pdf_button.grid_remove()
        self.upload_show_ocr_pdf_button.grid() if show_ocr_open else self.upload_show_ocr_pdf_button.grid_remove()

    def clear_upload_form(self, keep_target_folder: bool = True) -> None:
        selected_target = self.target_folder_var.get()
        self.clear_pdf_text_searchability_cache(self.selected_file)
        self.selected_file = None
        self.selected_folder = None
        self._selected_upload_source_file = None
        self._selected_upload_source_sha256 = ""
        self._selected_upload_duplicate_checked = False
        self.upload_ocr_pdf_path = None
        self.file_var.set("")
        self.upload_drop_hint_var.set("Datei aus dem Explorer hierher ziehen oder über ‚Datei auswählen‘ wählen.")
        self.update_upload_image_preview(None)
        for key, var in self.meta_vars.items():
            if key == "place":
                try:
                    var.set(self.place_var.get().strip())
                except Exception:
                    pass
                continue
            reset_tk_var(var)
        clear_text_widget(self.description_text)
        self.update_description_counter(self.description_text, self.upload_description_counter_var)
        clear_text_widget(self.note_text)
        self.person_status_var.set("none")
        self.persons = []
        self.person_summary_var.set("Keine Personen markiert.")
        self.upload_wizard.show_step(0)
        self.update_upload_status_indicator()
        self.upload_openai_text_var.set("OpenAI: nicht geprüft")
        self.upload_openai_usage_var.set("Verbrauch: k.A.")
        self.update_openai_precheck_indicator()
        if keep_target_folder:
            self.target_folder_var.set(selected_target)

    def openai_pdf_sample_pages(self) -> int:
        return self._read_int_config("openai_pdf_sample_pages", OPENAI_PDF_SAMPLE_PAGES, 1, 100)

    def openai_text_sample_chars(self) -> int:
        return self._read_int_config("openai_text_sample_chars", OPENAI_TEXT_SAMPLE_CHARS, 500, 100000)

    def format_openai_usage(self, usage: dict[str, Any], model_name: str | None = None) -> str:
        if not usage:
            return "Verbrauch: k.A."
        total = usage.get("total_tokens")
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if total is None:
            return "Verbrauch: k.A."
        details = f"{total} Tokens"
        if prompt is not None and completion is not None:
            details += f" (p{prompt}+c{completion})"
        model_key = str(model_name or self.config_data.get("openai_model", "") or "").strip().lower()
        price = OPENAI_USAGE_MODELS.get(model_key)
        if price and prompt is not None and completion is not None:
            cost = (float(prompt) * price["input"] + float(completion) * price["output"]) / 1_000_000
            details += f" | ca. ${cost:.4f}"
            context = int(price.get("context") or 0)
            if context:
                details += f" | Kontext frei: {max(0, context - int(total))}"
        else:
            details += " | Kosten/Rest: k.A."
        return f"Verbrauch: {details}"

    def reset_openai_status(self, message: str | None = None) -> None:
        """Setzt den OpenAI-Status zurück, ohne einen API-Aufruf auszulösen."""
        self.openai_metadata_suggestions = {}
        self.openai_metadata_applied_fields = []
        self.openai_metadata_source_model = ""
        self.upload_openai_metadata_button.configure(state="disabled")

        if not self.openai_available():
            status = "OpenAI: nicht konfiguriert"
        elif not self.selected_file:
            status = "OpenAI: keine Einzeldatei ausgewählt"
        else:
            status = message or "OpenAI: nicht geprüft"

        self.upload_openai_text_var.set(status)
        self.upload_openai_usage_var.set("Verbrauch: k.A.")
        self.update_openai_precheck_indicator()

    def set_openai_precheck_status(self, color: str, text: str) -> None:
        self.upload_openai_precheck_canvas.delete("all")
        self.upload_openai_precheck_canvas.create_oval(1, 1, 13, 13, fill=color, outline=color)
        self.upload_openai_precheck_var.set(text)

    def update_openai_precheck_indicator(self) -> tuple[str, str]:
        color, text = self.evaluate_openai_precheck()
        self.set_openai_precheck_status(color, text)
        self.refresh_upload_ai_controls_visibility()
        self.open_file_openai_button.configure(state=("disabled" if color == "red" else "normal"))
        self.upload_ocr_pdf_button.configure(state=("normal" if self.is_upload_image_pdf() else "disabled"))
        ocr_path = self.current_upload_ocr_pdf_path()
        self.upload_show_ocr_pdf_button.configure(state=("normal" if ocr_path and ocr_path.exists() else "disabled"))
        return color, text

    def evaluate_openai_precheck(self) -> tuple[str, str]:
        path = self.selected_file
        if self.selected_folder is not None:
            return "yellow", "OpenAI-Ampel gelb: Ordnerupload - OpenAI-Prüfung nur für einzelne Dateien."
        if path is None:
            return "red", "OpenAI-Ampel rot: keine Datei ausgewählt."
        if not path.exists() or not path.is_file():
            return "red", "OpenAI-Ampel rot: Datei fehlt oder ist nicht lesbar."

        suffix = path.suffix.lower()
        blocked_extensions = {
            ".exe", ".msi", ".bat", ".cmd", ".ps1", ".dll", ".com", ".scr",
            ".zip", ".7z", ".rar", ".tar", ".gz", ".db", ".sqlite", ".sqlite3",
        }
        if suffix in blocked_extensions:
            return "red", "OpenAI-Ampel rot: technische/Archivdatei - nicht an OpenAI senden."

        ocr_path = self.current_upload_ocr_pdf_path()
        sample = self.extract_upload_text_sample(
            ocr_path if ocr_path and ocr_path.exists() else path,
            max_chars=min(2500, self.openai_text_sample_chars()),
            max_pdf_pages=self.openai_pdf_sample_pages(),
        )
        text = sample or ""
        lower_text = text.lower()
        lower_name = path.name.lower()

        sensitive_patterns = [
            (r"\biban\b|\bde\d{20}\b", "Bankdaten"),
            (r"\bdiagnose\b|\bpatient\b|\bkrankenkasse\b|\bmedikation\b|\bbefund\b", "Gesundheitsdaten"),
            (r"\bpersonalausweis\b|\bausweisnummer\b|\bsteuer-id\b|\bsteuernummer\b", "Ausweis-/Steuerdaten"),
            (r"\bpasswort\b|\bkennwort\b|\bapi[_ -]?key\b|\btoken\b", "Zugangsdaten"),
        ]
        for pattern, label in sensitive_patterns:
            if re.search(pattern, lower_text) or re.search(pattern, lower_name):
                return "red", f"OpenAI-Ampel rot: mögliche {label} erkannt - nicht an OpenAI senden."

        if not sample:
            if suffix in {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}:
                if suffix == ".pdf":
                    return "yellow", "OpenAI-Ampel gelb: PDF enthält lokal keinen lesbaren Text - bitte ggf. zuerst PDF OCR erstellen."
                return "yellow", "OpenAI-Ampel gelb: kein lokaler Textauszug - Prüfung wäre nur eingeschränkt möglich."
            return "yellow", "OpenAI-Ampel gelb: Inhalt lokal nicht auslesbar - OpenAI-Prüfung möglich, aber unsicher."

        if len(text.strip()) < 120:
            return "yellow", "OpenAI-Ampel gelb: sehr wenig Text - OpenAI kann prüfen, Ergebnis kann dünn sein."

        archive_terms = [
            "ortschron", "niederschrift", "protokoll", "chronik", "geschichte",
            "datum", "ort:", "zeit/dauer", "tagesordnung", "verein", "stadt",
            "gemeinde", "archiv", "quelle", "veranstaltung",
        ]
        if any(term in lower_text or term in lower_name for term in archive_terms):
            return "green", "OpenAI-Ampel grün: Text ist lokal lesbar und wirkt für Metadatenprüfung geeignet."

        return "yellow", "OpenAI-Ampel gelb: Prüfung mit OpenAI möglich, Archivbezug ist lokal nicht eindeutig."

    def current_upload_ocr_pdf_path(self) -> Path | None:
        path = self.upload_ocr_pdf_path
        if path:
            path = Path(path)
            if path.exists() and path.is_file():
                return path
        inferred = self.inferred_upload_ocr_pdf_path()
        if inferred:
            self.upload_ocr_pdf_path = inferred
            return inferred
        return None

    def inferred_upload_ocr_pdf_path(self) -> Path | None:
        selected = self.selected_file
        if not selected:
            return None
        selected = Path(selected)
        if selected.suffix.lower() != ".pdf" or selected.name.lower().endswith("_ocr.pdf"):
            return None
        exact = selected.with_name(f"{selected.stem}_ocr.pdf")
        if exact.exists() and exact.is_file():
            return exact
        candidates = [
            candidate for candidate in selected.parent.glob(f"{selected.stem}_ocr_#*.pdf")
            if candidate.is_file()
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)

    def open_upload_ocr_pdf(self) -> None:
        path = self.current_upload_ocr_pdf_path()
        if not path:
            messagebox.showwarning("OCR anzeigen", "Zu dieser Datei ist noch kein OCR-PDF verknüpft.")
            return
        self.open_file_with_default_app(path)

    def extract_upload_text_sample(self, path: Path | None, max_chars: int = 4000, max_pdf_pages: int = OPENAI_PDF_SAMPLE_PAGES) -> str | None:
        """Liest einen kurzen Textauszug für OpenAI und lokale Metadatenableitung.

        Wichtig: Das ist nur eine lokale Dateianalyse. Es wird dabei kein OpenAI-Aufruf
        ausgelöst. Für DOCX wird der Text direkt aus dem ZIP/XML gelesen; dadurch werden
        Protokolle, Briefe usw. nicht nur nach Dateiname bewertet.
        """
        if path is None:
            return None
        try:
            suffix = path.suffix.lower()
            if suffix in {".txt", ".md", ".csv", ".log"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                return self.normalize_upload_text_sample(text, max_chars=max_chars)
            if suffix == ".xlsx":
                text = self._extract_excel_text(path)
                return self.normalize_upload_text_sample(text, max_chars=max_chars)
            if suffix == ".pdf":
                text_parts: list[str] = []
                try:
                    import warnings
                    from pypdf import PdfReader

                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        reader = PdfReader(str(path), strict=False)
                    for page in reader.pages[:max_pdf_pages]:
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            text_parts.append(page_text)
                        if sum(len(part) for part in text_parts) >= max_chars:
                            break
                except Exception as exc:
                    app_log_exception("PDF-Textauszug konnte nicht gelesen werden", exc, path=str(path))
                return self.normalize_upload_text_sample("\n".join(text_parts), max_chars=max_chars)
            if suffix == ".docx":
                text_parts: list[str] = []
                with zipfile.ZipFile(path) as zf:
                    names = zf.namelist()
                    xml_names = [n for n in names if n == "word/document.xml" or n.startswith("word/header") or n.startswith("word/footer")]
                    for xml_name in xml_names:
                        try:
                            root = ET.fromstring(zf.read(xml_name))
                        except Exception:
                            continue
                        for node in root.iter():
                            if node.tag.endswith("}t") and node.text:
                                text_parts.append(node.text)
                            elif node.tag.endswith("}tab"):
                                text_parts.append("\t")
                            elif node.tag.endswith("}br") or node.tag.endswith("}p"):
                                text_parts.append("\n")
                return self.normalize_upload_text_sample(" ".join(text_parts), max_chars=max_chars)
            if suffix == ".odt":
                with zipfile.ZipFile(path) as zf:
                    raw = zf.read("content.xml").decode("utf-8", errors="ignore")
                raw = re.sub(r"<text:p[^>]*>", "\n", raw)
                raw = re.sub(r"<[^>]+>", " ", raw)
                return self.normalize_upload_text_sample(raw, max_chars=max_chars)
        except Exception as exc:
            app_log_exception("OpenAI-Textauszug konnte nicht gelesen werden", exc, path=str(path))
        return None

    def _extract_excel_text(self, path: Path) -> str | None:
        try:
            try:
                import openpyxl
            except Exception:
                openpyxl = None

            if openpyxl is not None:
                text_chunks: list[str] = []
                workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
                try:
                    for worksheet in workbook.worksheets:
                        for row in worksheet.iter_rows(values_only=True):
                            for value in row:
                                text = str(value).strip() if value is not None else ""
                                if text:
                                    text_chunks.append(text)
                            if len(text_chunks) > 20000:
                                break
                        if len(text_chunks) > 20000:
                            break
                finally:
                    try:
                        workbook.close()
                    except Exception:
                        pass
                return " ".join(text_chunks)

            with zipfile.ZipFile(path) as zf:
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in zf.namelist():
                    shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                    for item in shared_root:
                        piece: list[str] = []
                        for node in item.iter():
                            if node.tag.endswith("}t") and node.text:
                                piece.append(node.text)
                        value = "".join(piece).strip()
                        if value:
                            shared_strings.append(value)

                sheet_files = [name for name in zf.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")]
                if not sheet_files:
                    return None

                text_chunks: list[str] = []
                for sheet_name in sheet_files:
                    sheet_root = ET.fromstring(zf.read(sheet_name))
                    for cell in sheet_root.iter():
                        if not cell.tag.endswith("}c"):
                            continue
                        value_type = cell.get("t")
                        value_text = ""
                        for child in cell:
                            tag = child.tag
                            if tag.endswith("}v"):
                                value_text = child.text or ""
                                break
                            if value_type == "inlineStr" and tag.endswith("}t"):
                                value_text = child.text or ""
                                break
                        if not value_text:
                            continue
                        if value_type == "s":
                            try:
                                index = int(value_text)
                                if 0 <= index < len(shared_strings):
                                    value_text = shared_strings[index]
                            except Exception:
                                pass
                        value = str(value_text).strip()
                        if value:
                            text_chunks.append(value)
                    if len(text_chunks) > 20000:
                        break
                return " ".join(text_chunks)
            return None
        except Exception as exc:
            app_log_exception("Excel-Textauszug konnte nicht gelesen werden", exc, path=str(path))
            return None

    def normalize_upload_text_sample(self, text: str | None, max_chars: int = 4000) -> str | None:
        return _utm_normalize_upload_text_sample(text, max_chars=max_chars)

    def local_places_from_text(self, text: str | None) -> list[str]:
        return _utm_local_places_from_text(text, LOCAL_PLACE_NAMES)

    def merge_place_values(self, current: str, suggested: str) -> str:
        return _utm_merge_place_values(current, suggested)

    def merge_metadata_values(self, current: str, suggested: str, separator: str = ", ") -> str:
        return _utm_merge_metadata_values(current, suggested, separator=separator)

    def append_openai_description(self, current: str, suggested: str) -> str:
        model = str(self.openai_metadata_source_model or self.config_data.get("openai_model", "") or OPENAI_DEFAULT_MODEL).strip()
        return _utm_append_openai_description(current, suggested, model)

    def derive_metadata_from_text(self, filename: str, extension: str, sample: str | None) -> dict[str, str]:
        """Robuste lokale Fallback-Ableitung für typische Protokolle/Niederschriften.

        Diese Werte kosten keine API-Tokens und verhindern, dass bei DOCX-Dateien mit
        klar erkennbarem Inhalt der Übernahme-Button leer bleibt, nur weil das Modell
        vorsichtig oder zu knapp antwortet.
        """
        metadata: dict[str, str] = {}
        text = sample or ""
        lower_name = filename.lower()
        lower_text = text.lower()

        if "niederschrift" in lower_name or "niederschrift" in lower_text:
            metadata["document_type"] = "Niederschrift / Protokoll"
        elif extension.lower() == ".docx":
            metadata["document_type"] = "Word-Dokument"

        date_match = re.search(r"(?:am|Zeit/Dauer:)\s*(\d{1,2}\.\d{1,2}\.\d{4})", text, flags=re.IGNORECASE)
        if not date_match:
            date_match = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", text)
        if date_match:
            metadata["document_date"] = date_match.group(1)

        place_match = re.search(r"(?:^|\n)\s*Ort:\s*([^\n]+)", text, flags=re.IGNORECASE)
        if place_match:
            metadata["place"] = place_match.group(1).strip(" .;,-")
        detected_places = self.local_places_from_text(text)
        if detected_places:
            metadata["place"] = self.merge_place_values(metadata.get("place", ""), ", ".join(detected_places))

        title_line = ""
        for line in text.splitlines():
            line = line.strip()
            if line:
                title_line = line
                break
        if title_line:
            event = title_line
            event = re.sub(r"^Niederschrift\s+über\s+die\s+", "", event, flags=re.IGNORECASE)
            event = re.sub(r"\s+am\s+\d{1,2}\.\d{1,2}\.\d{4}.*$", "", event, flags=re.IGNORECASE).strip()
            metadata["event"] = event[:160]

        keywords: list[str] = []
        keyword_candidates = [
            "Ortschronisten", "Stadt Römhild", "Sülzdorf", "Zeilfeld", "Gleichamberg",
            "Steinsburgfreunde", "altes Rathaus Römhild", "Geschichtsblätter", "Kinder wie die Zeit vergeht",
            "Datenschutz", "DSGVO", "Internetseite", "Fördermittel", "Thüringer Ehrenamtsstiftung",
            "Grabsteinprojekt", "Computergenealogie", "Ortschronistensatzung", "Flurnamenarchiv",
            "Kreisheimattag", "Tag des offenen Denkmals",
        ]
        for kw in keyword_candidates:
            if kw.lower() in lower_text:
                keywords.append(kw)
        if keywords:
            metadata["keywords"] = ", ".join(list(dict.fromkeys(keywords))[:12])

        if text:
            description_parts: list[str] = []
            if title_line:
                description_parts.append(title_line.rstrip("."))
            if metadata.get("place") or metadata.get("document_date"):
                description_parts.append(
                    "Ort/Zeit: " + ", ".join(v for v in [metadata.get("place", ""), metadata.get("document_date", "")] if v)
                )
            topics: list[str] = []
            for kw in ["Steinsburgfreunde", "Arbeitsräume", "Geschichtsblätter", "Datenschutz", "Internetseite", "Fördermittel", "Grabsteinprojekt", "Ortschronistensatzung"]:
                if kw.lower() in lower_text:
                    topics.append(kw)
            if topics:
                description_parts.append("Behandelte Themen: " + ", ".join(topics[:8]) + ".")
            if description_parts:
                metadata["description"] = " ".join(description_parts)[:600]

        if "ortschronisten" in lower_text:
            metadata.setdefault("primary_source", "Ortschronisten der Stadt Römhild")
        return metadata

    def create_searchable_pdf_for_upload(self) -> None:
        path = self.selected_file
        if path is None or path.suffix.lower() != ".pdf":
            messagebox.showwarning("PDF OCR", "Bitte zuerst eine PDF-Datei auswählen.")
            return
        if self.extract_upload_text_sample(path, max_chars=500):
            if not messagebox.askyesno("PDF OCR", "Dieses PDF enthält bereits lesbaren Text.\n\nTrotzdem eine OCR-PDF-Kopie erstellen?"):
                return

        ocr_backend = self.find_pdf_ocr_backend()
        if not ocr_backend:
            messagebox.showerror(
                "PDF OCR",
                "Es wurde kein PDF-OCR-Werkzeug gefunden.\n\n"
                "Installiert sein muss entweder OCRmyPDF oder Tesseract mit PyMuPDF. "
                "Danach kann ODV daraus eine durchsuchbare PDF-Kopie erzeugen.",
            )
            return

        target_path = unique_path_with_counter(path.with_name(f"{path.stem}_ocr.pdf"))

        self.upload_openai_text_var.set("PDF OCR läuft …")
        self.upload_openai_usage_var.set("Verbrauch: k.A.")
        self.start_upload_ocr_progress("PDF OCR läuft …")
        thread = threading.Thread(target=self._run_pdf_ocr, args=(path, target_path, ocr_backend), daemon=True)
        thread.start()

    def start_upload_ocr_progress(self, message: str) -> None:
        self.upload_ocr_progress_var.set(message)
        self.upload_ocr_progress_frame.grid()
        self.upload_ocr_progress.start(12)
        self.upload_ocr_pdf_button.configure(state="disabled")
        self.open_file_openai_button.configure(state="disabled")

    def stop_upload_ocr_progress(self) -> None:
        try:
            self.upload_ocr_progress.stop()
        except Exception:
            pass
        self.upload_ocr_progress_var.set("")
        self.upload_ocr_progress_frame.grid_remove()
        self.update_openai_precheck_indicator()

    def find_pdf_ocr_backend(self) -> tuple[str, Any] | None:
        ocrmypdf_command = self.find_ocrmypdf_command()
        if ocrmypdf_command:
            return ("ocrmypdf", ocrmypdf_command)
        pymupdf_config = self.find_pymupdf_ocr_config()
        if pymupdf_config:
            return ("pymupdf", pymupdf_config)
        return None

    def find_ocrmypdf_command(self) -> list[str] | None:
        executable = shutil.which("ocrmypdf")
        if executable:
            return [executable]
        if importlib.util.find_spec("ocrmypdf") is not None:
            return [sys.executable, "-m", "ocrmypdf"]
        return None

    def find_tesseract_executable(self) -> str | None:
        executable = shutil.which("tesseract")
        if executable:
            return executable
        candidates = [
            Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
            Path("C:/Program Files/PDF24/tesseract/tesseract.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def local_tessdata_dir(self) -> Path | None:
        candidates = [
            Path(__file__).resolve().parent / "tessdata",
            Path(__file__).resolve().parent.parent / "app" / "tessdata",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return None

    def find_pymupdf_ocr_config(self) -> dict[str, str] | None:
        if importlib.util.find_spec("fitz") is None:
            return None
        tesseract = self.find_tesseract_executable()
        if not tesseract:
            return None
        tessdata = self.local_tessdata_dir()
        language = "eng"
        tessdata_text = ""
        if tessdata and (tessdata / "deu.traineddata").exists():
            language = "deu"
            tessdata_text = str(tessdata)
        return {"tesseract": tesseract, "language": language, "tessdata": tessdata_text}

    def _run_pdf_ocr(self, source: Path, target: Path, ocr_backend: tuple[str, Any]) -> None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            backend_name, backend_config = ocr_backend
            if backend_name == "pymupdf":
                self._run_pdf_ocr_with_pymupdf(source, target, backend_config)
            else:
                self._run_pdf_ocr_with_ocrmypdf(source, target, backend_config)
            self.after(0, self.stop_upload_ocr_progress)
            self.after(0, lambda: self.link_upload_ocr_pdf(target))
            self.after(0, lambda: self.upload_openai_text_var.set("PDF OCR fertig - OCR-PDF verknüpft"))
            self.after(0, lambda: messagebox.showinfo("PDF OCR", f"Durchsuchbares PDF wurde erstellt und verknüpft:\n{target}\n\nDas Original bleibt für den Upload ausgewählt. OpenAI nutzt die OCR-Fassung."))
        except Exception as exc:
            app_log_exception("PDF OCR konnte nicht ausgeführt werden", exc, source=str(source), target=str(target))
            error_message = str(exc)
            self.after(0, self.stop_upload_ocr_progress)
            self.after(0, lambda: self.upload_openai_text_var.set("PDF OCR fehlgeschlagen"))
            self.after(0, lambda: messagebox.showerror("PDF OCR", f"OCR konnte nicht ausgeführt werden:\n{error_message}"))

    def _run_pdf_ocr_with_ocrmypdf(self, source: Path, target: Path, ocrmypdf_command: list[str]) -> None:
            cmd = ocrmypdf_command + [
                "--skip-text",
                "--language",
                "deu+eng",
                str(source),
                str(target),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                message = (result.stderr or result.stdout or "OCR konnte nicht abgeschlossen werden.").strip()
                raise RuntimeError(message[:1200])

    def _run_pdf_ocr_with_pymupdf(self, source: Path, target: Path, config: dict[str, str]) -> None:
        import fitz

        tesseract = config.get("tesseract", "")
        if tesseract:
            tesseract_dir = str(Path(tesseract).parent)
            path_parts = os.environ.get("PATH", "").split(os.pathsep)
            if tesseract_dir not in path_parts:
                os.environ["PATH"] = tesseract_dir + os.pathsep + os.environ.get("PATH", "")

        tessdata = config.get("tessdata", "")
        if tessdata:
            os.environ["TESSDATA_PREFIX"] = tessdata
        language = config.get("language") or "eng"

        src = fitz.open(str(source))
        out = fitz.open()
        try:
            for page in src:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                pdf_bytes = pix.pdfocr_tobytes(compress=True, language=language, tessdata=tessdata or None)
                page_doc = fitz.open("pdf", pdf_bytes)
                try:
                    out.insert_pdf(page_doc)
                finally:
                    page_doc.close()
            out.save(str(target), garbage=4, deflate=True)
        finally:
            out.close()
            src.close()

    def openai_metadata_cache_path(self) -> Path:
        return _utauc_openai_metadata_cache_path(APP_DIR)

    def load_openai_metadata_cache(self) -> dict[str, Any]:
        return _utauc_load_openai_metadata_cache(self.openai_metadata_cache_path())

    def save_openai_metadata_cache(self, data: dict[str, Any]) -> None:
        _utauc_save_openai_metadata_cache(self.openai_metadata_cache_path(), data)

    def openai_metadata_cache_key(self, analysis_file: Path | None = None) -> str | None:
        return _utauc_openai_metadata_cache_key(self.selected_file, analysis_file)

    def cached_openai_metadata_for_current_file(self) -> dict[str, Any] | None:
        analysis_file = self.current_upload_ocr_pdf_path() or self.selected_file
        key = self.openai_metadata_cache_key(analysis_file)
        return _utauc_cached_openai_metadata_for_key(self.load_openai_metadata_cache(), key)

    def store_openai_metadata_cache(self, analysis_file: Path | None, metadata: dict[str, Any], usage: dict[str, Any] | None, model: str) -> None:
        key = self.openai_metadata_cache_key(analysis_file)
        data = _utauc_add_openai_metadata_cache_entry(
            self.load_openai_metadata_cache(),
            key,
            self.selected_file,
            analysis_file,
            metadata,
            usage,
            model,
            datetime.now().isoformat(timespec="seconds"),
        )
        self.save_openai_metadata_cache(data)

    def apply_cached_openai_metadata_if_available(self, model_name: str | None = None) -> bool:
        cached = self.cached_openai_metadata_for_current_file()
        if not cached:
            return False
        cached_model = str(cached.get("model") or "").strip()
        if model_name and cached_model and model_name != cached_model:
            return False
        metadata = cached.get("metadata") if isinstance(cached.get("metadata"), dict) else {}
        self.openai_metadata_suggestions = {k: v for k, v in metadata.items() if str(v or "").strip()}
        self.openai_metadata_source_model = str(cached.get("model") or "OpenAI").strip() or "OpenAI"
        self.upload_openai_metadata_button.configure(state="normal" if self.openai_metadata_suggestions else "disabled")
        self.upload_openai_usage_var.set("Verbrauch: 0 Tokens (Cache)")
        if self.openai_metadata_suggestions:
            self.upload_openai_text_var.set("OpenAI: Metadatenvorschläge aus lokalem Cache verfügbar")
            self.after(0, self.show_upload_openai_apply_dialog_if_available)
            return True
        return False

    def queue_openai_check(self, auto_apply: bool = False, allow_yellow: bool = False) -> None:
        self.openai_metadata_suggestions = {}
        self.upload_openai_metadata_button.configure(state="disabled")
        color, precheck_text = self.update_openai_precheck_indicator()
        if color == "red":
            self.upload_openai_text_var.set("OpenAI: durch Ampel gesperrt")
            self.upload_openai_usage_var.set("Verbrauch: k.A.")
            if not auto_apply:
                messagebox.showwarning("OpenAI-Ampel", precheck_text)
            return
        if color == "yellow" and not allow_yellow:
            if not messagebox.askyesno("OpenAI-Ampel", f"{precheck_text}\n\nTrotzdem mit OpenAI prüfen?"):
                self.upload_openai_text_var.set("OpenAI: Prüfung durch Benutzer abgebrochen")
                self.upload_openai_usage_var.set("Verbrauch: k.A.")
                return
        if not self.selected_file:
            self.upload_openai_text_var.set("OpenAI: keine Einzeldatei ausgewählt")
            self.upload_openai_usage_var.set("Verbrauch: k.A.")
            return

        cached = self.cached_openai_metadata_for_current_file()
        cached_model = str(cached.get("model") or "").strip() if isinstance(cached, dict) else ""
        selected_model = ""
        if self.is_current_admin() and not auto_apply:
            selected_model = self.choose_upload_openai_model(cached_model)
            if not selected_model:
                self.upload_openai_text_var.set("OpenAI: Prüfung durch Benutzer abgebrochen")
                self.upload_openai_usage_var.set("Verbrauch: k.A.")
                return
            if cached_model and selected_model == cached_model and self.apply_cached_openai_metadata_if_available(selected_model):
                self.update_upload_status_indicator()
                return
        elif cached_model and self.apply_cached_openai_metadata_if_available():
            self.update_upload_status_indicator()
            return

        if not self.openai_available():
            self.upload_openai_text_var.set("OpenAI: nicht konfiguriert")
            self.upload_openai_usage_var.set("Verbrauch: k.A.")
            return
        self.upload_openai_text_var.set("OpenAI prüft …")
        self.upload_openai_usage_var.set("Verbrauch: k.A.")
        thread = threading.Thread(target=self._run_openai_check, args=(auto_apply, selected_model), daemon=True)
        thread.start()

    def _run_openai_check(self, auto_apply: bool = False, model: str | None = None) -> None:
        if not self.openai_available() or not self.selected_file:
            return
        client = self.openai_client(model)
        if client is None:
            return
        self.openai_metadata_source_model = client.model
        analysis_file = self.current_upload_ocr_pdf_path() or self.selected_file
        filename = self.selected_file.name if self.selected_file else ""
        extension = self.selected_file.suffix.lower() if self.selected_file else ""
        sample = self.extract_upload_text_sample(
            analysis_file,
            max_chars=self.openai_text_sample_chars(),
            max_pdf_pages=self.openai_pdf_sample_pages(),
        ) if analysis_file else None
        local_metadata = self.derive_metadata_from_text(filename=filename, extension=extension, sample=sample)
        try:
            result = client.analyze_upload_file(filename=filename, extension=extension, sample=sample)
            metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            metadata_keywords = _utm_limit_openai_keywords(
                str(metadata.get("keywords", "")),
                reference_text=sample,
                max_keywords=30,
            )
            if metadata_keywords:
                metadata["keywords"] = metadata_keywords
            else:
                metadata.pop("keywords", None)
            file_type = str(result.get("file_type") or "unbekannt").strip()
            confidence = str(result.get("confidence") or "").strip()
            advice = str(result.get("advice") or "").strip()
            merged_metadata = dict(local_metadata)
            for k, v in metadata.items():
                if str(v or "").strip():
                    merged_metadata[k] = v
            useful_metadata = {k: v for k, v in merged_metadata.items() if str(v or "").strip()}
            self.openai_metadata_suggestions = useful_metadata

            label = f"OpenAI: {file_type}"
            if confidence:
                label += f" ({confidence})"
            if advice:
                label += f" – {advice}"
            if useful_metadata:
                label += " – Metadatenvorschläge bereit"
            else:
                label += " – keine übernehmbaren Metadaten gefunden"

            usage_text = self.format_openai_usage(result.get("usage", {}), model_name=client.model)
            self.store_openai_metadata_cache(analysis_file, useful_metadata, result.get("usage", {}), client.model)
            metadata_button_state = "normal" if useful_metadata else "disabled"
            self.after(0, lambda: self.upload_openai_text_var.set(label))
            self.after(0, lambda: self.upload_openai_usage_var.set(usage_text))
            self.after(0, lambda: self.upload_openai_metadata_button.configure(state=metadata_button_state))
            self.after(0, self.show_upload_openai_apply_dialog_if_available)
            self.after(0, self.update_upload_status_indicator)
        except OpenAIError as exc:
            self.openai_metadata_suggestions = {}
            self.after(0, lambda: self.upload_openai_text_var.set(f"OpenAI: {exc.user_message()}"))
            self.after(0, lambda: self.upload_openai_metadata_button.configure(state="disabled"))
            self.after(0, lambda: self.upload_openai_usage_var.set("Verbrauch: k.A."))
        except Exception:
            self.openai_metadata_suggestions = {}
            self.after(0, lambda: self.upload_openai_text_var.set("OpenAI-Fehler"))
            self.after(0, lambda: self.upload_openai_metadata_button.configure(state="disabled"))
            self.after(0, lambda: self.upload_openai_usage_var.set("Verbrauch: k.A."))

    def on_apply_openai_metadata(self) -> None:
        if not self.openai_metadata_suggestions:
            self.upload_openai_text_var.set("OpenAI: keine Metadatenvorschläge verfügbar – zuerst „OpenAI prüfen“ drücken")
            self.upload_openai_metadata_button.configure(state="disabled")
            return
        changed = self.show_upload_openai_apply_dialog(self.openai_metadata_suggestions)
        if changed is None:
            self.upload_openai_text_var.set("OpenAI: Übernahme abgebrochen")
            return
        if changed:
            current_fields = list(self.openai_metadata_applied_fields or [])
            for field in changed:
                if field not in current_fields:
                    current_fields.append(field)
            self.openai_metadata_applied_fields = current_fields
            self.upload_openai_text_var.set(f"OpenAI: Metadaten übernommen ({', '.join(changed)})")
            self.update_upload_status_indicator()
        else:
            self.upload_openai_text_var.set("OpenAI: Keine neuen Metadaten übernommen")

    def current_upload_openai_field_value(self, key: str) -> str:
        if key == "description":
            return self.description_text.get("1.0", "end").strip()
        var = self.meta_vars.get(key)
        return str(var.get() or "").strip() if var is not None else ""

    def set_upload_openai_field_value(self, key: str, value: str) -> None:
        value = self.normalize_description_text(value) if key == "description" else str(value or "").strip()
        if key == "description":
            self.description_text.delete("1.0", "end")
            self.description_text.insert("1.0", value)
            return
        var = self.meta_vars.get(key)
        if var is not None:
            var.set(value)

    def show_upload_openai_apply_dialog(self, suggestions: dict[str, Any]) -> list[str] | None:
        excluded_fields = {"file_type", "confidence", "advice", "usage"}
        rows: list[tuple[str, str, str]] = []
        for key, raw_value in suggestions.items():
            if key in excluded_fields:
                continue
            suggestion = str(raw_value or "").strip()
            if not suggestion:
                continue
            if key == "description":
                current = self.current_upload_openai_field_value("description")
            elif key in self.meta_vars:
                current = self.current_upload_openai_field_value(key)
            else:
                continue
            rows.append((key, current, suggestion))

        if not rows:
            return []

        dialog = tk.Toplevel(self)
        dialog.title("OpenAI-Metadaten übernehmen")
        dialog.transient(self)
        dialog.geometry("1180x680")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(
            dialog,
            text="Wählen Sie je Feld eine Aktion. Keine Auswahl bedeutet: Vorschlag ignorieren.",
            wraplength=920,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        canvas = tk.Canvas(dialog, highlightthickness=0)
        scroll = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=4)
        scroll.grid(row=1, column=1, sticky="ns", pady=4)

        headers = ["Feld", "Aktueller Wert", "OpenAI-Vorschlag", "übernehmen", "überschreiben", "anfügen"]
        widths = [18, 30, 34, 12, 14, 10]
        for col, (header, width) in enumerate(zip(headers, widths)):
            ttk.Label(inner, text=header, font=("", 9, "bold"), width=width).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 6))

        action_vars: dict[str, dict[str, tk.BooleanVar]] = {}
        for row_index, (key, current, suggestion) in enumerate(rows, start=1):
            row_vars = {
                "take": tk.BooleanVar(value=not bool(str(current or "").strip())),
                "replace": tk.BooleanVar(value=False),
                "append": tk.BooleanVar(value=False),
            }
            action_vars[key] = row_vars
            row_height = max(self._openai_display_height(current), self._openai_display_height(suggestion))
            ttk.Label(inner, text=self.admin_openai_field_label(key), width=18).grid(row=row_index, column=0, sticky="nw", padx=4, pady=3)
            self._readonly_text_widget(inner, current or "-", width=34, height=row_height, background_source=dialog).grid(row=row_index, column=1, sticky="nw", padx=4, pady=3)
            self._readonly_text_widget(inner, suggestion, width=56, height=row_height, background_source=dialog).grid(row=row_index, column=2, sticky="nw", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["take"], command=lambda vars=row_vars: self._choose_openai_action(vars, "take")).grid(row=row_index, column=3, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["replace"], command=lambda vars=row_vars: self._choose_openai_action(vars, "replace")).grid(row=row_index, column=4, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["append"], command=lambda vars=row_vars: self._choose_openai_action(vars, "append")).grid(row=row_index, column=5, sticky="n", padx=4, pady=3)

        result = {"changed": None}

        def apply_selection() -> None:
            changed_fields: list[str] = []
            for key, _current, suggestion in rows:
                action_items = [action_name for action_name, var in action_vars[key].items() if var.get()]
                action = action_items[0] if action_items else ""
                if not action:
                    continue
                current = self.current_upload_openai_field_value(key)
                new_value = self.admin_openai_value_for_action(key, current, suggestion, action)
                new_value = self.normalize_description_text(new_value) if key == "description" else str(new_value or "").strip()
                if new_value != current:
                    self.set_upload_openai_field_value(key, new_value)
                    changed_fields.append(key)
            result["changed"] = changed_fields
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 12))
        ttk.Button(buttons, text="Auswahl übernehmen", command=apply_selection).pack(side="left", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
        self.wait_window(dialog)
        return result["changed"]

    def show_upload_openai_apply_dialog_if_available(self) -> None:
        if not self.openai_metadata_suggestions:
            self.upload_openai_text_var.set("OpenAI: keine Metadatenvorschläge verfügbar")
            return
        changed = self.show_upload_openai_apply_dialog(self.openai_metadata_suggestions)
        if changed is None:
            self.upload_openai_text_var.set("OpenAI: Übernahme abgebrochen")
            return
        if changed:
            current_fields = list(self.openai_metadata_applied_fields or [])
            for field in changed:
                if field not in current_fields:
                    current_fields.append(field)
            self.openai_metadata_applied_fields = current_fields
            self.upload_openai_text_var.set(f"OpenAI: Metadaten übernommen ({', '.join(changed)})")
            self.update_upload_status_indicator()
        else:
            self.upload_openai_text_var.set("OpenAI: Keine neuen Metadaten übernommen")

    def _fetch_openai_metadata_suggestions(self) -> None:
        if not self.openai_available() or not self.selected_file:
            return
        client = self.openai_client()
        if client is None:
            return
        analysis_file = self.current_upload_ocr_pdf_path() or self.selected_file
        filename = self.selected_file.name if self.selected_file else ""
        extension = self.selected_file.suffix.lower() if self.selected_file else ""
        sample = self.extract_upload_text_sample(
            analysis_file,
            max_chars=self.openai_text_sample_chars(),
            max_pdf_pages=self.openai_pdf_sample_pages(),
        ) if analysis_file else None
        try:
            suggestions = client.suggest_metadata(filename=filename, extension=extension, sample=sample)
            suggestions["keywords"] = _utm_limit_openai_keywords(
                str(suggestions.get("keywords", "")),
                reference_text=sample,
                max_keywords=30,
            )
            self.openai_metadata_suggestions = suggestions
            self.after(0, lambda: self.upload_openai_text_var.set("OpenAI: Metadatenvorschläge bereit"))
            self.after(0, lambda: self.upload_openai_metadata_button.configure(state="normal"))
            self.after(0, lambda: self.upload_openai_usage_var.set(self.format_openai_usage(suggestions.get("usage", {}))))
        except OpenAIError as exc:
            self.after(0, lambda: self.upload_openai_text_var.set(f"OpenAI: {exc.user_message()}"))
            self.after(0, lambda: self.upload_openai_metadata_button.configure(state="disabled"))
            self.after(0, lambda: self.upload_openai_usage_var.set("Verbrauch: k.A."))
        except Exception:
            self.after(0, lambda: self.upload_openai_text_var.set("OpenAI-Fehler"))
            self.after(0, lambda: self.upload_openai_metadata_button.configure(state="disabled"))
            self.after(0, lambda: self.upload_openai_usage_var.set("Verbrauch: k.A."))

    def set_upload_status(self, color: str, text: str) -> None:
        self.upload_status_canvas.delete("all")
        self.upload_status_canvas.create_oval(1, 1, 13, 13, fill=color, outline=color)
        self.upload_status_text_var.set(text)

    def evaluate_upload_status(self) -> tuple[str, str]:
        if self.selected_folder is not None:
            return "yellow", "Ordnerupload"
        if self.selected_file is None:
            return "red", "Keine Datei"
        if not self.selected_file.exists():
            return "red", "Datei fehlt"
        detected_type = detect_document_type(self.selected_file)
        ready = self.is_upload_metadata_ready()
        if detected_type == "Sonstiges":
            return "yellow", "Dateityp unklar"
        if not ready:
            return "yellow", "Metadaten ergänzen"
        return "green", "Bereit zum Upload"

    def is_upload_metadata_ready(self) -> bool:
        for key in UPLOAD_METADATA_REQUIRED_FIELDS:
            value = self.meta_vars.get(key)
            if value is None or not str(value.get() or "").strip():
                return False
        return True

    def update_upload_status_indicator(self) -> None:
        color, text = self.evaluate_upload_status()
        self.set_upload_status(color, text)

    def update_upload_image_preview(self, path: Path | None) -> None:
        if self.upload_image_preview_label is None:
            return
        if path is None or not path.exists():
            self.upload_image_preview_label.configure(
                text="",
                image="",
            )
            self._upload_preview_photo = None
            return

        if not is_image_file(path):
            self.upload_image_preview_label.configure(
                text="",
                image="",
            )
            self._upload_preview_photo = None
            return

        if Image is None or ImageTk is None:
            self.upload_image_preview_label.configure(
                text="Pillow nicht installiert – Vorschau nicht verfügbar.",
                image="",
            )
            self._upload_preview_photo = None
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
            self.upload_image_preview_label.configure(image=photo, text="")
            self._upload_preview_photo = photo
        except Exception as exc:
            app_log_exception("Upload-Bildvorschau konnte nicht geladen werden", exc)
            self.upload_image_preview_label.configure(
                text="Vorschau nicht möglich.",
                image="",
            )
            self._upload_preview_photo = None

    def choose_file(self) -> None:
        filename = filedialog.askopenfilename(title="Datei auswählen")
        if filename:
            self.set_selected_upload_file(Path(filename), source="dialog")

    def clear_selected_upload_file(self) -> None:
        self.clear_upload_form(keep_target_folder=True)
        self.upload_drop_hint_var.set("Datei aus dem Explorer hierher ziehen oder über ‚Datei auswählen‘ wählen.")

    def set_selected_upload_file(self, path: Path, source: str = "dialog") -> None:
        """Übernimmt eine einzelne Datei in den Upload-Reiter.

        Wird sowohl vom klassischen Datei-Auswahldialog als auch von Drag & Drop
        genutzt. Drag & Drop startet bewusst keinen Upload, sondern wählt nur die
        Datei aus; der Benutzer muss weiterhin „Datei hochladen“ klicken.
        """
        previous_selected = self.selected_file
        path = Path(path).expanduser()
        if not path.exists() or not path.is_file():
            messagebox.showwarning("Datei auswählen", f"Die Datei wurde nicht gefunden oder ist kein Dokument:\n{path}")
            return
        source_sha256 = self.compute_source_sha256(path)
        if source_sha256 and not self.confirm_upload_for_duplicate(path, source_sha256):
            self.clear_upload_form(keep_target_folder=True)
            self.upload_drop_hint_var.set("Auswahl abgebrochen: Datei wurde bereits in ODV hochgeladen (wurde nicht übernommen).")
            messagebox.showinfo(
                "Duplikatprüfung",
                "Die Datei wurde bereits in ODV erkannt.\n\n"
                "Der Upload wurde abgebrochen. Bitte eine andere Datei wählen oder im Warnungsdialog \"Trotzdem hochladen\" entscheiden.",
            )
            return
        self._selected_upload_duplicate_checked = True
        self.reset_upload_metadata_for_new_file()
        self.selected_file = path
        self.selected_folder = None
        self._selected_upload_source_file = path
        self._selected_upload_source_sha256 = source_sha256
        if source != "keep_ocr_link":
            self.upload_ocr_pdf_path = None
        self.file_var.set(self.normalize_local_path_text(path))
        self.update_upload_image_preview(path)
        self.update_upload_technical_fields(selected_file=path)
        detected_type = detect_document_type(self.selected_file)
        self.meta_vars["document_type"].set(detected_type)
        self.remember_document_type(detected_type)
        if not self.meta_vars.get("place").get().strip():
            self.meta_vars["place"].set(self.place_var.get().strip())
        self.apply_image_metadata_suggestions(path)
        self.apply_filename_keyword_suggestions(path)
        self.refresh_planned_upload_filename(path)
        self.refresh_upload_metadata_option_comboboxes()
        self.persons = []
        self.person_status_var.set("none")
        self.person_summary_var.set("Keine Personen markiert.")
        self.upload_drop_hint_var.set(f"Ausgewählte Datei: {path.name}")
        self.update_upload_status_indicator()
        self.reset_openai_status("OpenAI: nicht geprüft – Button „OpenAI prüfen“ drücken")
        color, _text = self.update_openai_precheck_indicator()
        ocr_path = self.current_upload_ocr_pdf_path()
        if ocr_path:
            self.upload_drop_hint_var.set(f"Ausgewählte Datei: {path.name} | OCR: {ocr_path.name}")
        self.clear_pdf_text_searchability_cache(previous_selected)
        if color == "green":
            self.after(150, lambda: self.queue_openai_check(auto_apply=True, allow_yellow=True))
        app_log("info", "Upload-Datei ausgewählt", path=str(path), source=source)

    def reset_upload_metadata_for_new_file(self) -> None:
        """Leert fachliche Upload-Metadaten beim Wechsel auf ein neues Dokument."""
        self._upload_filename_auto_value = ""
        keep_empty_or_system = {"upload_id", "status", "current_filename", "uploaded_at", "uploaded_by"}
        for key, var in self.meta_vars.items():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            elif key in keep_empty_or_system:
                var.set("")
            elif key == "place":
                var.set(self.place_var.get().strip())
            else:
                var.set("")
        self.description_text.delete("1.0", "end")
        self.note_text.delete("1.0", "end")
        self.update_description_counter(self.description_text, self.upload_description_counter_var)
        self.persons = []
        self.person_status_var.set("none")
        self.person_summary_var.set("Keine Personen markiert.")

    def link_upload_ocr_pdf(self, path: Path) -> None:
        path = Path(path).expanduser()
        if not path.exists() or not path.is_file():
            messagebox.showwarning("PDF OCR", f"Das OCR-PDF wurde nicht gefunden:\n{path}")
            return
        self.upload_ocr_pdf_path = path
        self.clear_pdf_text_searchability_cache(self.selected_file)
        if self.selected_file:
            self.upload_drop_hint_var.set(f"Ausgewählte Datei: {self.selected_file.name} | OCR: {path.name}")
        self.update_openai_precheck_indicator()
        self.after(150, lambda: self.queue_openai_check(auto_apply=True, allow_yellow=True))

    def parse_dropped_files(self, data: str) -> list[Path]:
        """Parst Dateipfade aus tkinterdnd2-Dropdaten, auch mit Leerzeichen."""
        if not data:
            return []
        try:
            parts = self.tk.splitlist(data)
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

    def handle_upload_file_drop(self, event) -> str:
        dropped_data = ""
        try:
            dropped_data = event.data
        except Exception:
            dropped_data = ""
        paths = [p for p in self.parse_dropped_files(dropped_data) if p.exists()]
        files = [p for p in paths if p.is_file()]
        folders = [p for p in paths if p.is_dir()]
        if files:
            if len(files) > 1:
                messagebox.showinfo("Drag & Drop", "Es wurde mehr als eine Datei gezogen. Für diesen Upload wird die erste Datei übernommen.")
            self.set_selected_upload_file(files[0], source="drag_drop")
        elif folders:
            messagebox.showinfo("Drag & Drop", "Bitte für Drag & Drop eine einzelne Datei ablegen. Ordner bitte weiterhin über „Ordner auswählen“ wählen.")
        else:
            messagebox.showwarning("Drag & Drop", "Es konnte keine gültige Datei übernommen werden.")
        return "break"

    def enable_upload_drag_and_drop(self, *widgets: tk.Widget) -> None:
        """Aktiviert Drag & Drop im Upload-Reiter, sofern tkinterdnd2 verfügbar ist."""
        if DND_FILES is None:
            self.upload_drop_hint_var.set("Drag & Drop ist in diesem Build nicht verfügbar. Bitte „Datei auswählen“ verwenden.")
            return
        for widget in widgets + (self.upload_file_entry, self.upload_drop_hint, self.upload_tab):
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self.handle_upload_file_drop)
            except Exception as exc:
                app_log_exception("Drag & Drop konnte für Upload-Widget nicht aktiviert werden", exc)

    def choose_upload_folder(self) -> None:
        folder = filedialog.askdirectory(title="Ordner mit Dateien auswählen")
        if folder:
            self.selected_folder = Path(folder)
            self.selected_file = None
            self.file_var.set(self.normalize_local_path_text(folder))
            self.update_upload_image_preview(None)
            self.meta_vars["document_type"].set("Mehrere Dateien")
            self.remember_document_type("Mehrere Dateien")
            if not self.meta_vars.get("place").get().strip():
                self.meta_vars["place"].set(self.place_var.get().strip())
            self.persons = []
            self.person_status_var.set("none")
            self.person_summary_var.set("Ordnerupload: Personenmarkierung je Datei nicht aktiv.")
            self.update_upload_status_indicator()
            self.reset_openai_status()

    def open_person_tagger(self) -> None:
        if not self.selected_file:
            messagebox.showwarning("Keine Datei", "Bitte zuerst eine Bilddatei auswählen.")
            return
        if not is_image_file(self.selected_file):
            messagebox.showwarning("Keine Bilddatei", "Personenmarkierung ist im MVP nur für Bilddateien vorgesehen.")
            return
        tagger = PersonTagger(self, self.selected_file)
        result = tagger.show_modal()
        if result is not None:
            self.persons = result
            self.person_status_var.set("identified" if self.persons else "none")
            self.person_summary_var.set(f"{len(self.persons)} Personen markiert.")
