from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox


DEFAULT_MANUAL_BONUS_RULES = [
    ("manual_archive_research", "Recherche in Archiven", 0),
    ("manual_collection_indexing", "Erschließung von Beständen", 0),
    ("manual_event_organization", "Organisation Veranstaltung", 0),
    ("manual_excursion_organization", "Organisation Busfahrt / Exkursion", 0),
    ("manual_exhibition_work", "Mitarbeit an Ausstellung", 0),
    ("manual_digitization_support", "Digitalisierungshilfe", 0),
    ("manual_lecture_guided_tour", "Vortrag / Führung", 0),
    ("manual_other", "Sonstige Tätigkeit", 0),
]


class PointsSpecialManagerMixin:
    def open_manual_points_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Sonderpunkte sind Admins vorbehalten.")
            return
        item = None
        try:
            item = self.selected_admin_upload()
        except Exception:
            item = None
        if not item or not item.get("upload_id"):
            messagebox.showwarning("Sonderpunkte", "Bitte im Reiter 'Dateien bearbeiten' zuerst ein Dokument auswählen.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Sonderpunkte ist eine API-Anmeldung erforderlich.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Sonderpunkte vergeben")
        try:
            self.track_window_geometry(dialog, "Sonderpunkte vergeben")
        except Exception:
            pass
        dialog.geometry("760x430")
        dialog.transient(self)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(5, weight=1)
        ttk.Label(dialog, text=f"Dokument: {item.get('current_filename') or item.get('original_filename')}").grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 6))

        users_resp = self.api.list_users(self.api_token)
        users = users_resp.get("users", []) or []
        user_map = {f"{u.get('display_name')} ({u.get('username')})": int(u.get('id')) for u in users if int(u.get('is_active', 1)) == 1}
        user_var = tk.StringVar(value=next(iter(user_map.keys()), ""))

        bonus_rules = []
        try:
            rules_resp = self.api.list_point_rules(self.api_token, self._current_points_year())
            for rule in rules_resp.get("rules", []) or []:
                if str(rule.get("category", "")).strip() in {"manual", "manual_bonus"} and int(rule.get("is_active", 1)) == 1:
                    bonus_rules.append(rule)
        except Exception:
            bonus_rules = []
        if not bonus_rules:
            bonus_rules = [
                {"rule_key": key, "label": label, "points": points, "category": "manual_bonus"}
                for key, label, points in DEFAULT_MANUAL_BONUS_RULES
            ]
        bonus_labels = [f"{r.get('label', r.get('rule_key'))} ({int(r.get('points', 0))} Punkte)" for r in bonus_rules]
        bonus_map = {bonus_labels[i]: bonus_rules[i] for i in range(len(bonus_rules))}
        bonus_var = tk.StringVar(value=bonus_labels[0] if bonus_labels else "")
        points_var = tk.StringVar(value=str(int(bonus_rules[0].get("points", 0))) if bonus_rules else "0")
        reason_text = tk.Text(dialog, height=8, wrap="word")

        ttk.Label(dialog, text="Empfänger:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        ttk.Combobox(dialog, textvariable=user_var, values=list(user_map.keys()), state="readonly").grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        ttk.Label(dialog, text="Leistungsart:").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        bonus_combo = ttk.Combobox(dialog, textvariable=bonus_var, values=bonus_labels, state="readonly")
        bonus_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=4)
        ttk.Label(dialog, text="Punkte:").grid(row=3, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(dialog, textvariable=points_var, width=8).grid(row=3, column=1, sticky="w", padx=10, pady=4)
        ttk.Label(dialog, text="Begründung:").grid(row=4, column=0, sticky="nw", padx=10, pady=4)
        reason_text.grid(row=4, column=1, sticky="nsew", padx=10, pady=4)
        ttk.Label(dialog, text="Hinweis: Manuell vergebene Punkte müssen begründet werden. Bei 'Besondere Zuarbeit' bitte Punkte bewusst festlegen.", foreground="#555555").grid(row=5, column=1, sticky="w", padx=10, pady=(0, 4))

        def on_bonus_selected(_event=None):
            rule = bonus_map.get(bonus_var.get())
            if rule:
                points_var.set(str(int(rule.get("points", 0))))
                if not reason_text.get("1.0", "end").strip():
                    reason_text.insert("1.0", str(rule.get("label", "")))

        bonus_combo.bind("<<ComboboxSelected>>", on_bonus_selected)
        on_bonus_selected()

        def save_manual():
            try:
                user_id = user_map.get(user_var.get())
                if not user_id:
                    raise ValueError("Bitte einen Benutzer auswählen.")
                reason = reason_text.get("1.0", "end").strip()
                if not reason:
                    raise ValueError("Bitte eine Begründung erfassen.")
                points = int(points_var.get())
                if points == 0:
                    raise ValueError("Bitte eine Punktzahl ungleich 0 erfassen.")
                rule = bonus_map.get(bonus_var.get()) or {}
                category = str(rule.get("category") or "manual_bonus")
                rule_key = str(rule.get("rule_key") or "")
                source_field = self.point_rule_source_field_from_key(rule_key)
                label = str(rule.get("label") or "Sonderpunkte")
                full_reason = f"{label}: {reason}" if not reason.startswith(label) else reason
                self.api.add_manual_points(self.api_token, str(item.get("upload_id")), user_id, points, full_reason, category, rule_key=rule_key, source_field=source_field)
                self.update_admin_document_points_display(str(item.get("upload_id", "")))
                messagebox.showinfo("Sonderpunkte", "Sonderpunkte wurden gespeichert.")
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc))

        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=6, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="Speichern", command=save_manual).pack(side="left")
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="right")

    def open_points_settings_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Punkte-Einstellungen dürfen nur Superadmins ändern.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Punkte-Einstellungen ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Punkte-Einstellungen")
        try:
            self.track_window_geometry(dialog, "Punkte-Einstellungen")
        except Exception:
            pass
        dialog.geometry("520x180")
        dialog.transient(self)
        dialog.columnconfigure(1, weight=1)
        points_per_hour_var = tk.StringVar(value="150")
        try:
            resp = self.api.get_manual_points_settings(self.api_token)
            points_per_hour_var.set(str(resp.get("points_per_hour", 150)))
        except Exception:
            points_per_hour_var.set("150")
        ttk.Label(dialog, text="Standardpunkte pro Stunde für manuelle Sonderpunkte:").grid(row=0, column=0, sticky="w", padx=10, pady=(14, 6))
        ttk.Entry(dialog, textvariable=points_per_hour_var, width=10).grid(row=0, column=1, sticky="w", padx=10, pady=(14, 6))
        ttk.Label(dialog, text="Wird ein Zeitaufwand erfasst, berechnet ODV daraus einen Punktvorschlag.\nDie Punkte bleiben vor dem Speichern manuell änderbar.", foreground="#555555").grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=6)

        def save():
            try:
                val = int(float(points_per_hour_var.get().replace(",", ".")))
                if val <= 0:
                    raise ValueError("Bitte einen positiven Wert erfassen.")
                self.api.save_manual_points_settings(self.api_token, val)
                messagebox.showinfo("Punkte-Einstellungen", "Einstellungen wurden gespeichert.", parent=dialog)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Punkte-Einstellungen", str(exc), parent=dialog)

        buttons = ttk.Frame(dialog, padding=10)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="Speichern", command=save).pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")

    def point_rule_source_field_from_key(self, rule_key: str) -> str:
        key = str(rule_key or "").strip()
        for suffix in ("_metadata", "_metadaten", "_manual", "_openAI"):
            if key.endswith(suffix):
                key = key[:-len(suffix)]
                break
        aliases = {
            "metadata_description": "description",
            "metadata_keywords": "keywords",
            "metadata_source": "source",
            "rights_author": "copyright_author",
            "rights_usage_permission": "usage_permission",
            "event_topic": "event",
            "openai_metadata": "openai_metadata",
            "persons_image_marked": "persons",
            "persons_per_person": "persons",
        }
        return aliases.get(key, key or "manual_bonus")

    def _manual_rule_options(self, year: int) -> tuple[list[str], dict[str, dict]]:
        rules = []
        try:
            resp = self.api.list_point_rules(self.api_token, int(year))
            for rule in resp.get("rules", []) or []:
                if str(rule.get("category", "")).strip() == "manual" and int(rule.get("is_active", 1)) == 1:
                    rules.append(rule)
        except Exception:
            rules = []
        if not rules:
            rules = [{"rule_key": key, "label": label, "points": points, "category": "manual"} for key, label, points in DEFAULT_MANUAL_BONUS_RULES]
        labels = [f"{r.get('label', r.get('rule_key'))} [{r.get('rule_key')}]" for r in rules]
        return labels, {labels[i]: rules[i] for i in range(len(rules))}

    def open_manual_special_points_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Manuelle Sonderpunkte sind Admins vorbehalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für manuelle Sonderpunkte ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Sonderpunkte für Ortschronisten")
        try:
            self.track_window_geometry(dialog, "Sonderpunkte für Ortschronisten")
        except Exception:
            pass
        dialog.geometry("860x560")
        dialog.transient(self)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(6, weight=1)

        users_resp = self.api.list_users(self.api_token)
        users = users_resp.get("users", []) or []
        user_map = {f"{u.get('display_name')} ({u.get('username')})": int(u.get('id')) for u in users if int(u.get('is_active', 1)) == 1}
        user_var = tk.StringVar(value=next(iter(user_map.keys()), ""))
        year = self._current_points_year()
        rule_labels, rule_map = self._manual_rule_options(year)
        rule_var = tk.StringVar(value=rule_labels[0] if rule_labels else "")
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        hours_var = tk.StringVar()
        points_var = tk.StringVar()
        pph_var = tk.StringVar(value="150")
        try:
            settings = self.api.get_manual_points_settings(self.api_token)
            pph_var.set(str(settings.get("points_per_hour", 150)))
        except Exception:
            pass
        reason_text = tk.Text(dialog, height=6, wrap="word")
        note_text = tk.Text(dialog, height=4, wrap="word")

        ttk.Label(dialog, text="Ortschronist:").grid(row=0, column=0, sticky="w", padx=10, pady=(12, 4))
        ttk.Combobox(dialog, textvariable=user_var, values=list(user_map.keys()), state="readonly").grid(row=0, column=1, sticky="ew", padx=10, pady=(12, 4))
        ttk.Label(dialog, text="Tätigkeit / Regel:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        rule_combo = ttk.Combobox(dialog, textvariable=rule_var, values=rule_labels, state="readonly")
        rule_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        ttk.Label(dialog, text="Datum der Tätigkeit:").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(dialog, textvariable=date_var, width=14).grid(row=2, column=1, sticky="w", padx=10, pady=4)
        row3 = ttk.Frame(dialog)
        row3.grid(row=3, column=1, sticky="w", padx=10, pady=4)
        ttk.Label(dialog, text="Zeitaufwand / Punkte:").grid(row=3, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(row3, textvariable=hours_var, width=10).pack(side="left")
        ttk.Label(row3, text=" Stunden × ").pack(side="left")
        ttk.Entry(row3, textvariable=pph_var, width=7).pack(side="left")
        ttk.Label(row3, text=" Punkte/Stunde = ").pack(side="left")
        ttk.Entry(row3, textvariable=points_var, width=9).pack(side="left")
        ttk.Label(dialog, text="Beschreibung / Begründung:").grid(row=4, column=0, sticky="nw", padx=10, pady=4)
        reason_text.grid(row=4, column=1, sticky="nsew", padx=10, pady=4)
        ttk.Label(dialog, text="Bemerkung / Beleg:").grid(row=5, column=0, sticky="nw", padx=10, pady=4)
        note_text.grid(row=5, column=1, sticky="nsew", padx=10, pady=4)
        ttk.Label(dialog, text="Wenn ein Zeitaufwand eingetragen ist, berechnet ODV automatisch einen Vorschlag. Punkte können vor dem Speichern geändert werden.", foreground="#555555").grid(row=6, column=1, sticky="w", padx=10, pady=(0, 4))

        def recalc_points(*_):
            try:
                htxt = hours_var.get().strip().replace(",", ".")
                if not htxt:
                    rule = rule_map.get(rule_var.get()) or {}
                    default_points = int(rule.get("points", 0) or 0)
                    if default_points and not points_var.get().strip():
                        points_var.set(str(default_points))
                    return
                hours = float(htxt)
                pph = int(float(pph_var.get().strip().replace(",", ".") or "150"))
                points_var.set(str(int(round(hours * pph))))
            except Exception:
                pass

        hours_var.trace_add("write", recalc_points)
        pph_var.trace_add("write", recalc_points)
        rule_combo.bind("<<ComboboxSelected>>", lambda e: recalc_points())
        recalc_points()

        def save():
            try:
                uid = user_map.get(user_var.get())
                if not uid:
                    raise ValueError("Bitte einen Benutzer auswählen.")
                rule = rule_map.get(rule_var.get()) or {}
                rule_key = str(rule.get("rule_key") or "manual_other")
                reason = reason_text.get("1.0", "end").strip()
                note = note_text.get("1.0", "end").strip()
                if not reason:
                    raise ValueError("Bitte eine Beschreibung/Begründung erfassen.")
                points = int(float(points_var.get().strip().replace(",", ".")))
                if points == 0:
                    raise ValueError("Bitte Punkte ungleich 0 erfassen.")
                hours = None
                if hours_var.get().strip():
                    hours = float(hours_var.get().strip().replace(",", "."))
                self.api.add_manual_special_points(self.api_token, uid, rule_key, points, reason, activity_date=date_var.get().strip(), hours=hours, note=note)
                messagebox.showinfo("Sonderpunkte", "Manuelle Sonderpunkte wurden gespeichert.", parent=dialog)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc), parent=dialog)

        buttons = ttk.Frame(dialog, padding=10)
        buttons.grid(row=7, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="Speichern", command=save).pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")

    def open_manual_special_points_overview_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Diese Übersicht ist Admins vorbehalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für diese Übersicht ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Übersicht manuelle Sonderpunkte")
        try:
            self.track_window_geometry(dialog, "Übersicht manuelle Sonderpunkte")
        except Exception:
            pass
        dialog.geometry("1200x680")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Kalenderjahr:").pack(side="left")
        year_var = tk.StringVar(value=str(self._current_points_year()))
        ttk.Entry(top, textvariable=year_var, width=8).pack(side="left", padx=6)
        cols = ("date", "user", "place", "rule", "hours", "points", "reason", "created_by", "created_at")
        tree = ttk.Treeview(dialog, columns=cols, show="headings")
        widths = {"date": 110, "user": 190, "place": 120, "rule": 240, "hours": 90, "points": 80, "reason": 340, "created_by": 180, "created_at": 150}
        labels = {"date": "Datum", "user": "Ortschronist", "place": "Ort", "rule": "Tätigkeit", "hours": "Stunden", "points": "Punkte", "reason": "Begründung", "created_by": "Vergeben von", "created_at": "Erfasst am"}
        for c in cols:
            tree.heading(c, text=labels[c], anchor="w")
            tree.column(c, width=widths[c], anchor="w", stretch=True)
        tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(dialog, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew", padx=8)

        def load():
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                resp = self.api.list_manual_special_points(self.api_token, int(year_var.get()))
                for row in resp.get("items", []) or []:
                    tree.insert("", "end", values=(row.get("activity_date", ""), row.get("user_display_name", ""), row.get("place", ""), row.get("rule_label", row.get("rule_key", "")), row.get("hours", ""), row.get("points", 0), row.get("reason", ""), row.get("created_by_name", ""), row.get("created_at", "")))
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc), parent=dialog)

        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Button(top, text="Aktualisieren", command=load).pack(side="left", padx=8)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load()
