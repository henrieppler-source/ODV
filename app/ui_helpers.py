from __future__ import annotations

import tkinter as tk


def reset_tk_var(var: tk.Variable) -> None:
    try:
        if isinstance(var, tk.BooleanVar):
            var.set(False)
        else:
            var.set("")
    except Exception:
        pass


def clear_text_widget(widget: tk.Text, placeholder: str | None = None, disable_after: bool = True) -> None:
    try:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if placeholder is not None:
            widget.insert("1.0", placeholder)
        if disable_after:
            widget.configure(state="disabled")
    except Exception:
        pass


def clear_tree_selection(tree: tk.Widget) -> None:
    try:
        tree.selection_remove(tree.selection())
    except Exception:
        pass
