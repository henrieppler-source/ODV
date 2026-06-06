from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox


class AdminPointsDetailManagerMixin:
    def open_document_points_detail_dialog(self) -> None:
        item = self.selected_admin_upload()
        if not item or not item.get("upload_id"):
            messagebox.showwarning("Punkte", "Bitte zuerst ein Dokument auswählen.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Punkte ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Punkte des Dokuments")
        try:
            self.track_window_geometry(dialog, "Punkte des Dokuments")
        except Exception:
            pass
        dialog.geometry("900x480")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(dialog, text=f"Dokument: {item.get('current_filename') or item.get('original_filename')}").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        tree = ttk.Treeview(dialog, columns=("date", "user", "cat", "reason", "points"), show="headings")
        for col, label, width in [("date", "Datum", 140), ("user", "Benutzer", 180), ("cat", "Kategorie", 120), ("reason", "Grund", 330), ("points", "Punkte", 70)]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=1, column=1, sticky="ns", pady=6)
        try:
            resp = self.api.document_points(self.api_token, str(item.get("upload_id")))
            for row in resp.get("points", []) or []:
                tree.insert("", "end", values=(row.get("created_at", ""), row.get("user_display_name", ""), row.get("category", ""), row.get("reason", ""), row.get("points", 0)))
        except Exception as exc:
            messagebox.showerror("Punkte", str(exc), parent=dialog)
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
        if self.is_current_admin():
            ttk.Button(buttons, text="Sonderpunkte erfassen...", command=lambda: self.open_manual_points_dialog(item=self.selected_admin_upload())).pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
