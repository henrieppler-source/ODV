from __future__ import annotations

from pathlib import Path
import re
import threading
from typing import Any

import tkinter as tk
from tkinter import ttk, messagebox

from .config import OPENAI_DEFAULT_MODEL, OPENAI_MODEL_OPTIONS
from .openai_client import OpenAIClient, OpenAIError
from .upload_tab_metadata_utils import limit_openai_keywords as _utm_limit_openai_keywords


def openai_available(manager: Any) -> bool:
    return bool(manager.config_data.get("openai_api_key", "").strip())


def _openai_privacy_blockers(manager: Any) -> dict[str, bool]:
    defaults = {
        "bankdaten": True,
        "gesundheitsdaten": True,
        "ausweis_steuerdaten": True,
        "zugangsdaten": True,
    }
    blockers = manager.config_data.get("openai_privacy_blockers", defaults)
    if not isinstance(blockers, dict):
        return defaults
    merged = {key: bool(blockers.get(key, value)) for key, value in defaults.items()}
    merged["zugangsdaten"] = True
    return merged


def openai_client(manager: Any, model_name: str | None = None) -> OpenAIClient | None:
    api_key = manager.config_data.get("openai_api_key", "").strip()
    if not api_key:
        return None
    model = str(manager.config_data.get("openai_model", OPENAI_DEFAULT_MODEL) or OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL
    if str(manager.current_role()).strip().lower() in {"admin", "superadmin"} and model_name:
        model = str(model_name).strip() or model
    return OpenAIClient(api_key=api_key, model=model or OPENAI_DEFAULT_MODEL)


def upload_openai_model_choices(manager: Any, cached_model: str | None = None) -> list[str]:
    models: list[str] = []
    current = str(manager.config_data.get("openai_model", OPENAI_DEFAULT_MODEL) or OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL
    for model in (current, *OPENAI_MODEL_OPTIONS, str(cached_model or "").strip()):
        if not model:
            continue
        if model not in models:
            models.append(model)
    return models


def choose_upload_openai_model(manager: Any, cached_model: str | None = None) -> str:
    current_model = str(manager.config_data.get("openai_model", OPENAI_DEFAULT_MODEL) or OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL
    cached_model = str(cached_model or "").strip()
    model_values = upload_openai_model_choices(manager, cached_model)
    if not model_values:
        model_values = [current_model]

    dialog = tk.Toplevel(manager)
    dialog.title("OpenAI-Modell wählen")
    dialog.transient(manager)
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
    ttk.Label(dialog, textvariable=info_var, foreground="#555555", wraplength=500).grid(row=3, column=0, sticky="w", padx=12, pady=(8, 8))

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
    manager.wait_window(dialog)
    return result["model"]


def _clean_openai_label_text(text: str) -> str:
    text = (text or "").strip()
    if text.lower().startswith("openai:"):
        text = text[7:].strip()
    return text


def _needs_manual_metadata_hint(color: str, text: str) -> bool:
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


def reset_openai_status(manager: Any, message: str | None = None) -> None:
    manager.openai_metadata_suggestions = {}
    manager.openai_metadata_applied_fields = []
    manager.openai_metadata_source_model = ""
    manager.upload_openai_metadata_button.configure(state="disabled")
    precheck_color, precheck_text = evaluate_openai_precheck(manager)
    clean_precheck = _clean_openai_label_text(precheck_text)
    manual_hint = _needs_manual_metadata_hint(precheck_color, precheck_text)

    if not openai_available(manager):
        status = "OpenAI: nicht konfiguriert"
    elif not manager.selected_file:
        status = "OpenAI: keine Einzeldatei ausgewählt"
    elif precheck_color == "red":
        status = "OpenAI-Prüfung: nicht möglich"
        if manual_hint:
            detail = clean_precheck or "Datenschutz- oder technische Regel greift"
            status = f"{status} ({detail}). Metadaten bitte manuell ergänzen."
        elif clean_precheck:
            status = f"{status} ({clean_precheck})."
    elif precheck_color == "yellow":
        if message is None:
            detail = clean_precheck
            status = f"OpenAI-Prüfung: eingeschränkt ({detail})" if detail else "OpenAI-Prüfung: eingeschränkt"
        else:
            status = message
    else:
        status = message or "OpenAI-Prüfung: bitte starten"

    manager.upload_openai_text_var.set(status)
    manager.upload_openai_usage_var.set("Verbrauch: k.A.")
    update_openai_precheck_indicator(manager)


def set_openai_precheck_status(manager: Any, color: str, text: str) -> None:
    manager.upload_openai_precheck_var.set(_clean_openai_label_text(text))
    color_map = {
        "red": "#d9534f",
        "yellow": "#f0ad4e",
        "green": "#5cb85c",
    }
    manager.upload_openai_precheck_label.configure(foreground=color_map.get(color, "#555555"))


def evaluate_openai_precheck(manager: Any) -> tuple[str, str]:
    path = manager.selected_file
    if manager.selected_folder is not None:
        return "yellow", "OpenAI: Ordnerupload - Prüfung nur für einzelne Dateien möglich."
    if path is None:
        return "red", "OpenAI: keine Datei ausgewählt."
    if not path.exists() or not path.is_file():
        return "red", "OpenAI: Datei fehlt oder ist nicht lesbar."

    suffix = path.suffix.lower()
    blocked_extensions = {
        ".exe", ".msi", ".bat", ".cmd", ".ps1", ".dll", ".com", ".scr",
        ".zip", ".7z", ".rar", ".tar", ".gz", ".db", ".sqlite", ".sqlite3",
    }
    if suffix in blocked_extensions:
        return "red", "OpenAI: technische/Archivdatei - nicht an OpenAI senden."

    ocr_path = manager.current_upload_ocr_pdf_path()
    sample = manager.extract_upload_text_sample(
        ocr_path if ocr_path and ocr_path.exists() else path,
        max_chars=manager.openai_text_sample_chars(),
        max_pdf_pages=manager.openai_pdf_sample_pages(),
    )
    text = sample or ""
    lower_text = text.lower()
    lower_name = path.name.lower()

    blockers = _openai_privacy_blockers(manager)
    sensitive_patterns = [
        (r"\biban\b|\bde\d{20}\b", "Bankdaten", "bankdaten"),
        (r"\bdiagnose\b|\bpatient\b|\bkrankenkasse\b|\bmedikation\b|\bbefund\b", "Gesundheitsdaten", "gesundheitsdaten"),
        (r"\bpersonalausweis\b|\bausweisnummer\b|\bsteuer-id\b|\bsteuernummer\b", "Ausweis-/Steuerdaten", "ausweis_steuerdaten"),
        (r"\bpasswort\b|\bkennwort\b|\bapi[_ -]?key\b|\btoken\b", "Zugangsdaten", "zugangsdaten"),
    ]
    for pattern, label, blocker_key in sensitive_patterns:
        if not blockers.get(blocker_key, True):
            continue
        if re.search(pattern, lower_text) or re.search(pattern, lower_name):
            return "red", f"OpenAI: mögliche {label} erkannt - nicht an OpenAI senden."

    if not sample:
        if suffix in {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}:
            if suffix == ".pdf":
                return "yellow", "OpenAI: PDF enthält lokal keinen lesbaren Text - bitte ggf. zuerst PDF OCR erstellen."
            return "yellow", "OpenAI: kein lokaler Textauszug - Prüfung wäre nur eingeschränkt möglich."
        return "yellow", "OpenAI: Inhalt lokal nicht auslesbar - OpenAI-Prüfung möglich, aber unsicher."

    if len(text.strip()) < 120:
        return "yellow", "OpenAI: sehr wenig Text - OpenAI kann prüfen, Ergebnis kann dünn sein."

    archive_terms = [
        "ortschron", "niederschrift", "protokoll", "chronik", "geschichte",
        "datum", "ort:", "zeit/dauer", "tagesordnung", "verein", "stadt",
        "gemeinde", "archiv", "quelle", "veranstaltung",
    ]
    if any(term in lower_text or term in lower_name for term in archive_terms):
        return "green", "OpenAI: Text ist lokal lesbar und wirkt für Metadatenprüfung geeignet."

    return "yellow", "OpenAI: Prüfung möglich, Archivbezug lokal nicht eindeutig."


def update_openai_precheck_indicator(manager: Any) -> tuple[str, str]:
    color, text = evaluate_openai_precheck(manager)
    set_openai_precheck_status(manager, color, text)
    manager.refresh_upload_ai_controls_visibility()
    manager.open_file_openai_button.configure(state=("disabled" if color == "red" else "normal"))
    manager.upload_ocr_pdf_button.configure(state=("normal" if manager.is_upload_image_pdf() else "disabled"))
    ocr_path = manager.current_upload_ocr_pdf_path()
    manager.upload_show_ocr_pdf_button.configure(state=("normal" if ocr_path and ocr_path.exists() else "disabled"))
    return color, text


def current_upload_openai_field_value(manager: Any, key: str) -> str:
    if key == "description":
        return manager.description_text.get("1.0", "end").strip()
    var = manager.meta_vars.get(key)
    return str(var.get() or "").strip() if var is not None else ""


def set_upload_openai_field_value(manager: Any, key: str, value: str) -> None:
    value = manager.normalize_description_text(value) if key == "description" else str(value or "").strip()
    if key == "description":
        manager.description_text.delete("1.0", "end")
        manager.description_text.insert("1.0", value)
        return
    var = manager.meta_vars.get(key)
    if var is not None:
        var.set(value)


def show_upload_openai_apply_dialog(manager: Any, suggestions: dict[str, Any]) -> list[str] | None:
    excluded_fields = {"file_type", "confidence", "advice", "usage"}
    rows: list[tuple[str, str, str]] = []
    for key, raw_value in suggestions.items():
        if key in excluded_fields:
            continue
        suggestion = str(raw_value or "").strip()
        if not suggestion:
            continue
        if key == "description":
            current = current_upload_openai_field_value(manager, "description")
        elif key in manager.meta_vars:
            current = current_upload_openai_field_value(manager, key)
        else:
            continue
        rows.append((key, current, suggestion))

    if not rows:
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
        changed_fields: list[str] = []
        for key, _current, suggestion in rows:
            action_items = [action_name for action_name, var in action_vars[key].items() if var.get()]
            action = action_items[0] if action_items else ""
            if not action:
                continue
            current = current_upload_openai_field_value(manager, key)
            new_value = manager.admin_openai_value_for_action(key, current, suggestion, action)
            new_value = manager.normalize_description_text(new_value) if key == "description" else str(new_value or "").strip()
            if new_value != current:
                set_upload_openai_field_value(manager, key, new_value)
                changed_fields.append(key)
        result["changed"] = changed_fields
        dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 12))
    ttk.Button(buttons, text="Auswahl übernehmen", command=apply_selection).pack(side="left", padx=4)
    ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
    manager.wait_window(dialog)
    return result["changed"]


def show_upload_openai_apply_dialog_if_available(manager: Any) -> None:
    if not manager.openai_metadata_suggestions:
        manager.upload_openai_text_var.set("OpenAI: keine Metadatenvorschläge verfügbar")
        return
    changed = show_upload_openai_apply_dialog(manager, manager.openai_metadata_suggestions)
    if changed is None:
        manager.upload_openai_text_var.set("OpenAI: Übernahme abgebrochen")
        return
    if changed:
        current_fields = list(manager.openai_metadata_applied_fields or [])
        for field in changed:
            if field not in current_fields:
                current_fields.append(field)
        manager.openai_metadata_applied_fields = current_fields
        manager.upload_openai_text_var.set(f"OpenAI: Metadaten übernommen ({', '.join(changed)})")
        manager.update_upload_status_indicator()
    else:
        manager.upload_openai_text_var.set("OpenAI: Keine neuen Metadaten übernommen")


def on_apply_openai_metadata(manager: Any) -> None:
    if not manager.openai_metadata_suggestions:
        manager.upload_openai_text_var.set("OpenAI: keine Metadatenvorschläge verfügbar – zuerst „OpenAI prüfen“ drücken")
        manager.upload_openai_metadata_button.configure(state="disabled")
        return
    changed = show_upload_openai_apply_dialog(manager, manager.openai_metadata_suggestions)
    if changed is None:
        manager.upload_openai_text_var.set("OpenAI: Übernahme abgebrochen")
        return
    if changed:
        current_fields = list(manager.openai_metadata_applied_fields or [])
        for field in changed:
            if field not in current_fields:
                current_fields.append(field)
        manager.openai_metadata_applied_fields = current_fields
        manager.upload_openai_text_var.set(f"OpenAI: Metadaten übernommen ({', '.join(changed)})")
        manager.update_upload_status_indicator()
    else:
        manager.upload_openai_text_var.set("OpenAI: Keine neuen Metadaten übernommen")


def queue_openai_check(manager: Any, auto_apply: bool = False, allow_yellow: bool = False) -> None:
    manager.openai_metadata_suggestions = {}
    manager.upload_openai_metadata_button.configure(state="disabled")
    color, precheck_text = update_openai_precheck_indicator(manager)
    clean_precheck = _clean_openai_label_text(precheck_text)
    if color == "red":
        manual_hint = _needs_manual_metadata_hint(color, precheck_text)
        if manual_hint:
            reason = clean_precheck or "Datenschutz- oder technische Regel greift"
            status = f"OpenAI-Prüfung: nicht möglich ({reason}). Metadaten bitte manuell ergänzen."
        elif clean_precheck:
            status = f"OpenAI-Prüfung: nicht möglich ({clean_precheck})."
        else:
            status = "OpenAI-Prüfung: nicht möglich."
        manager.upload_openai_text_var.set(status)
        manager.upload_openai_usage_var.set("Verbrauch: k.A.")
        if not auto_apply:
            messagebox.showwarning("OpenAI-Prüfung", precheck_text)
        return
    if color == "yellow" and not allow_yellow:
        if not messagebox.askyesno("OpenAI-Prüfung", f"{precheck_text}\n\nTrotzdem mit OpenAI prüfen?"):
            manager.upload_openai_text_var.set("OpenAI: Prüfung durch Benutzer abgebrochen")
            manager.upload_openai_usage_var.set("Verbrauch: k.A.")
            return
    if not manager.selected_file:
        manager.upload_openai_text_var.set("OpenAI: keine Einzeldatei ausgewählt")
        manager.upload_openai_usage_var.set("Verbrauch: k.A.")
        return

    cached = manager.cached_openai_metadata_for_current_file()
    cached_model = str(cached.get("model") or "").strip() if isinstance(cached, dict) else ""
    selected_model = ""
    if manager.is_current_admin() and not auto_apply:
        selected_model = choose_upload_openai_model(manager, cached_model)
        if not selected_model:
            manager.upload_openai_text_var.set("OpenAI: Prüfung durch Benutzer abgebrochen")
            manager.upload_openai_usage_var.set("Verbrauch: k.A.")
            return
        if cached_model and selected_model == cached_model and manager.apply_cached_openai_metadata_if_available(selected_model):
            manager.update_upload_status_indicator()
            return
    elif cached_model and manager.apply_cached_openai_metadata_if_available():
        manager.update_upload_status_indicator()
        return

    if not openai_available(manager):
        manager.upload_openai_text_var.set("OpenAI: nicht konfiguriert")
        manager.upload_openai_usage_var.set("Verbrauch: k.A.")
        return
    manager.upload_openai_text_var.set("OpenAI prüft …")
    manager.upload_openai_usage_var.set("Verbrauch: k.A.")
    thread = threading.Thread(target=_run_openai_check, args=(manager, auto_apply, selected_model), daemon=True)
    thread.start()


def _run_openai_check(manager: Any, auto_apply: bool = False, model: str | None = None) -> None:
    if not openai_available(manager) or not manager.selected_file:
        return
    client = openai_client(manager, model)
    if client is None:
        return
    manager.openai_metadata_source_model = client.model
    analysis_file = manager.current_upload_ocr_pdf_path() or manager.selected_file
    filename = manager.selected_file.name if manager.selected_file else ""
    extension = manager.selected_file.suffix.lower() if manager.selected_file else ""
    sample = manager.extract_upload_text_sample(
        analysis_file,
        max_chars=manager.openai_text_sample_chars(),
        max_pdf_pages=manager.openai_pdf_sample_pages(),
    ) if analysis_file else None
    local_metadata = manager.derive_metadata_from_text(filename=filename, extension=extension, sample=sample)
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
        manager.openai_metadata_suggestions = useful_metadata

        label = f"OpenAI: {file_type}"
        if confidence:
            label += f" ({confidence})"
        if advice:
            label += f" – {advice}"
        if useful_metadata:
            label += " – Metadatenvorschläge bereit"
        else:
            label += " – keine übernehmbaren Metadaten gefunden"

        usage_text = manager.format_openai_usage(result.get("usage", {}), model_name=client.model)
        manager.store_openai_metadata_cache(analysis_file, useful_metadata, result.get("usage", {}), client.model)
        metadata_button_state = "normal" if useful_metadata else "disabled"
        manager.after(0, lambda: manager.upload_openai_text_var.set(label))
        manager.after(0, lambda: manager.upload_openai_usage_var.set(usage_text))
        manager.after(0, lambda: manager.upload_openai_metadata_button.configure(state=metadata_button_state))
        manager.after(0, manager.show_upload_openai_apply_dialog_if_available)
        manager.after(0, manager.update_upload_status_indicator)
    except OpenAIError as exc:
        manager.openai_metadata_suggestions = {}
        manager.after(0, lambda: manager.upload_openai_text_var.set(f"OpenAI: {exc.user_message()}"))
        manager.after(0, lambda: manager.upload_openai_metadata_button.configure(state="disabled"))
        manager.after(0, lambda: manager.upload_openai_usage_var.set("Verbrauch: k.A."))
    except Exception:
        manager.openai_metadata_suggestions = {}
        manager.after(0, lambda: manager.upload_openai_text_var.set("OpenAI-Fehler"))
        manager.after(0, lambda: manager.upload_openai_metadata_button.configure(state="disabled"))
        manager.after(0, lambda: manager.upload_openai_usage_var.set("Verbrauch: k.A."))


def _fetch_openai_metadata_suggestions(manager: Any) -> None:
    if not openai_available(manager) or not manager.selected_file:
        return
    client = openai_client(manager)
    if client is None:
        return
    analysis_file = manager.current_upload_ocr_pdf_path() or manager.selected_file
    filename = manager.selected_file.name if manager.selected_file else ""
    extension = manager.selected_file.suffix.lower() if manager.selected_file else ""
    sample = manager.extract_upload_text_sample(
        analysis_file,
        max_chars=manager.openai_text_sample_chars(),
        max_pdf_pages=manager.openai_pdf_sample_pages(),
    ) if analysis_file else None
    try:
        suggestions = client.suggest_metadata(filename=filename, extension=extension, sample=sample)
        suggestions["keywords"] = _utm_limit_openai_keywords(
            str(suggestions.get("keywords", "")),
            reference_text=sample,
            max_keywords=30,
        )
        manager.openai_metadata_suggestions = suggestions
        manager.after(0, lambda: manager.upload_openai_text_var.set("OpenAI: Metadatenvorschläge bereit"))
        manager.after(0, lambda: manager.upload_openai_metadata_button.configure(state="normal"))
        manager.after(0, lambda: manager.upload_openai_usage_var.set(manager.format_openai_usage(suggestions.get("usage", {}))))
    except OpenAIError as exc:
        manager.after(0, lambda: manager.upload_openai_text_var.set(f"OpenAI: {exc.user_message()}"))
        manager.after(0, lambda: manager.upload_openai_metadata_button.configure(state="disabled"))
        manager.after(0, lambda: manager.upload_openai_usage_var.set("Verbrauch: k.A."))
    except Exception:
        manager.after(0, lambda: manager.upload_openai_text_var.set("OpenAI-Fehler"))
        manager.after(0, lambda: manager.upload_openai_metadata_button.configure(state="disabled"))
        manager.after(0, lambda: manager.upload_openai_usage_var.set("Verbrauch: k.A."))
