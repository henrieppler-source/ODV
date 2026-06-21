from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
from typing import Any

import tkinter as tk
from tkinter import ttk, messagebox

from .app_logging import app_log_exception
from .file_service import append_metadata_history
from .openai_client import OpenAIError
from .upload_tab_metadata_utils import limit_openai_keywords as _utm_limit_openai_keywords


def admin_openai_selected_document(manager: Any) -> None:
    item = manager.selected_admin_upload()
    path = manager.admin_selected_document_path()
    if not item or path is None:
        return
    selected_model = manager.choose_admin_openai_model(item)
    if not selected_model:
        return
    cached = manager.openai_cached_model_result(item, selected_model, "openai_model_results")
    if cached:
        suggestions = cached.get("suggestions") if isinstance(cached.get("suggestions"), dict) else {}
        usage_text = str(cached.get("usage_text") or f"gespeichertes Ergebnis ({selected_model})")
        manager.apply_admin_openai_metadata_suggestions(item, suggestions, selected_model, usage_text, cached=True)
        manager.update_admin_openai_controls()
        return
    analysis_path = manager.existing_ocr_pdf_for_path(path) or path
    sample = manager.extract_upload_text_sample(analysis_path, max_chars=manager.openai_text_sample_chars(), max_pdf_pages=manager.openai_pdf_sample_pages())
    if not sample and path.suffix.lower() == ".pdf":
        messagebox.showwarning("OpenAI", "Dieses PDF ist lokal nicht lesbar. Bitte zuerst PDF OCR erstellen.")
        manager.update_admin_openai_controls()
        return
    client = manager._openai_client_for_model(selected_model, warning_title="OpenAI")
    if client is None:
        return
    manager.admin_openai_button.configure(state="disabled")
    manager.admin_openai_status_var.set(f"OpenAI prüft mit {selected_model} ...")

    def run() -> None:
        try:
            result = client.analyze_upload_file(filename=path.name, extension=path.suffix.lower(), sample=sample)
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
            local_metadata = manager.derive_metadata_from_text(filename=path.name, extension=path.suffix.lower(), sample=sample)
            merged = dict(local_metadata)
            for key, value in metadata.items():
                if str(value or "").strip():
                    merged[key] = value
            usage_text = manager.format_openai_usage(result.get("usage", {}), model_name=client.model)
            manager.store_openai_model_result(item, client.model, "openai_model_results", {
                "suggestions": merged,
                "usage_text": usage_text,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            })

            def apply() -> None:
                manager.apply_admin_openai_metadata_suggestions(item, merged, client.model, usage_text, cached=False)
                manager.update_admin_openai_controls()

            manager.after(0, apply)
        except OpenAIError as exc:
            manager.after(0, lambda: manager.admin_openai_status_var.set(f"OpenAI: {exc.user_message()}"))
            manager.after(0, manager.update_admin_openai_controls)
        except Exception as exc:
            app_log_exception("Admin-OpenAI-Prüfung fehlgeschlagen", exc, path=str(path))
            manager.after(0, lambda: manager.admin_openai_status_var.set("OpenAI-Fehler"))
            manager.after(0, manager.update_admin_openai_controls)

    threading.Thread(target=run, daemon=True).start()


def apply_admin_openai_metadata_suggestions(manager: Any, item: dict, suggestions: dict, model_name: str, usage_text: str, cached: bool = False) -> None:
    changed = manager.show_admin_openai_apply_dialog(suggestions)
    if changed is None:
        manager.admin_openai_status_var.set(f"OpenAI: Vorschläge nicht übernommen | {usage_text}")
        return
    previous_fields = [str(field) for field in (item.get("openai_metadata_fields", []) or []) if str(field).strip()]
    item["openai_metadata_fields"] = list(dict.fromkeys(previous_fields + changed))
    item["openai_metadata_model"] = model_name
    item["openai_metadata_applied_at"] = datetime.now().isoformat(timespec="seconds")
    details = f"Modell: {model_name}"
    details += "; gespeichertes Ergebnis verwendet" if cached else "; neues Ergebnis gespeichert"
    details += f"; Felder: {', '.join(changed)}" if changed else "; keine Felder übernommen"
    append_metadata_history(item, manager.display_name_var.get().strip() or "Admin", "OpenAI-Metadaten geprüft", details)
    if changed:
        manager.persist_admin_openai_form_item(item)
        api_ok, api_msg = manager.save_admin_openai_item_to_storage(item)
        manager.update_admin_tree_row_for_item(item)
        if api_ok:
            manager.admin_openai_status_var.set(f"OpenAI: {len(changed)} Feld(er) übernommen und gespeichert | {usage_text}")
        else:
            manager.admin_openai_status_var.set(f"OpenAI: lokal übernommen; MySQL nicht gespeichert: {api_msg} | {usage_text}")
    else:
        api_ok, api_msg = manager.save_admin_openai_item_to_storage(item)
        if api_ok:
            manager.update_admin_tree_row_for_item(item)
            manager.admin_openai_status_var.set(f"OpenAI: Modell geprüft, keine Felder übernommen | {usage_text}")
        else:
            manager.admin_openai_status_var.set(f"OpenAI: Modell lokal markiert; MySQL nicht gespeichert: {api_msg} | {usage_text}")


def choose_admin_openai_model(manager: Any, item: dict) -> str:
    used_models = manager.openai_used_models(item, "openai_model_results", "openai_metadata_model")
    previous_fields = ", ".join(str(field) for field in (item.get("openai_metadata_fields", []) or []) if str(field).strip()) or "-"
    previous_time = str(item.get("openai_metadata_applied_at") or "").strip() or "-"
    return manager._resolve_openai_model_dialog_result(
        item=item,
        result_field="openai_model_results",
        legacy_model_field="openai_metadata_model",
        previous_time_field="openai_metadata_applied_at",
        used_fallback=False,
        accept_label="OpenAI prüfen",
        title_with_fallback="OpenAI-Modell wählen",
        title_without="OpenAI-Modell wählen",
        intro_with_fallback=f"Bisheriges OpenAI-Modell: {', '.join(used_models) or 'noch keine OpenAI-Prüfung'}\n\nBisherige Felder: {previous_fields}\n\nZeitpunkt: {previous_time}",
        intro_without=f"Bisheriges OpenAI-Modell: {', '.join(used_models) or 'noch keine OpenAI-Prüfung'}\n\nBisherige Felder: {previous_fields}\n\nZeitpunkt: {previous_time}",
        list_text_getter=lambda: "\n".join(
            [
                f"Bisheriges OpenAI-Modell: {', '.join(used_models) or 'noch keine OpenAI-Prüfung'}",
                f"Bisherige Felder: {previous_fields}",
                f"Letzter Stand: {previous_time}",
                "",
                "Neu prüfen mit Modell:",
            ]
        ),
    )


def show_admin_openai_apply_dialog(manager: Any, suggestions: dict) -> list[str] | None:
    excluded_fields = {"document_type"}
    rows = []
    active_vars = manager.active_admin_openai_meta_vars()
    for key, value in suggestions.items():
        if key in excluded_fields:
            continue
        text = str(value or "").strip()
        if not text:
            continue
        current = manager.current_admin_openai_field_value(key)
        if key == "description" or key in active_vars:
            rows.append((key, current, text))
    if not rows:
        messagebox.showinfo("OpenAI", "OpenAI hat keine übernehmbaren Metadatenvorschläge geliefert.")
        return []

    dialog = tk.Toplevel(manager)
    dialog.title("OpenAI-Metadaten übernehmen")
    dialog.transient(manager)
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
        row_height = max(manager._openai_display_height(current), manager._openai_display_height(suggestion))
        ttk.Label(inner, text=manager.admin_openai_field_label(key), width=18).grid(row=row_index, column=0, sticky="nw", padx=4, pady=3)
        manager._readonly_text_widget(inner, current or "-", width=34, height=row_height, background_source=dialog).grid(row=row_index, column=1, sticky="nw", padx=4, pady=3)
        manager._readonly_text_widget(inner, suggestion, width=56, height=row_height, background_source=dialog).grid(row=row_index, column=2, sticky="nw", padx=4, pady=3)
        ttk.Checkbutton(inner, variable=row_vars["take"], command=lambda vars=row_vars: manager._choose_openai_action(vars, "take")).grid(row=row_index, column=3, sticky="n", padx=4, pady=3)
        ttk.Checkbutton(inner, variable=row_vars["replace"], command=lambda vars=row_vars: manager._choose_openai_action(vars, "replace")).grid(row=row_index, column=4, sticky="n", padx=4, pady=3)
        ttk.Checkbutton(inner, variable=row_vars["append"], command=lambda vars=row_vars: manager._choose_openai_action(vars, "append")).grid(row=row_index, column=5, sticky="n", padx=4, pady=3)
    result = {"changed": None}

    def apply_selection() -> None:
        changed: list[str] = []
        for key, current, suggestion in rows:
            selected = [action_name for action_name, var in action_vars[key].items() if var.get()]
            action = selected[0] if selected else ""
            if not action:
                continue
            new_value = manager.admin_openai_value_for_action(key, current, suggestion, action)
            if new_value != current:
                manager.set_admin_openai_field_value(key, new_value)
                changed.append(key)
        result["changed"] = changed
        dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 12))
    ttk.Button(buttons, text="Auswahl übernehmen", command=apply_selection).pack(side="left", padx=4)
    ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
    manager.wait_window(dialog)
    return result["changed"]


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
