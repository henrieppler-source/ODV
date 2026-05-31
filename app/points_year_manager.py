from __future__ import annotations

import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class PointsYearManagerMixin:
    def _current_points_year(self) -> int:
        return datetime.now().year

    def open_points_summary_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Auswertungen sind Admins vorbehalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für die Auswertung ist eine API-Anmeldung erforderlich.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Beitragsauswertung")
        try:
            self.track_window_geometry(dialog, "Beitragsauswertung")
        except Exception:
            pass
        dialog.geometry("980x620")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(2, weight=1)

        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(5, weight=1)
        ttk.Label(top, text="Kalenderjahr:").grid(row=0, column=0, sticky="w")
        year_var = tk.StringVar(value=str(self._current_points_year()))
        year_entry = ttk.Entry(top, textvariable=year_var, width=8)
        year_entry.grid(row=0, column=1, sticky="w", padx=(6, 10))
        ttk.Button(top, text="Laden", command=lambda: load_state()).grid(row=0, column=2, sticky="w", padx=(0, 16))
        status_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=status_var, foreground="#444444").grid(row=0, column=3, sticky="w")

        budget_frame = ttk.Frame(dialog, padding=(8, 0, 8, 4))
        budget_frame.grid(row=1, column=0, sticky="ew")
        for idx in range(8):
            budget_frame.columnconfigure(idx, weight=1 if idx in (1, 3, 5, 7) else 0)

        ttk.Label(budget_frame, text="Prämienbetrag:").grid(row=0, column=0, sticky="w")
        budget_var = tk.StringVar(value="")
        budget_entry = ttk.Entry(budget_frame, textvariable=budget_var, width=12)
        budget_entry.grid(row=0, column=1, sticky="w", padx=(6, 16))
        ttk.Label(budget_frame, text="Wert je Punkt:").grid(row=0, column=2, sticky="w")
        value_per_point_var = tk.StringVar(value="0,00")
        ttk.Label(budget_frame, textvariable=value_per_point_var, foreground="#444444").grid(row=0, column=3, sticky="w", padx=(6, 16))
        ttk.Label(budget_frame, text="Gesamtpunkte:").grid(row=0, column=4, sticky="w")
        total_points_var = tk.StringVar(value="0")
        ttk.Label(budget_frame, textvariable=total_points_var, foreground="#444444").grid(row=0, column=5, sticky="w", padx=(6, 16))
        ttk.Label(budget_frame, text="Teilnehmer:").grid(row=0, column=6, sticky="w")
        participant_count_var = tk.StringVar(value="0")
        ttk.Label(budget_frame, textvariable=participant_count_var, foreground="#444444").grid(row=0, column=7, sticky="w", padx=(6, 0))

        tree = ttk.Treeview(
            dialog,
            columns=("user", "place", "upload", "metadata", "persons", "admin", "manual", "total"),
            show="headings",
        )
        for col, label, width in [
            ("user", "Benutzer", 220),
            ("place", "Ort", 120),
            ("upload", "Upload", 70),
            ("metadata", "Metadaten", 90),
            ("persons", "Personen", 80),
            ("admin", "Admin", 70),
            ("manual", "Sonder", 70),
            ("total", "Gesamt", 80),
        ]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=2, column=1, sticky="ns")

        rows_cache: list[dict] = []
        year_state: dict[str, object] = {}
        load_pending: dict[str, object] = {}

        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=3, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=0)
        buttons.columnconfigure(2, weight=0)
        buttons.columnconfigure(3, weight=0)
        buttons.columnconfigure(4, weight=0)
        buttons.columnconfigure(5, weight=0)

        def fmt_budget(value: float) -> str:
            return f"{value:.2f}".replace(".", ",")

        def update_controls() -> None:
            closed = bool(year_state.get("closed"))
            closed_text = ""
            if closed:
                closed_at = str(year_state.get("closed_at") or "")
                closed_by = str(year_state.get("closed_by_name") or "")
                closed_text = f"Abgeschlossen"
                if closed_at:
                    closed_text += f" am {closed_at}"
                if closed_by:
                    closed_text += f" durch {closed_by}"
            else:
                closed_text = "Offen"
            status_var.set(closed_text)
            if closed:
                budget_entry.configure(state="disabled")
                save_budget_button.configure(state="disabled")
                close_year_button.configure(state="disabled")
                reopen_year_button.configure(state="normal")
            else:
                budget_entry.configure(state="normal")
                save_budget_button.configure(state="normal")
                close_year_button.configure(state="normal")
                reopen_year_button.configure(state="disabled")

        def load_summary() -> None:
            nonlocal rows_cache
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                resp = self.api.points_summary(self.api_token, int(year_var.get()))
                rows_cache = resp.get("summary", []) or []
                for row in rows_cache:
                    tree.insert(
                        "",
                        "end",
                        values=(
                            row.get("user_display_name", ""),
                            row.get("place", ""),
                            row.get("upload_points", 0),
                            row.get("metadata_points", 0),
                            row.get("persons_points", 0),
                            row.get("admin_points", 0),
                            row.get("manual_points", 0),
                            row.get("total_points", 0),
                        ),
                    )
            except Exception as exc:
                messagebox.showerror("Beitragsauswertung", str(exc))

        def schedule_load() -> None:
            try:
                old_after = load_pending.get("after_id")
                if old_after:
                    try:
                        dialog.after_cancel(old_after)
                    except Exception:
                        pass
                load_pending["after_id"] = dialog.after(150, load_state)
            except Exception:
                load_state()

        def load_state() -> None:
            try:
                year = int(year_var.get())
            except Exception:
                return
            try:
                resp = self.api.points_year_status(self.api_token, year)
                year_state.clear()
                year_state.update(resp)
                budget_var.set(fmt_budget(float(resp.get("budget", 0) or 0)))
                total_points_var.set(str(int(resp.get("total_points", 0) or 0)))
                participant_count_var.set(str(int(resp.get("participant_count", 0) or 0)))
                value_per_point_var.set(fmt_budget(float(resp.get("value_per_point", 0) or 0)))
                update_controls()
                load_summary()
            except Exception as exc:
                messagebox.showerror("Beitragsauswertung", str(exc))

        def save_budget() -> None:
            try:
                year = int(year_var.get())
            except Exception:
                messagebox.showwarning("Beitragsauswertung", "Bitte ein gültiges Kalenderjahr eingeben.")
                return
            try:
                resp = self.api.set_points_year_budget(self.api_token, year, budget_var.get().strip())
                budget_var.set(fmt_budget(float(resp.get("budget", 0) or 0)))
                load_state()
            except Exception as exc:
                messagebox.showerror("Beitragsauswertung", str(exc))

        def close_year() -> None:
            if not messagebox.askyesno("Jahr abschließen", "Soll dieses Punktejahr wirklich abgeschlossen werden?"):
                return
            try:
                self.api.close_points_year(self.api_token, int(year_var.get()))
                load_state()
            except Exception as exc:
                messagebox.showerror("Beitragsauswertung", str(exc))

        def reopen_year() -> None:
            if not messagebox.askyesno("Jahr wieder öffnen", "Soll das Punktejahr wieder freigegeben werden?"):
                return
            try:
                self.api.reopen_points_year(self.api_token, int(year_var.get()))
                load_state()
            except Exception as exc:
                messagebox.showerror("Beitragsauswertung", str(exc))

        def export_csv() -> None:
            if not rows_cache:
                messagebox.showinfo("Export", "Keine Daten zum Export vorhanden.")
                return
            path = filedialog.asksaveasfilename(title="CSV exportieren", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not path:
                return
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Benutzer", "Ort", "Upload", "Metadaten", "Personen", "Admin", "Sonder", "Gesamt"])
                for row in rows_cache:
                    writer.writerow([
                        row.get("user_display_name", ""),
                        row.get("place", ""),
                        row.get("upload_points", 0),
                        row.get("metadata_points", 0),
                        row.get("persons_points", 0),
                        row.get("admin_points", 0),
                        row.get("manual_points", 0),
                        row.get("total_points", 0),
                    ])
            messagebox.showinfo("Export", f"CSV wurde gespeichert:\n{path}")

        save_budget_button = ttk.Button(buttons, text="Prämienbetrag speichern", command=save_budget)
        save_budget_button.pack(side="left")
        reopen_year_button = ttk.Button(buttons, text="Jahr wieder öffnen", command=reopen_year)
        reopen_year_button.pack(side="left", padx=(8, 0))
        close_year_button = ttk.Button(buttons, text="Jahr abschließen", command=close_year)
        close_year_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="CSV exportieren", command=export_csv).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")

        try:
            year_var.trace_add("write", lambda *_: schedule_load())
        except Exception:
            pass

        load_state()
