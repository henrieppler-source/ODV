from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .app_logging import app_log_exception


class SystemStatusMixin:
    def open_system_status_dialog(self) -> None:
        """Zeigt den ausführlichen Betriebsstatus auf Wunsch über das Hilfe-Menü."""
        try:
            lines = self.startup_system_check_lines()
            dialog = tk.Toplevel(self)
            dialog.title("ODV-Systemstatus")
            try:
                self.track_window_geometry(dialog, "ODV-Systemstatus")
            except Exception:
                pass
            dialog.transient(self)
            dialog.resizable(True, True)
            dialog.columnconfigure(0, weight=1)
            dialog.rowconfigure(0, weight=1)
            frame = ttk.Frame(dialog, padding=14)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            ttk.Label(frame, text="Systemstatus", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
            text = tk.Text(frame, width=92, height=min(18, max(8, len(lines) + 1)), wrap="word")
            text.grid(row=1, column=0, sticky="nsew")
            text.insert("1.0", "\n".join(lines))
            text.configure(state="disabled")
            buttons = ttk.Frame(frame)
            buttons.grid(row=2, column=0, sticky="e", pady=(8, 0))
            ttk.Button(buttons, text="Aktualisieren", command=lambda: self.refresh_system_status_text(text)).pack(side="left", padx=4)
            ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
            dialog.update_idletasks()
            x = self.winfo_rootx() + max(60, (self.winfo_width() - dialog.winfo_width()) // 2)
            y = self.winfo_rooty() + 80
            dialog.geometry(f"+{x}+{y}")
        except Exception as exc:
            app_log_exception("Systemstatus konnte nicht angezeigt werden", exc)

    def refresh_system_status_text(self, text: tk.Text) -> None:
        lines = self.startup_system_check_lines()
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")
