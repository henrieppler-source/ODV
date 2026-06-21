from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk, messagebox

from .config import OPENAI_DEFAULT_MODEL, OPENAI_MODEL_OPTIONS
from .openai_client import OpenAIClient
from .postprocess_openai_utils import (
    openai_cached_model_result as _ppm_openai_cached_model_result,
    openai_used_models as _ppm_openai_used_models,
    store_openai_model_result as _ppm_store_openai_model_result,
)
from .postprocess_dialog_utils import (
    choose_openai_action as _ppd_choose_openai_action,
    openai_display_height as _ppd_openai_display_height,
    openai_model_options as _ppd_openai_model_options,
    readonly_text_widget as _ppd_readonly_text_widget,
    resolve_openai_model_dialog_result as _ppd_resolve_openai_model_dialog_result,
)
from .postprocess_openai_document_utils import (
    active_admin_openai_meta_vars as _ppod_active_admin_openai_meta_vars,
    admin_openai_field_label as _ppod_admin_openai_field_label,
    admin_openai_selected_document as _ppod_admin_openai_selected_document,
    admin_openai_value_for_action as _ppod_admin_openai_value_for_action,
    apply_admin_openai_metadata_suggestions as _ppod_apply_admin_openai_metadata_suggestions,
    choose_admin_openai_model as _ppod_choose_admin_openai_model,
    current_admin_openai_field_value as _ppod_current_admin_openai_field_value,
    persist_admin_openai_form_item as _ppod_persist_admin_openai_form_item,
    save_admin_openai_item_to_storage as _ppod_save_admin_openai_item_to_storage,
    set_admin_openai_field_value as _ppod_set_admin_openai_field_value,
    show_admin_openai_apply_dialog as _ppod_show_admin_openai_apply_dialog,
    update_admin_tree_row_for_item as _ppod_update_admin_tree_row_for_item,
    use_file_view_openai_form as _ppod_use_file_view_openai_form,
)
from .postprocess_openai_form_utils import (
    active_admin_openai_meta_vars as _ppf_active_admin_openai_meta_vars,
    admin_openai_field_label as _ppf_admin_openai_field_label,
    admin_openai_value_for_action as _ppf_admin_openai_value_for_action,
    current_admin_openai_field_value as _ppf_current_admin_openai_field_value,
    persist_admin_openai_form_item as _ppf_persist_admin_openai_form_item,
    save_admin_openai_item_to_storage as _ppf_save_admin_openai_item_to_storage,
    set_admin_openai_field_value as _ppf_set_admin_openai_field_value,
    update_admin_tree_row_for_item as _ppf_update_admin_tree_row_for_item,
    use_file_view_openai_form as _ppf_use_file_view_openai_form,
)
from .postprocess_control_utils import update_admin_openai_controls as _ppctrl_update_admin_openai_controls
from .postprocess_place_scan_utils import (
    admin_openai_place_scan_selected_document as _ppps_admin_openai_place_scan_selected_document,
    compact_openai_place_contexts as _ppps_compact_openai_place_contexts,
    confirm_admin_place_scan_openai as _ppps_confirm_admin_place_scan_openai,
    place_context_counts as _ppps_place_context_counts,
    show_admin_place_contexts_dialog as _ppps_show_admin_place_contexts_dialog,
    show_admin_place_scan_result_dialog as _ppps_show_admin_place_scan_result_dialog,
)
from .postprocess_ocr_utils import (
    admin_create_ocr_for_selected_document as _ppoc_admin_create_ocr_for_selected_document,
    create_ocr_for_document_path as _ppoc_create_ocr_for_document_path,
)


class PostprocessManagerMixin:
    """OpenAI-, OCR- und Nachbearbeitungshelfer für die zentrale Dateiliste."""

    _OPENAI_SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".log", ".docx", ".odt", ".xlsx"}
    _OPENAI_FALLBACK_MODELS = OPENAI_MODEL_OPTIONS

    def _read_int_config(self, key: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
        try:
            value = int(self.config_data.get(key, default))
        except Exception:
            return default
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def _openai_default_model(self) -> str:
        return str(self.config_data.get("openai_model", OPENAI_DEFAULT_MODEL) or OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL

    def _openai_client_for_model(self, model_name: str, warning_title: str = "OpenAI") -> OpenAIClient | None:
        key = str(self.config_data.get("openai_api_key", "") or "").strip()
        if not key:
            messagebox.showwarning(warning_title, f"{warning_title} ist nicht konfiguriert.")
            return None
        return OpenAIClient(api_key=key, model=(str(model_name or "").strip() or OPENAI_DEFAULT_MODEL))

    def _resolve_openai_model_dialog_result(
        self,
        item: dict,
        result_field: str,
        legacy_model_field: str,
        previous_time_field: str,
        used_fallback: bool,
        accept_label: str,
        title_with_fallback: str,
        title_without: str,
        intro_with_fallback: str,
        intro_without: str,
        list_text_getter,
    ) -> str:
        return _ppd_resolve_openai_model_dialog_result(
            self,
            item,
            result_field,
            legacy_model_field,
            previous_time_field,
            used_fallback,
            accept_label,
            title_with_fallback,
            title_without,
            intro_with_fallback,
            intro_without,
            list_text_getter,
        )

    def _openai_model_options(self, item: dict, result_field: str, legacy_field: str) -> list[str]:
        return _ppd_openai_model_options(self, item, result_field, legacy_field)

    @staticmethod
    def _choose_openai_action(row_vars: dict[str, tk.BooleanVar], selected_action: str) -> None:
        _ppd_choose_openai_action(row_vars, selected_action)

    @staticmethod
    def _readonly_text_widget(parent: tk.Widget, value: str, width: int, height: int, background_source: tk.Widget | None = None) -> tk.Text:
        return _ppd_readonly_text_widget(parent, value, width, height, background_source=background_source)

    @staticmethod
    def _openai_display_height(value: str, wrap_at: int = 55, max_lines: int = 10, fallback: int = 1) -> int:
        return _ppd_openai_display_height(value, wrap_at=wrap_at, max_lines=max_lines, fallback=fallback)

    def existing_ocr_pdf_for_path(self, path: Path | None) -> Path | None:
        if path is None or path.suffix.lower() != ".pdf":
            return None
        exact = path.with_name(f"{path.stem}_ocr.pdf")
        if exact.exists() and exact.is_file():
            return exact
        candidates = [candidate for candidate in path.parent.glob(f"{path.stem}_ocr_#*.pdf") if candidate.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)

    def admin_selected_document_path(self) -> Path | None:
        path = self.file_view_current_path
        if path is not None and path.exists() and path.is_file():
            return path
        item = self.selected_admin_upload()
        if not item:
            return None
        return self.resolve_document_local_path(item)

    def update_admin_openai_controls(self) -> None:
        _ppctrl_update_admin_openai_controls(self)

    def admin_create_ocr_for_selected_document(self) -> None:
        _ppoc_admin_create_ocr_for_selected_document(self)

    def create_ocr_for_document_path(self, path: Path | None, item: dict | None = None, on_success=None) -> None:
        _ppoc_create_ocr_for_document_path(self, path, item=item, on_success=on_success)

    def admin_openai_selected_document(self) -> None:
        _ppod_admin_openai_selected_document(self)

    def openai_cached_model_result(self, item: dict, model: str, field: str) -> dict:
        return _ppm_openai_cached_model_result(item, model, field)

    def store_openai_model_result(self, item: dict, model: str, field: str, data: dict) -> None:
        _ppm_store_openai_model_result(item, model, field, data)

    def openai_used_models(self, item: dict, field: str, legacy_model_field: str = "") -> list[str]:
        return _ppm_openai_used_models(item, field, legacy_model_field)

    def apply_admin_openai_metadata_suggestions(self, item: dict, suggestions: dict, model_name: str, usage_text: str, cached: bool = False) -> None:
        _ppod_apply_admin_openai_metadata_suggestions(self, item, suggestions, model_name, usage_text, cached=cached)

    def admin_openai_place_scan_selected_document(self) -> None:
        _ppps_admin_openai_place_scan_selected_document(self)

    def place_context_counts(self, contexts: list[dict[str, str]]) -> dict[str, int]:
        return _ppps_place_context_counts(self, contexts)

    def confirm_admin_place_scan_openai(self, item: dict, contexts: list[dict[str, str]], used_fallback: bool = False) -> str:
        return _ppps_confirm_admin_place_scan_openai(self, item, contexts, used_fallback=used_fallback)

    def compact_openai_place_contexts(self, contexts: list[dict[str, str]]) -> list[dict[str, str]]:
        return _ppps_compact_openai_place_contexts(self, contexts)

    def show_admin_place_contexts_dialog(self) -> None:
        _ppps_show_admin_place_contexts_dialog(self)

    def show_admin_place_scan_result_dialog(
        self,
        item: dict,
        result: dict,
        contexts: list[dict[str, str]],
        usage_text: str,
        used_fallback: bool = False,
        model_name: str = "",
    ) -> None:
        _ppps_show_admin_place_scan_result_dialog(self, item, result, contexts, usage_text, used_fallback=used_fallback, model_name=model_name)

    def choose_admin_openai_model(self, item: dict) -> str:
        return _ppod_choose_admin_openai_model(self, item)

    def show_admin_openai_apply_dialog(self, suggestions: dict) -> list[str] | None:
        return _ppod_show_admin_openai_apply_dialog(self, suggestions)

    def current_admin_openai_field_value(self, key: str) -> str:
        return _ppf_current_admin_openai_field_value(self, key)

    def set_admin_openai_field_value(self, key: str, value: str) -> None:
        _ppf_set_admin_openai_field_value(self, key, value)

    def use_file_view_openai_form(self) -> bool:
        return _ppf_use_file_view_openai_form(self)

    def active_admin_openai_meta_vars(self) -> dict:
        return _ppf_active_admin_openai_meta_vars(self)

    def persist_admin_openai_form_item(self, item: dict) -> None:
        _ppf_persist_admin_openai_form_item(self, item)

    def save_admin_openai_item_to_storage(self, item: dict) -> tuple[bool, str]:
        return _ppf_save_admin_openai_item_to_storage(self, item)

    def update_admin_tree_row_for_item(self, item: dict) -> None:
        _ppf_update_admin_tree_row_for_item(self, item)

    def admin_openai_value_for_action(self, key: str, current: str, suggestion: str, action: str) -> str:
        return _ppf_admin_openai_value_for_action(self, key, current, suggestion, action)

    def admin_openai_field_label(self, key: str) -> str:
        return _ppf_admin_openai_field_label(self, key)
