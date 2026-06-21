from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk, messagebox


def openai_model_options(manager: Any, item: dict, result_field: str, legacy_field: str) -> list[str]:
    current_model = manager._openai_default_model()
    used_models = manager.openai_used_models(item, result_field, legacy_field)
    model_values: list[str] = []
    for model in (current_model, *manager._OPENAI_FALLBACK_MODELS):
        if model and model not in model_values:
            model_values.append(model)
    for model in used_models:
        if model and model not in model_values:
            model_values.append(model)
    return model_values


def choose_openai_action(row_vars: dict[str, tk.BooleanVar], selected_action: str) -> None:
    if not row_vars.get(selected_action) or not row_vars[selected_action].get():
        return
    for action_name, var in row_vars.items():
        if action_name != selected_action:
            var.set(False)


def readonly_text_widget(parent: tk.Widget, value: str, width: int, height: int, background_source: tk.Widget | None = None) -> tk.Text:
    source = background_source or parent
    source_background = ""
    if source is not None:
        source_background = source.cget("background")
    text_widget = tk.Text(
        parent,
        width=width,
        height=height,
        wrap="word",
        relief="flat",
        borderwidth=0,
        background=source_background,
        font=("TkDefaultFont", 9),
    )
    text_widget.insert("1.0", value or "-")
    text_widget.configure(state="disabled")
    return text_widget


def openai_display_height(value: str, wrap_at: int = 55, max_lines: int = 10, fallback: int = 1) -> int:
    text = str(value or "")
    line_count = max(fallback, len(text.splitlines()))
    estimated_wrap_lines = max(fallback, (len(text) + max(1, wrap_at - 1)) // max(1, wrap_at))
    return min(max_lines, max(line_count, estimated_wrap_lines))


def resolve_openai_model_dialog_result(
    manager: Any,
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
    used_models = manager.openai_used_models(item, result_field, legacy_model_field)
    previous_model = ", ".join(used_models)
    previous_time = str(item.get(previous_time_field) or "").strip() or "-"
    model_values = openai_model_options(manager, item, result_field, legacy_model_field)
    current_model = manager._openai_default_model()

    dialog = tk.Toplevel(manager)
    dialog.title(title_with_fallback if used_fallback else title_without)
    dialog.transient(manager)
    dialog.geometry("560x470")
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(2, weight=1)

    intro = intro_with_fallback if used_fallback else intro_without
    list_text = "Keine Ortsfundstellen." if used_fallback else list_text_getter()

    ttk.Label(dialog, text=f"{intro}", wraplength=520).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
    model_frame = ttk.Frame(dialog)
    model_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
    model_frame.columnconfigure(1, weight=1)
    ttk.Label(model_frame, text="OpenAI-Modell:").grid(row=0, column=0, sticky="w")
    model_var = tk.StringVar(value=current_model)
    ttk.Combobox(model_frame, textvariable=model_var, values=model_values, state="readonly", width=28).grid(row=0, column=1, sticky="ew", padx=(8, 0))
    ttk.Label(dialog, text=f"Bisherig verwendet: {previous_model}").grid(row=2, column=0, sticky="w", padx=12)
    ttk.Label(dialog, text=f"Letzter Stand: {previous_time}").grid(row=3, column=0, sticky="w", padx=12)
    info_var = tk.StringVar(value="")
    ttk.Label(dialog, textvariable=info_var, foreground="#555555", wraplength=520).grid(row=4, column=0, sticky="w", padx=12, pady=(4, 0))
    text = tk.Text(dialog, height=12, wrap="word")
    text.grid(row=2, column=0, sticky="nsew", padx=12, pady=4)
    text.insert("1.0", list_text)
    text.configure(state="disabled")
    result = {"model": ""}

    def accept() -> None:
        result["model"] = model_var.get().strip()
        dialog.destroy()

    def refresh_info(*_args) -> None:
        selected = model_var.get().strip()
        cached = bool(manager.openai_cached_model_result(item, selected, result_field))
        if cached:
            info_var.set(f"Dieses Dokument wurde mit diesem Modell bereits verarbeitet ({previous_time}). Gespeicherte Vorschläge werden angezeigt.")
            continue_button.configure(text="Gespeicherte Vorschläge anzeigen", state="normal")
        else:
            info_var.set("OpenAI startet erst nach Bestätigung und verursacht Kosten.")
            continue_button.configure(text=accept_label, state="normal")

    buttons = ttk.Frame(dialog)
    buttons.grid(row=5, column=0, sticky="e", padx=12, pady=(8, 12))
    continue_button = ttk.Button(buttons, text=accept_label, command=accept)
    continue_button.pack(side="left", padx=4)
    ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
    model_var.trace_add("write", refresh_info)
    refresh_info()
    manager.wait_window(dialog)
    return result["model"]
