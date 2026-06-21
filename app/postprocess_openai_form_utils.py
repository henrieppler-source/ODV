from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import tkinter as tk

from .file_service import append_metadata_history


def current_admin_openai_field_value(manager: Any, key: str) -> str:
    if manager.use_file_view_openai_form():
        if key == "description":
            return manager.file_view_description_text.get("1.0", "end").strip()
        var = manager.file_view_meta_vars.get(key)
        return str(var.get() or "").strip() if var is not None else ""
    if key == "description":
        return manager.admin_description_text.get("1.0", "end").strip()
    var = manager.admin_meta_vars.get(key)
    return str(var.get() or "").strip() if var is not None else ""


def set_admin_openai_field_value(manager: Any, key: str, value: str) -> None:
    if manager.use_file_view_openai_form():
        if key == "description":
            value = manager.normalize_description_text(value)
            manager.file_view_description_text.delete("1.0", "end")
            manager.file_view_description_text.insert("1.0", value)
            return
        var = manager.file_view_meta_vars.get(key)
        if var is not None:
            var.set(value)
        return
    if key == "description":
        value = manager.normalize_description_text(value)
        manager.admin_description_text.delete("1.0", "end")
        manager.admin_description_text.insert("1.0", value)
        return
    var = manager.admin_meta_vars.get(key)
    if var is not None:
        var.set(value)


def use_file_view_openai_form(manager: Any) -> bool:
    return bool(manager.is_unified_file_view_active())


def active_admin_openai_meta_vars(manager: Any) -> dict:
    if manager.use_file_view_openai_form():
        return manager.file_view_meta_vars
    return manager.admin_meta_vars


def persist_admin_openai_form_item(manager: Any, item: dict) -> None:
    """Persist the visible admin metadata form into the concrete analyzed item."""
    technical_edit_keys = {"upload_id", "edited_by", "edited_at"}
    meta_vars = manager.active_admin_openai_meta_vars()
    for key, var in meta_vars.items():
        if key in technical_edit_keys:
            continue
        raw_value = var.get()
        item[key] = "1" if isinstance(var, tk.BooleanVar) and bool(raw_value) else ("0" if isinstance(var, tk.BooleanVar) else str(raw_value).strip())
    description_widget = manager.file_view_description_text if manager.use_file_view_openai_form() else manager.admin_description_text
    note_widget = manager.file_view_note_text if manager.use_file_view_openai_form() else manager.admin_note_text
    if description_widget is not None:
        item["description"] = manager.normalize_description_text(description_widget.get("1.0", "end").strip())
    if note_widget is not None:
        item["note"] = note_widget.get("1.0", "end").strip()
    display_name = manager.display_name_var.get().strip() or "Admin"
    edited_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item["edited_by"] = display_name
    item["edited_at"] = edited_at
    if "edited_by" in meta_vars:
        meta_vars["edited_by"].set(display_name)
    if "edited_at" in meta_vars:
        meta_vars["edited_at"].set(edited_at)


def save_admin_openai_item_to_storage(manager: Any, item: dict) -> tuple[bool, str]:
    if bool(item.get("_missing_odv_entry")):
        path_text = str(item.get("current_path") or "").strip()
        path = Path(path_text) if path_text else None
        if path is None or not path.exists() or not path.is_file():
            return False, "Lokale Datei für neuen ODV-Eintrag nicht gefunden"
        tree_iid = str(item.get("_tree_iid") or item.get("upload_id") or "")
        new_item, metadata_file = manager.ensure_file_view_metadata_item(path)
        real_upload_id = str(new_item.get("upload_id") or "")
        metadata_file_text = str(metadata_file)
        pending_flag = bool(new_item.get("_pending_existing_file_metadata", True))
        for key, value in list(item.items()):
            if key in {"upload_id", "_display_upload_id", "_display_status", "_display_by", "_display_date", "_tree_iid"}:
                continue
            if key.startswith("_") and key not in {"_metadata_file"}:
                continue
            new_item[key] = value
        new_item["upload_id"] = real_upload_id
        new_item["_metadata_file"] = metadata_file_text
        new_item["_pending_existing_file_metadata"] = pending_flag
        new_item["_tree_iid"] = tree_iid
        new_item["_display_upload_id"] = real_upload_id
        new_item["_display_status"] = new_item.get("status") or "erfasst"
        new_item["status"] = "erfasst" if str(new_item.get("status") or "").strip() == "ohne" else str(new_item.get("status") or "erfasst")
        display_name = manager.display_name_var.get().strip() or "Admin"
        append_metadata_history(new_item, display_name, "Vorhandene Datei durch OpenAI-Ortsanalyse in ODV aufgenommen", path.name)
        ok, msg = manager.save_file_view_item_to_storage(new_item, metadata_file, True)
        item.clear()
        item.update(new_item)
        item.pop("_missing_odv_entry", None)
        item.pop("_pending_existing_file_metadata", None)
        return ok, msg
    api_ok, api_msg = manager.save_item_to_api(item)
    manager.save_item_json_if_present(item)
    return api_ok, api_msg


def update_admin_tree_row_for_item(manager: Any, item: dict) -> None:
    if manager.is_unified_file_view_active():
        manager.file_view_current_metadata = item
        manager.load_file_view_metadata_form()
        try:
            manager.refresh_file_view_tree()
        except Exception:
            pass
        return
    tree_iid = str(item.get("_tree_iid") or item.get("upload_id") or "")
    if not tree_iid or not manager.admin_tree.exists(tree_iid):
        return
    manager.admin_tree.item(
        tree_iid,
        values=(
            item.get("_display_upload_id") or item.get("upload_id") or "",
            item.get("_display_status") or item.get("status", "hochgeladen"),
            item.get("current_filename") or item.get("stored_filename") or item.get("original_filename", ""),
            item.get("_display_by") if "_display_by" in item else (item.get("uploaded_by") or item.get("uploaded_by_name", "")),
            item.get("_display_date") if "_display_date" in item else item.get("uploaded_at", ""),
            item.get("document_type", ""),
        ),
    )


def admin_openai_value_for_action(manager: Any, key: str, current: str, suggestion: str, action: str) -> str:
    current = str(current or "").strip()
    suggestion = str(suggestion or "").strip()
    if action == "take":
        if not current:
            return suggestion
        if key == "place":
            return manager.merge_place_values(current, suggestion)
        if key == "keywords":
            return manager.merge_metadata_values(current, suggestion, separator=", ")
        return suggestion
    if action == "replace":
        return suggestion
    if action == "append":
        if key == "description":
            return manager.append_openai_description(current, suggestion)
        if key == "place":
            return manager.merge_place_values(current, suggestion)
        return manager.merge_metadata_values(current, suggestion, separator=", " if key == "keywords" else "; ")
    return current


def admin_openai_field_label(_manager: Any, key: str) -> str:
    labels = {
        "document_type": "Dokumenttyp",
        "document_date": "Datum / Zeitraum",
        "place": "Ort",
        "event": "Ereignis",
        "keywords": "Stichwörter",
        "description": "Beschreibung",
        "primary_source": "Primärquelle",
        "secondary_source": "Sekundärquelle",
        "original_location": "Standort Original",
        "archive_name": "Archiv",
        "archive_signature": "Signatur",
        "archive_accessed_at": "Abruf am",
        "copyright_author": "Urheber/in",
        "rights_holder": "Rechteinhaber",
        "usage_permission": "Nutzungsfreigabe",
        "license_note": "Lizenz",
        "rights_note": "Rechte",
    }
    return labels.get(key, key)
