from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .config import APP_DIR
from .upload_tab_openai_cache_utils import (
    add_openai_metadata_cache_entry as _utauc_add_openai_metadata_cache_entry,
    cached_openai_metadata_for_key as _utauc_cached_openai_metadata_for_key,
    openai_metadata_cache_key as _utauc_openai_metadata_cache_key,
    openai_metadata_cache_path as _utauc_openai_metadata_cache_path,
    load_openai_metadata_cache as _utauc_load_openai_metadata_cache,
    save_openai_metadata_cache as _utauc_save_openai_metadata_cache,
)


def openai_metadata_cache_path(_manager: Any) -> Path:
    return _utauc_openai_metadata_cache_path(APP_DIR)


def load_openai_metadata_cache(manager: Any) -> dict[str, Any]:
    return _utauc_load_openai_metadata_cache(openai_metadata_cache_path(manager))


def save_openai_metadata_cache(manager: Any, data: dict[str, Any]) -> None:
    _utauc_save_openai_metadata_cache(openai_metadata_cache_path(manager), data)


def openai_metadata_cache_key(manager: Any, analysis_file: Path | None = None) -> str | None:
    return _utauc_openai_metadata_cache_key(manager.selected_file, analysis_file)


def cached_openai_metadata_for_current_file(manager: Any) -> dict[str, Any] | None:
    analysis_file = manager.current_upload_ocr_pdf_path() or manager.selected_file
    key = openai_metadata_cache_key(manager, analysis_file)
    return _utauc_cached_openai_metadata_for_key(load_openai_metadata_cache(manager), key)


def store_openai_metadata_cache(manager: Any, analysis_file: Path | None, metadata: dict[str, Any], usage: dict[str, Any] | None, model: str) -> None:
    key = openai_metadata_cache_key(manager, analysis_file)
    data = _utauc_add_openai_metadata_cache_entry(
        load_openai_metadata_cache(manager),
        key,
        manager.selected_file,
        analysis_file,
        metadata,
        usage,
        model,
        datetime.now().isoformat(timespec="seconds"),
    )
    save_openai_metadata_cache(manager, data)


def apply_cached_openai_metadata_if_available(manager: Any, model_name: str | None = None) -> bool:
    cached = cached_openai_metadata_for_current_file(manager)
    if not cached:
        return False
    cached_model = str(cached.get("model") or "").strip()
    if model_name and cached_model and model_name != cached_model:
        return False
    metadata = cached.get("metadata") if isinstance(cached.get("metadata"), dict) else {}
    manager.openai_metadata_suggestions = {k: v for k, v in metadata.items() if str(v or "").strip()}
    manager.openai_metadata_source_model = str(cached.get("model") or "OpenAI").strip() or "OpenAI"
    manager.upload_openai_metadata_button.configure(state="normal" if manager.openai_metadata_suggestions else "disabled")
    manager.upload_openai_usage_var.set("Verbrauch: 0 Tokens (Cache)")
    if manager.openai_metadata_suggestions:
        manager.upload_openai_text_var.set("OpenAI: Metadatenvorschläge aus lokalem Cache verfügbar")
        manager.after(0, manager.show_upload_openai_apply_dialog_if_available)
        return True
    return False
