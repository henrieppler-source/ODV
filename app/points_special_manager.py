from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from .file_service import append_metadata_history


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
    def open_manual_points_dialog(self, item: dict | None = None) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Sonderpunkte sind Admins vorbehalten.")
            return
        if item is None:
            item = getattr(self, "file_view_current_metadata", None) or None
        if not item or not item.get("upload_id"):
            path = getattr(self, "file_view_current_path", None)
            if path and path.exists() and not path.is_dir():
                try:
                    item, metadata_file = self.ensure_file_view_metadata_item(path)
                    is_new_existing_file = bool(item.get("_pending_existing_file_metadata", False))
                    if is_new_existing_file:
                        display_name = self.display_name_var.get().strip() or "Admin"
                        append_metadata_history(item, display_name, "Vorhandene Nextcloud-Datei in ODV aufgenommen", "Automatisch für dokumentbezogene Sonderpunkte")
                    api_ok, api_msg = self.save_file_view_item_to_storage(item, metadata_file, is_new_existing_file)
                    if not api_ok:
                        messagebox.showwarning("Sonderpunkte", f"Das Dokument konnte nicht in ODV angelegt werden:\n{api_msg}")
                        return
                    self.file_view_current_metadata = item
                    self.load_file_view_metadata_form()
                    try:
                        self.refresh_admin_uploads(show_message=False)
                    except Exception:
                        pass
                except Exception as exc:
                    messagebox.showerror("Sonderpunkte", f"Das Dokument konnte nicht in ODV angelegt werden:\n{exc}")
                    return
        if not item or not item.get("upload_id"):
            messagebox.showwarning("Sonderpunkte", "Bitte im Reiter 'Dateien anzeigen' zuerst ein ODV-Dokument auswählen.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Sonderpunkte ist eine API-Anmeldung erforderlich.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Sonderpunkte zum Dokument")
        try:
            self.track_window_geometry(dialog, "Sonderpunkte zum Dokument")
        except Exception:
            pass
        dialog.geometry("920x560")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        upload_id = str(item.get("upload_id") or "")
        selected_point_id = {"id": None}
        manual_points: list[dict] = []
        ttk.Label(dialog, text=f"Dokument: {item.get('current_filename') or item.get('original_filename') or upload_id}").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))

        users_resp = self.api.list_users(self.api_token)
        users = users_resp.get("users", []) or []
        user_map = {f"{u.get('display_name')} ({u.get('username')})": int(u.get('id')) for u in users if int(u.get('is_active', 1)) == 1}
        user_id_to_label = {uid: label for label, uid in user_map.items()}
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
        rule_key_to_label = {str(rule.get("rule_key") or ""): label for label, rule in bonus_map.items()}
        bonus_var = tk.StringVar(value=bonus_labels[0] if bonus_labels else "")
        points_var = tk.StringVar(value=str(int(bonus_rules[0].get("points", 0))) if bonus_rules else "0")
        content = ttk.Frame(dialog)
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        list_frame = ttk.LabelFrame(content, text="Vorhandene Sonderpunkte", padding=6)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        cols = ("user", "points", "reason", "created")
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse", height=12)
        headings = {"user": "Benutzer", "points": "Punkte", "reason": "Begründung", "created": "Erfasst"}
        widths = {"user": 150, "points": 60, "reason": 260, "created": 130}
        for col in cols:
            tree.heading(col, text=headings[col])
            tree.column(col, width=widths[col], anchor=("e" if col == "points" else "w"))
        tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=0, column=1, sticky="ns")

        form = ttk.LabelFrame(content, text="Sonderpunkt bearbeiten", padding=8)
        form.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        form.columnconfigure(1, weight=1)
        form.rowconfigure(3, weight=1)
        reason_text = tk.Text(form, height=10, wrap="word")

        ttk.Label(form, text="Empfänger:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=user_var, values=list(user_map.keys()), state="readonly").grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(form, text="Leistungsart:").grid(row=1, column=0, sticky="w", pady=4)
        bonus_combo = ttk.Combobox(form, textvariable=bonus_var, values=bonus_labels, state="readonly")
        bonus_combo.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(form, text="Punkte:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=points_var, width=8).grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(form, text="Begründung:").grid(row=3, column=0, sticky="nw", pady=4)
        reason_text.grid(row=3, column=1, sticky="nsew", pady=4)
        ttk.Label(form, text="Hinweis: Bestehende Einträge können ausgewählt, geändert und erneut gespeichert werden.", foreground="#555555", wraplength=360).grid(row=4, column=1, sticky="w", pady=(0, 4))

        def on_bonus_selected(_event=None):
            rule = bonus_map.get(bonus_var.get())
            if rule:
                points_var.set(str(int(rule.get("points", 0))))
                if not reason_text.get("1.0", "end").strip():
                    reason_text.insert("1.0", str(rule.get("label", "")))

        bonus_combo.bind("<<ComboboxSelected>>", on_bonus_selected)

        def strip_rule_prefix(reason: str, rule_label: str) -> str:
            text = str(reason or "").strip()
            prefix = f"{rule_label}:"
            if rule_label and text.startswith(prefix):
                return text[len(prefix):].strip()
            return text

        def refresh_manual_points(select_id: int | None = None) -> None:
            nonlocal manual_points
            try:
                resp = self.api.document_points(self.api_token, upload_id)
                manual_points = [p for p in resp.get("points", []) or [] if int(p.get("is_manual", 0) or 0) == 1]
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc), parent=dialog)
                manual_points = []
            tree.delete(*tree.get_children())
            for point in manual_points:
                pid = str(point.get("id") or "")
                tree.insert("", "end", iid=pid, values=(
                    point.get("user_display_name", ""),
                    point.get("points", ""),
                    point.get("reason", ""),
                    point.get("created_at", ""),
                ))
            if select_id is not None and tree.exists(str(select_id)):
                tree.selection_set(str(select_id))
                tree.see(str(select_id))
                load_selected_point()

        def clear_form() -> None:
            selected_point_id["id"] = None
            if user_map:
                user_var.set(next(iter(user_map.keys())))
            if bonus_labels:
                bonus_var.set(bonus_labels[0])
                points_var.set(str(int(bonus_rules[0].get("points", 0))))
            else:
                points_var.set("0")
            reason_text.delete("1.0", "end")
            on_bonus_selected()
            try:
                tree.selection_remove(tree.selection())
            except tk.TclError:
                pass

        def load_selected_point(_event=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            point = next((p for p in manual_points if str(p.get("id")) == str(sel[0])), None)
            if not point:
                return
            selected_point_id["id"] = int(point.get("id") or 0)
            user_var.set(user_id_to_label.get(int(point.get("user_id", 0) or 0), user_var.get()))
            rule_key = str(point.get("rule_key") or "")
            bonus_var.set(rule_key_to_label.get(rule_key, bonus_var.get()))
            points_var.set(str(int(point.get("points", 0) or 0)))
            rule = bonus_map.get(bonus_var.get()) or {}
            label = str(rule.get("label") or "")
            reason_text.delete("1.0", "end")
            reason_text.insert("1.0", strip_rule_prefix(str(point.get("reason") or ""), label))

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
                point_id = selected_point_id.get("id")
                if point_id:
                    self.api.update_manual_document_points(self.api_token, int(point_id), user_id, points, full_reason, category, rule_key=rule_key, source_field=source_field)
                    select_id = int(point_id)
                else:
                    self.api.add_manual_points(self.api_token, upload_id, user_id, points, full_reason, category, rule_key=rule_key, source_field=source_field)
                    select_id = None
                self.update_admin_document_points_display(str(item.get("upload_id", "")))
                refresh_manual_points(select_id=select_id)
                messagebox.showinfo("Sonderpunkte", "Sonderpunkte wurden gespeichert.", parent=dialog)
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc), parent=dialog)

        def delete_manual() -> None:
            point_id = selected_point_id.get("id")
            if not point_id:
                messagebox.showwarning("Sonderpunkte", "Bitte zuerst einen vorhandenen Sonderpunkt auswählen.", parent=dialog)
                return
            if not messagebox.askyesno("Sonderpunkte", "Ausgewählten Sonderpunkt wirklich löschen?", parent=dialog):
                return
            try:
                self.api.delete_manual_document_points(self.api_token, int(point_id))
                selected_point_id["id"] = None
                clear_form()
                refresh_manual_points()
                self.update_admin_document_points_display(upload_id)
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc), parent=dialog)

        tree.bind("<<TreeviewSelect>>", load_selected_point)
        clear_form()
        refresh_manual_points()
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(buttons, text="Neu", command=clear_form).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Speichern", command=save_manual).pack(side="left")
        ttk.Button(buttons, text="Löschen", command=delete_manual).pack(side="left", padx=6)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")

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
