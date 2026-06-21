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
from .postprocess_place_utils import (
    admin_place_names_for_scan as _ppm_admin_place_names_for_scan,
    clean_place_context_text as _ppm_clean_place_context_text,
    compact_openai_place_contexts as _ppm_compact_openai_place_contexts,
    place_context_counts as _ppm_place_context_counts,
    find_place_contexts_in_text as _ppm_find_place_contexts_in_text,
)
from .upload_tab_metadata_utils import limit_openai_keywords as _utm_limit_openai_keywords


def admin_place_names_for_scan(manager: Any) -> list[str]:
    try:
        current = manager.place_var.get().strip()
    except Exception:
        current = ""
    return _ppm_admin_place_names_for_scan(manager.place_folder_map, current)


def find_place_contexts_in_text(text: str, places: list[str], context_chars: int = 650, max_contexts: int = 30) -> list[dict[str, str]]:
    return _ppm_find_place_contexts_in_text(text, places, context_chars=context_chars, max_contexts=max_contexts)


def clean_place_context_text(text: str) -> str:
    return _ppm_clean_place_context_text(text)


def admin_openai_place_scan_selected_document(manager: Any) -> None:
    item = manager.selected_admin_upload()
    path = manager.admin_selected_document_path()
    if not item or path is None:
        return
    places = manager.admin_place_names_for_scan()
    if not places:
        messagebox.showwarning("Orte prüfen", "Keine Orte aus der Ortsverwaltung gefunden.")
        return
    analysis_path = manager.existing_ocr_pdf_for_path(path) or path
    local_scan_text = manager.extract_upload_text_sample(
        analysis_path,
        max_chars=10_000_000,
        max_pdf_pages=10_000,
    )
    if not local_scan_text and path.suffix.lower() == ".pdf":
        messagebox.showwarning("Orte prüfen", "Dieses PDF ist lokal nicht lesbar. Bitte zuerst PDF OCR erstellen.")
        manager.update_admin_openai_controls()
        return
    place_context_chars = manager._read_int_config("openai_place_context_chars", 650, minimum=100, maximum=6000)
    place_max_contexts = manager._read_int_config("openai_place_max_contexts", 30, minimum=1, maximum=200)
    contexts = manager.find_place_contexts_in_text(local_scan_text or "", places, context_chars=place_context_chars, max_contexts=place_max_contexts)
    fallback_text = ""
    if not contexts:
        fallback_text = manager.extract_upload_text_sample(analysis_path, max_chars=manager.openai_text_sample_chars(), max_pdf_pages=manager.openai_pdf_sample_pages()) or ""
        selected_model = manager.confirm_admin_place_scan_openai(item, contexts, used_fallback=True)
        if not selected_model:
            manager.admin_openai_status_var.set("Orte prüfen: kein Ort lokal gefunden - OpenAI nicht gestartet")
            return
    else:
        selected_model = manager.confirm_admin_place_scan_openai(item, contexts, used_fallback=False)
    if not selected_model:
        found_places = ", ".join(manager.place_context_counts(contexts).keys())
        manager.admin_openai_status_var.set(f"Orte prüfen: lokal gefunden ({found_places}) - OpenAI nicht gestartet")
        return
    cached = manager.openai_cached_model_result(item, selected_model, "openai_place_model_results")
    if cached:
        result = cached.get("result") if isinstance(cached.get("result"), dict) else {}
        cached_contexts = cached.get("contexts") if isinstance(cached.get("contexts"), list) else contexts
        usage_text = str(cached.get("usage_text") or f"gespeichertes Ergebnis ({selected_model})")
        manager.show_admin_place_scan_result_dialog(
            item,
            result,
            cached_contexts,
            usage_text,
            used_fallback=bool(cached.get("used_fallback", not bool(cached_contexts))),
            model_name=selected_model,
        )
        manager.update_admin_openai_controls()
        return
    client = manager._openai_client_for_model(selected_model, warning_title="OpenAI")
    if client is None:
        return
    manager.admin_openai_places_button.configure(state="disabled")
    if contexts:
        manager.admin_openai_status_var.set(f"Orte prüfen: {len(contexts)} Fundstelle(n), OpenAI läuft ...")
    else:
        manager.admin_openai_status_var.set("Orte prüfen: kein Ort lokal gefunden, begrenzte Textprobe wird geprüft ...")

    def run() -> None:
        try:
            result = client.analyze_place_contexts(path.name, contexts, fallback_text=fallback_text, max_context_chars=(place_context_chars * 2 + 80))
            result["keywords"] = _utm_limit_openai_keywords(
                str(result.get("keywords", "")),
                reference_text=(fallback_text if fallback_text else local_scan_text),
                max_keywords=30,
            )
            usage_text = manager.format_openai_usage(result.get("usage", {}), model_name=client.model)
            manager.store_openai_model_result(item, client.model, "openai_place_model_results", {
                "result": result,
                "contexts": manager.compact_openai_place_contexts(contexts),
                "usage_text": usage_text,
                "used_fallback": not bool(contexts),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            })

            def apply() -> None:
                manager.show_admin_place_scan_result_dialog(
                    item,
                    result,
                    contexts,
                    usage_text,
                    used_fallback=not bool(contexts),
                    model_name=client.model,
                )
                manager.update_admin_openai_controls()

            manager.after(0, apply)
        except OpenAIError as exc:
            manager.after(0, lambda: manager.admin_openai_status_var.set(f"Orte prüfen: {exc.user_message()}"))
            manager.after(0, manager.update_admin_openai_controls)
        except Exception as exc:
            app_log_exception("Admin-OpenAI-Ortsprüfung fehlgeschlagen", exc, path=str(path))
            manager.after(0, lambda: manager.admin_openai_status_var.set("Orte prüfen: OpenAI-Fehler"))
            manager.after(0, manager.update_admin_openai_controls)

    threading.Thread(target=run, daemon=True).start()


def place_context_counts(manager: Any, contexts: list[dict[str, str]]) -> dict[str, int]:
    return _ppm_place_context_counts(contexts)


def confirm_admin_place_scan_openai(manager: Any, item: dict, contexts: list[dict[str, str]], used_fallback: bool = False) -> str:
    if used_fallback:
        intro = (
            "Es wurde kein Ort aus der Ortsverwaltung im lokal lesbaren Text gefunden.\n\n"
            "Soll OpenAI stattdessen mit der begrenzten Textprobe nach den OpenAI-Einstellungen fortfahren?"
        )
        list_text = "Keine Ortsfundstellen."
    else:
        counts = manager.place_context_counts(contexts)
        intro = (
            f"ODV hat lokal {len(contexts)} Fundstelle(n) zu {len(counts)} Ort(en) gefunden.\n\n"
            "Soll OpenAI mit diesen Fundstellen-Kontexten fortfahren?"
        )
        list_text = "\n".join(f"{place}: {count} Fundstelle(n)" for place, count in counts.items())
    return manager._resolve_openai_model_dialog_result(
        item=item,
        result_field="openai_place_model_results",
        legacy_model_field="openai_place_contexts_model",
        previous_time_field="openai_place_contexts_updated_at",
        used_fallback=used_fallback,
        accept_label="Mit OpenAI fortfahren",
        title_with_fallback="Keine Orte lokal gefunden",
        title_without="Orte lokal gefunden",
        intro_with_fallback=intro,
        intro_without=intro,
        list_text_getter=lambda: list_text,
    )


def compact_openai_place_contexts(manager: Any, contexts: list[dict[str, str]]) -> list[dict[str, str]]:
    return _ppm_compact_openai_place_contexts(contexts)


def show_admin_place_contexts_dialog(manager: Any) -> None:
    item = manager.selected_admin_upload()
    if not item:
        return
    contexts = item.get("openai_place_contexts") or []
    if not isinstance(contexts, list) or not contexts:
        messagebox.showinfo("Fundstellen", "Für dieses Dokument sind keine gespeicherten Ortsanalyse-Fundstellen vorhanden.")
        return
    updated_at = str(item.get("openai_place_contexts_updated_at") or "").strip() or "-"
    model_name = str(item.get("openai_place_contexts_model") or "").strip() or "-"
    grouped: dict[str, list[str]] = {}
    for context in contexts:
        if not isinstance(context, dict):
            continue
        place = str(context.get("place") or "Ohne Ort").strip() or "Ohne Ort"
        text = str(context.get("text") or "").strip()
        if text:
            grouped.setdefault(place, []).append(text)
    dialog = tk.Toplevel(manager)
    dialog.title("Gespeicherte Ortsanalyse-Fundstellen")
    dialog.transient(manager)
    dialog.geometry("900x650")
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(1, weight=1)
    ttk.Label(
        dialog,
        text=f"Gespeicherte Fundstellen: {sum(len(values) for values in grouped.values())} | Modell: {model_name} | Aktualisiert: {updated_at}",
        wraplength=860,
    ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
    text = tk.Text(dialog, wrap="word")
    text.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
    scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=text.yview)
    scrollbar.grid(row=1, column=1, sticky="ns", pady=4)
    text.configure(yscrollcommand=scrollbar.set)
    for place, snippets in sorted(grouped.items(), key=lambda item: item[0].casefold()):
        text.insert("end", f"{place}\n", ("heading",))
        for idx, snippet in enumerate(snippets, start=1):
            text.insert("end", f"{idx}. {snippet}\n\n")
    text.tag_configure("heading", font=("", 10, "bold"))
    text.configure(state="disabled")
    buttons = ttk.Frame(dialog)
    buttons.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 12))
    ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
    manager.wait_window(dialog)


def show_admin_place_scan_result_dialog(
    manager: Any,
    item: dict,
    result: dict,
    contexts: list[dict[str, str]],
    usage_text: str,
    used_fallback: bool = False,
    model_name: str = "",
) -> None:
    summary = str(result.get("summary") or "").strip()
    keywords = str(result.get("keywords") or "").strip()
    places = str(result.get("places") or "").strip() or ", ".join(dict.fromkeys(context.get("place", "") for context in contexts if context.get("place")))
    document_date = str(result.get("document_date") or "").strip()
    event = str(result.get("event") or "").strip()
    primary_source = str(result.get("primary_source") or "").strip()
    description_suggestion = f"enthält u.a. {summary}" if summary and not summary.lower().startswith("enthält u.a.") else summary
    dialog = tk.Toplevel(manager)
    dialog.title("OpenAI-Ortsanalyse")
    dialog.transient(manager)
    dialog.geometry("1180x720")
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(1, weight=1)
    mode_text = "Keine Ortsfundstelle lokal gefunden - begrenzte Textprobe nach OpenAI-Vorgaben geprüft" if used_fallback else f"Fundstellen: {len(contexts)}"
    model_text = str(model_name or "").strip() or "-"
    ttk.Label(dialog, text=f"Gefundene Orte: {places or '-'} | Modell: {model_text} | {mode_text} | {usage_text}\nJe Feld Aktion wählen; keine Auswahl bedeutet ignorieren.", wraplength=920).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
    body = ttk.Frame(dialog)
    body.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(2, weight=1)
    ttk.Label(body, text="Feldübernahme:").grid(row=0, column=0, sticky="w")
    rows = [
        ("document_date", "Datum / Zeitraum", manager.current_admin_openai_field_value("document_date"), document_date),
        ("event", "Ereignis", manager.current_admin_openai_field_value("event"), event),
        ("primary_source", "Primärquelle", manager.current_admin_openai_field_value("primary_source"), primary_source),
        ("description", "Beschreibung", manager.current_admin_openai_field_value("description"), description_suggestion),
        ("keywords", "Stichwörter", manager.current_admin_openai_field_value("keywords"), keywords),
        ("place", "Ort", manager.current_admin_openai_field_value("place"), places),
    ]
    rows = [(key, label, current, suggestion) for key, label, current, suggestion in rows if str(suggestion or "").strip()]
    transfer = ttk.Frame(body)
    transfer.grid(row=1, column=0, sticky="ew", pady=(2, 8))
    headers = ["Feld", "Aktueller Wert", "OpenAI-Vorschlag", "übernehmen", "überschreiben", "anhängen"]
    widths = [16, 28, 42, 12, 14, 10]
    for col, (header, width) in enumerate(zip(headers, widths)):
        ttk.Label(transfer, text=header, font=("", 9, "bold"), width=width).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 4))
    action_vars: dict[str, dict[str, tk.BooleanVar]] = {}
    for row_idx, (key, label, current, suggestion) in enumerate(rows, start=1):
        row_vars = {
            "take": tk.BooleanVar(value=not bool(str(current or "").strip())),
            "replace": tk.BooleanVar(value=False),
            "append": tk.BooleanVar(value=False),
        }
        action_vars[key] = row_vars
        row_height = max(manager._openai_display_height(current, wrap_at=58, max_lines=12), manager._openai_display_height(suggestion, wrap_at=58, max_lines=12))
        ttk.Label(transfer, text=label, width=16).grid(row=row_idx, column=0, sticky="nw", padx=4, pady=3)
        manager._readonly_text_widget(transfer, current or "-", width=30, height=row_height, background_source=dialog).grid(row=row_idx, column=1, sticky="nw", padx=4, pady=3)
        manager._readonly_text_widget(transfer, suggestion, width=62, height=row_height, background_source=dialog).grid(row=row_idx, column=2, sticky="nw", padx=4, pady=3)
        ttk.Checkbutton(transfer, variable=row_vars["take"], command=lambda vars=row_vars: manager._choose_openai_action(vars, "take")).grid(row=row_idx, column=3, sticky="n", padx=4, pady=3)
        ttk.Checkbutton(transfer, variable=row_vars["replace"], command=lambda vars=row_vars: manager._choose_openai_action(vars, "replace")).grid(row=row_idx, column=4, sticky="n", padx=4, pady=3)
        ttk.Checkbutton(transfer, variable=row_vars["append"], command=lambda vars=row_vars: manager._choose_openai_action(vars, "append")).grid(row=row_idx, column=5, sticky="n", padx=4, pady=3)

    ttk.Label(body, text="Verwendete lokale Fundstellen:").grid(row=2, column=0, sticky="w")
    contexts_text = tk.Text(body, height=9, wrap="word")
    contexts_text.grid(row=3, column=0, sticky="nsew", pady=(2, 0))
    if contexts:
        for idx, context in enumerate(contexts, start=1):
            contexts_text.insert("end", f"{idx}. {context.get('place', '')}\n{context.get('text', '')}\n\n")
    else:
        contexts_text.insert("end", "Keine lokale Ortsfundstelle. OpenAI hat die begrenzte Textprobe nach den OpenAI-Einstellungen ausgewertet.")
    contexts_text.configure(state="disabled")

    def apply_to_metadata() -> None:
        analysis_model = str(model_name or manager.config_data.get("openai_model", "") or "").strip()
        analysis_time = datetime.now().isoformat(timespec="seconds")
        changed = []
        for key, _label, current, suggestion in rows:
            selected = [action_name for action_name, var in action_vars[key].items() if var.get()]
            action = selected[0] if selected else ""
            if not action:
                continue
            new_value = manager.admin_openai_value_for_action(key, current, suggestion, action)
            if new_value != current:
                manager.set_admin_openai_field_value(key, new_value)
                changed.append(key)
        if changed:
            previous_fields = [str(field) for field in (item.get("openai_metadata_fields", []) or []) if str(field).strip()]
            item["openai_metadata_fields"] = list(dict.fromkeys(previous_fields + changed))
            item["openai_metadata_model"] = analysis_model
            item["openai_metadata_applied_at"] = datetime.now().isoformat(timespec="seconds")
            item["openai_place_contexts_model"] = analysis_model
            item["openai_place_contexts_updated_at"] = analysis_time
            if contexts:
                item["openai_place_contexts"] = manager.compact_openai_place_contexts(contexts)
            append_metadata_history(item, manager.display_name_var.get().strip() or "Admin", "OpenAI-Ortsanalyse übernommen", f"Felder: {', '.join(changed)}; Orte: {places}")
            manager.persist_admin_openai_form_item(item)
            api_ok, api_msg = manager.save_admin_openai_item_to_storage(item)
            if api_ok:
                manager.update_admin_tree_row_for_item(item)
                manager.update_admin_openai_controls()
                manager.admin_openai_status_var.set(f"Ortsanalyse übernommen und gespeichert: {', '.join(changed)}")
            else:
                manager.update_admin_openai_controls()
                manager.admin_openai_status_var.set(f"Ortsanalyse lokal übernommen; MySQL nicht gespeichert: {api_msg}")
        else:
            item["openai_place_contexts_model"] = analysis_model
            item["openai_place_contexts_updated_at"] = analysis_time
            if contexts:
                item["openai_place_contexts"] = manager.compact_openai_place_contexts(contexts)
            api_ok, api_msg = manager.save_admin_openai_item_to_storage(item)
            if api_ok:
                manager.update_admin_tree_row_for_item(item)
                manager.update_admin_openai_controls()
                manager.admin_openai_status_var.set("Ortsanalyse gespeichert: keine Felder übernommen")
            else:
                manager.update_admin_openai_controls()
                manager.admin_openai_status_var.set(f"Ortsanalyse lokal gespeichert; MySQL nicht aktualisiert: {api_msg}")
        dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.grid(row=2, column=0, sticky="e", padx=12, pady=(8, 12))
    ttk.Button(buttons, text="Auswahl übernehmen", command=apply_to_metadata).pack(side="left", padx=4)
    ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
    manager.wait_window(dialog)
