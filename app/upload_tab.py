from __future__ import annotations

from pathlib import Path
import importlib.util
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import urllib.parse
import os
from typing import Any

try:
    from tkinterdnd2 import DND_FILES
except Exception:
    DND_FILES = None

from .app_logging import app_log
from .config import (
    OPENAI_PDF_SAMPLE_PAGES,
    OPENAI_TEXT_SAMPLE_CHARS,
)
from .file_service import make_normalized_archive_filename, unique_path_with_counter
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
from .upload_file_selection_utils import (
    choose_file as _ufs_choose_file,
    clear_selected_upload_file as _ufs_clear_selected_upload_file,
    _commit_selected_upload_file_text as _ufs_commit_selected_upload_file_text,
    _finalize_selected_upload_file as _ufs_finalize_selected_upload_file,
    _load_selected_upload_file_async as _ufs_load_selected_upload_file_async,
    _set_upload_file_loading_text as _ufs_set_upload_file_loading_text,
    _start_upload_file_loading_indicator as _ufs_start_upload_file_loading_indicator,
    _tick_upload_file_loading_indicator as _ufs_tick_upload_file_loading_indicator,
    _stop_upload_file_loading_indicator as _ufs_stop_upload_file_loading_indicator,
    choose_upload_folder as _ufs_choose_upload_folder,
    enable_upload_drag_and_drop as _ufs_enable_upload_drag_and_drop,
    handle_upload_file_drop as _ufs_handle_upload_file_drop,
    link_upload_ocr_pdf as _ufs_link_upload_ocr_pdf,
    parse_dropped_files as _ufs_parse_dropped_files,
    reset_upload_metadata_for_new_file as _ufs_reset_upload_metadata_for_new_file,
    set_selected_upload_file as _ufs_set_selected_upload_file,
)
from .upload_ocr_utils import (
    create_searchable_pdf_for_upload as _uoc_create_searchable_pdf_for_upload,
    find_pdf_ocr_backend as _uoc_find_pdf_ocr_backend,
    find_ocrmypdf_command as _uoc_find_ocrmypdf_command,
    find_pymupdf_ocr_config as _uoc_find_pymupdf_ocr_config,
    find_tesseract_executable as _uoc_find_tesseract_executable,
    local_tessdata_dir as _uoc_local_tessdata_dir,
    start_upload_ocr_progress as _uoc_start_upload_ocr_progress,
    stop_upload_ocr_progress as _uoc_stop_upload_ocr_progress,
    _run_pdf_ocr as _uoc_run_pdf_ocr,
    _run_pdf_ocr_with_ocrmypdf as _uoc_run_pdf_ocr_with_ocrmypdf,
    _run_pdf_ocr_with_pymupdf as _uoc_run_pdf_ocr_with_pymupdf,
)
from .upload_openai_cache_utils import (
    apply_cached_openai_metadata_if_available as _uocac_apply_cached_openai_metadata_if_available,
    cached_openai_metadata_for_current_file as _uocac_cached_openai_metadata_for_current_file,
    load_openai_metadata_cache as _uocac_load_openai_metadata_cache,
    openai_metadata_cache_key as _uocac_openai_metadata_cache_key,
    openai_metadata_cache_path as _uocac_openai_metadata_cache_path,
    save_openai_metadata_cache as _uocac_save_openai_metadata_cache,
    store_openai_metadata_cache as _uocac_store_openai_metadata_cache,
)
from .upload_openai_utils import (
    _fetch_openai_metadata_suggestions as _uoo_fetch_openai_metadata_suggestions,
    _openai_privacy_blockers as _uoo_openai_privacy_blockers,
    _run_openai_check as _uoo_run_openai_check,
    choose_upload_openai_model as _uoo_choose_upload_openai_model,
    current_upload_openai_field_value as _uoo_current_upload_openai_field_value,
    evaluate_openai_precheck as _uoo_evaluate_openai_precheck,
    on_apply_openai_metadata as _uoo_on_apply_openai_metadata,
    openai_available as _uoo_openai_available,
    openai_client as _uoo_openai_client,
    queue_openai_check as _uoo_queue_openai_check,
    reset_openai_status as _uoo_reset_openai_status,
    set_openai_precheck_status as _uoo_set_openai_precheck_status,
    set_upload_openai_field_value as _uoo_set_upload_openai_field_value,
    show_upload_openai_apply_dialog as _uoo_show_upload_openai_apply_dialog,
    show_upload_openai_apply_dialog_if_available as _uoo_show_upload_openai_apply_dialog_if_available,
    update_openai_precheck_indicator as _uoo_update_openai_precheck_indicator,
    upload_openai_model_choices as _uoo_upload_openai_model_choices,
)
from .upload_text_utils import (
    append_openai_description as _utx_append_openai_description,
    derive_metadata_from_text as _utx_derive_metadata_from_text,
    extract_upload_text_sample as _utx_extract_upload_text_sample,
    local_places_from_text as _utx_local_places_from_text,
    merge_metadata_values as _utx_merge_metadata_values,
    merge_place_values as _utx_merge_place_values,
    normalize_upload_text_sample as _utx_normalize_upload_text_sample,
    _extract_excel_text as _utx_extract_excel_text,
)
from .upload_status_utils import (
    evaluate_upload_status as _usst_evaluate_upload_status,
    is_upload_metadata_ready as _usst_is_upload_metadata_ready,
    open_person_tagger as _usst_open_person_tagger,
    set_upload_status as _usst_set_upload_status,
    update_upload_image_preview as _usst_update_upload_image_preview,
    update_upload_status_indicator as _usst_update_upload_status_indicator,
)

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
        self._upload_text_sample_cache: dict[str, str | None] = {}
        self._upload_ocr_path_cache: dict[str, Path | None] = {}
        self._upload_file_selection_token = 0
        self._upload_file_loading_active = False
        self._upload_file_loading_job = None
        self._upload_file_loading_dot_count = 0

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
        self.open_selected_upload_file_button = ttk.Button(
            file_button_frame,
            text="Dokument öffnen",
            command=self.open_selected_upload_file,
            width=file_select_button_width,
            state="disabled",
        )
        self.open_selected_upload_file_button.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
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
        self.upload_openai_precheck_var = tk.StringVar(value="OpenAI-Prüfung: keine Datei")
        self.upload_openai_precheck_label = ttk.Label(
            status_container,
            textvariable=self.upload_openai_precheck_var,
            foreground="#555555",
            wraplength=760,
        )
        self.upload_openai_precheck_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=(0, 0), pady=(4, 0))

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
        return _uoo_openai_available(self)

    def _openai_privacy_blockers(self) -> dict[str, bool]:
        return _uoo_openai_privacy_blockers(self)

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
        return _uoo_openai_client(self, model_name)

    def upload_openai_model_choices(self, cached_model: str | None = None) -> list[str]:
        return _uoo_upload_openai_model_choices(self, cached_model)

    def choose_upload_openai_model(self, cached_model: str | None = None) -> str:
        return _uoo_choose_upload_openai_model(self, cached_model)

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

    def _upload_path_cache_key(self, path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            expanded = Path(path).expanduser()
            stat = expanded.stat()
        except Exception:
            return None
        return f"{expanded.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"

    def clear_upload_text_sample_cache(self, path: Path | None = None) -> None:
        cache = getattr(self, "_upload_text_sample_cache", None)
        if cache is None:
            self._upload_text_sample_cache = {}
            return
        if path is None:
            self._upload_text_sample_cache = {}
            return
        prefix = str(Path(path).expanduser())
        for key in [key for key in cache if key.startswith(prefix)]:
            cache.pop(key, None)

    def clear_upload_ocr_path_cache(self, path: Path | None = None) -> None:
        cache = getattr(self, "_upload_ocr_path_cache", None)
        if cache is None:
            self._upload_ocr_path_cache = {}
            return
        if path is None:
            self._upload_ocr_path_cache = {}
            return
        prefix = str(Path(path).expanduser())
        for key in [key for key in cache if key.startswith(prefix)]:
            cache.pop(key, None)

    def refresh_upload_ai_controls_visibility(self) -> None:
        show_ai = self.is_upload_text_or_pdf_document()
        widgets = [
            self.open_file_openai_button,
            self.upload_status_container,
        ]
        for widget in widgets:
            widget.grid() if show_ai else widget.grid_remove()
        self.upload_openai_metadata_button.grid_remove()

        show_ocr_create = self.is_upload_image_pdf() and not self.current_upload_ocr_pdf_path()
        show_ocr_open = self.is_upload_image_pdf() and bool(self.current_upload_ocr_pdf_path())
        self.upload_ocr_pdf_button.grid() if show_ocr_create else self.upload_ocr_pdf_button.grid_remove()
        self.upload_show_ocr_pdf_button.grid() if show_ocr_open else self.upload_show_ocr_pdf_button.grid_remove()
        self.open_selected_upload_file_button.configure(state=("normal" if self.selected_file else "disabled"))

    def clear_upload_form(self, keep_target_folder: bool = True) -> None:
        self._upload_file_selection_token += 1
        self._stop_upload_file_loading_indicator()
        selected_target = self.target_folder_var.get()
        self.clear_pdf_text_searchability_cache(self.selected_file)
        self.clear_upload_text_sample_cache()
        self.clear_upload_ocr_path_cache()
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
        _uoo_reset_openai_status(self, message)

    def _clean_openai_label_text(self, text: str) -> str:
        text = (text or "").strip()
        if text.lower().startswith("openai:"):
            text = text[7:].strip()
        return text

    def _needs_manual_metadata_hint(self, color: str, text: str) -> bool:
        if color != "red":
            return False
        lowered = (text or "").lower()
        if not lowered:
            return False
        return (
            "mögliche" in lowered
            and "erkannt" in lowered
            and "nicht an openai senden" in lowered
        ) or "technische/archivdatei" in lowered

    def set_openai_precheck_status(self, color: str, text: str) -> None:
        _uoo_set_openai_precheck_status(self, color, text)

    def update_openai_precheck_indicator(self) -> tuple[str, str]:
        return _uoo_update_openai_precheck_indicator(self)

    def evaluate_openai_precheck(self) -> tuple[str, str]:
        return _uoo_evaluate_openai_precheck(self)

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
        cache_key = self._upload_path_cache_key(selected)
        cache = getattr(self, "_upload_ocr_path_cache", None)
        if cache_key is not None and cache is not None and cache_key in cache:
            cached = cache[cache_key]
            if cached is None:
                return None
            if cached.exists() and cached.is_file():
                return cached
        exact = selected.with_name(f"{selected.stem}_ocr.pdf")
        if exact.exists() and exact.is_file():
            if cache_key is not None and cache is not None:
                cache[cache_key] = exact
            return exact
        candidates = [
            candidate for candidate in selected.parent.glob(f"{selected.stem}_ocr_#*.pdf")
            if candidate.is_file()
        ]
        if not candidates:
            if cache_key is not None and cache is not None:
                cache[cache_key] = None
            return None
        inferred = max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)
        if cache_key is not None and cache is not None:
            cache[cache_key] = inferred
        return inferred

    def open_upload_ocr_pdf(self) -> None:
        path = self.current_upload_ocr_pdf_path()
        if not path:
            messagebox.showwarning("OCR anzeigen", "Zu dieser Datei ist noch kein OCR-PDF verknüpft.")
            return
        self.open_file_with_default_app(path)

    def open_selected_upload_file(self) -> None:
        if self.selected_folder is not None:
            messagebox.showwarning("Dokument öffnen", "Es ist ein Ordner für den Upload ausgewählt.")
            return
        if not self.selected_file:
            messagebox.showwarning("Dokument öffnen", "Bitte zuerst eine Datei auswählen.")
            return
        if not self.selected_file.exists():
            messagebox.showwarning("Dokument öffnen", f"Die Datei ist nicht mehr vorhanden:\n{self.selected_file}")
            return
        self.open_file_with_default_app(self.selected_file)

    def extract_upload_text_sample(self, path: Path | None, max_chars: int = 4000, max_pdf_pages: int = OPENAI_PDF_SAMPLE_PAGES) -> str | None:
        return _utx_extract_upload_text_sample(self, path, max_chars=max_chars, max_pdf_pages=max_pdf_pages)

    def _extract_excel_text(self, path: Path) -> str | None:
        return _utx_extract_excel_text(self, path)

    def normalize_upload_text_sample(self, text: str | None, max_chars: int = 4000) -> str | None:
        return _utx_normalize_upload_text_sample(text, max_chars=max_chars)

    def local_places_from_text(self, text: str | None) -> list[str]:
        return _utx_local_places_from_text(text)

    def merge_place_values(self, current: str, suggested: str) -> str:
        return _utx_merge_place_values(current, suggested)

    def merge_metadata_values(self, current: str, suggested: str, separator: str = ", ") -> str:
        return _utx_merge_metadata_values(current, suggested, separator=separator)

    def append_openai_description(self, current: str, suggested: str) -> str:
        return _utx_append_openai_description(self, current, suggested)

    def derive_metadata_from_text(self, filename: str, extension: str, sample: str | None) -> dict[str, str]:
        return _utx_derive_metadata_from_text(self, filename, extension, sample)

    def create_searchable_pdf_for_upload(self) -> None:
        _uoc_create_searchable_pdf_for_upload(self)

    def start_upload_ocr_progress(self, message: str) -> None:
        _uoc_start_upload_ocr_progress(self, message)

    def stop_upload_ocr_progress(self) -> None:
        _uoc_stop_upload_ocr_progress(self)

    def find_pdf_ocr_backend(self) -> tuple[str, Any] | None:
        return _uoc_find_pdf_ocr_backend(self)

    def find_ocrmypdf_command(self) -> list[str] | None:
        return _uoc_find_ocrmypdf_command()

    def find_tesseract_executable(self) -> str | None:
        return _uoc_find_tesseract_executable()

    def local_tessdata_dir(self) -> Path | None:
        return _uoc_local_tessdata_dir()

    def find_pymupdf_ocr_config(self) -> dict[str, str] | None:
        return _uoc_find_pymupdf_ocr_config(self)

    def _run_pdf_ocr(self, source: Path, target: Path, ocr_backend: tuple[str, Any]) -> None:
        _uoc_run_pdf_ocr(self, source, target, ocr_backend)

    def _run_pdf_ocr_with_ocrmypdf(self, source: Path, target: Path, ocrmypdf_command: list[str]) -> None:
        _uoc_run_pdf_ocr_with_ocrmypdf(source, target, ocrmypdf_command)

    def _run_pdf_ocr_with_pymupdf(self, source: Path, target: Path, config: dict[str, str]) -> None:
        _uoc_run_pdf_ocr_with_pymupdf(self, source, target, config)

    def openai_metadata_cache_path(self) -> Path:
        return _uocac_openai_metadata_cache_path(self)

    def load_openai_metadata_cache(self) -> dict[str, Any]:
        return _uocac_load_openai_metadata_cache(self)

    def save_openai_metadata_cache(self, data: dict[str, Any]) -> None:
        _uocac_save_openai_metadata_cache(self, data)

    def openai_metadata_cache_key(self, analysis_file: Path | None = None) -> str | None:
        return _uocac_openai_metadata_cache_key(self, analysis_file)

    def cached_openai_metadata_for_current_file(self) -> dict[str, Any] | None:
        return _uocac_cached_openai_metadata_for_current_file(self)

    def store_openai_metadata_cache(self, analysis_file: Path | None, metadata: dict[str, Any], usage: dict[str, Any] | None, model: str) -> None:
        _uocac_store_openai_metadata_cache(self, analysis_file, metadata, usage, model)

    def apply_cached_openai_metadata_if_available(self, model_name: str | None = None) -> bool:
        return _uocac_apply_cached_openai_metadata_if_available(self, model_name)

    def queue_openai_check(self, auto_apply: bool = False, allow_yellow: bool = False) -> None:
        _uoo_queue_openai_check(self, auto_apply=auto_apply, allow_yellow=allow_yellow)

    def _run_openai_check(self, auto_apply: bool = False, model: str | None = None) -> None:
        _uoo_run_openai_check(self, auto_apply=auto_apply, model=model)

    def on_apply_openai_metadata(self) -> None:
        _uoo_on_apply_openai_metadata(self)

    def current_upload_openai_field_value(self, key: str) -> str:
        return _uoo_current_upload_openai_field_value(self, key)

    def set_upload_openai_field_value(self, key: str, value: str) -> None:
        _uoo_set_upload_openai_field_value(self, key, value)

    def show_upload_openai_apply_dialog(self, suggestions: dict[str, Any]) -> list[str] | None:
        return _uoo_show_upload_openai_apply_dialog(self, suggestions)

    def show_upload_openai_apply_dialog_if_available(self) -> None:
        _uoo_show_upload_openai_apply_dialog_if_available(self)

    def _fetch_openai_metadata_suggestions(self) -> None:
        _uoo_fetch_openai_metadata_suggestions(self)

    def set_upload_status(self, color: str, text: str) -> None:
        _usst_set_upload_status(self, color, text)

    def evaluate_upload_status(self) -> tuple[str, str]:
        return _usst_evaluate_upload_status(self)

    def is_upload_metadata_ready(self) -> bool:
        return _usst_is_upload_metadata_ready(self)

    def update_upload_status_indicator(self) -> None:
        _usst_update_upload_status_indicator(self)

    def update_upload_image_preview(self, path: Path | None) -> None:
        _usst_update_upload_image_preview(self, path)

    def choose_file(self) -> None:
        _ufs_choose_file(self)

    def clear_selected_upload_file(self) -> None:
        _ufs_clear_selected_upload_file(self)

    def _start_upload_file_loading_indicator(self, token: int) -> None:
        _ufs_start_upload_file_loading_indicator(self, token)

    def _set_upload_file_loading_text(self, text: str, token: int) -> None:
        _ufs_set_upload_file_loading_text(self, text, token)

    def _tick_upload_file_loading_indicator(self, token: int) -> None:
        _ufs_tick_upload_file_loading_indicator(self, token)

    def _stop_upload_file_loading_indicator(self) -> None:
        _ufs_stop_upload_file_loading_indicator(self)

    def _finalize_selected_upload_file(self, path: Path, source: str, previous_selected: Path | None, source_sha256: str, duplicate_documents: list[dict], token: int) -> None:
        _ufs_finalize_selected_upload_file(self, path, source, previous_selected, source_sha256, duplicate_documents, token)

    def _commit_selected_upload_file_text(
        self,
        path: Path,
        source: str,
        previous_selected: Path | None,
        precheck_color: str,
        token: int,
    ) -> None:
        _ufs_commit_selected_upload_file_text(self, path, source, previous_selected, precheck_color, token)

    def _load_selected_upload_file_async(
        self,
        path: Path,
        source: str,
        previous_selected: Path | None,
        source_sha256_hint: str,
        token: int,
    ) -> None:
        _ufs_load_selected_upload_file_async(self, path, source, previous_selected, source_sha256_hint, token)

    def set_selected_upload_file(self, path: Path, source: str = "dialog") -> None:
        _ufs_set_selected_upload_file(self, path, source=source)

    def reset_upload_metadata_for_new_file(self) -> None:
        _ufs_reset_upload_metadata_for_new_file(self)

    def link_upload_ocr_pdf(self, path: Path) -> None:
        _ufs_link_upload_ocr_pdf(self, path)

    def parse_dropped_files(self, data: str) -> list[Path]:
        return _ufs_parse_dropped_files(self, data)

    def handle_upload_file_drop(self, event) -> str:
        return _ufs_handle_upload_file_drop(self, event)

    def enable_upload_drag_and_drop(self, *widgets: tk.Widget) -> None:
        _ufs_enable_upload_drag_and_drop(self, *widgets)

    def choose_upload_folder(self) -> None:
        _ufs_choose_upload_folder(self)

    def open_person_tagger(self) -> None:
        _usst_open_person_tagger(self)
