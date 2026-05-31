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

class PointsManagerMixin:
    # Punkte / Beitragsauswertung
    def _current_points_year(self) -> int:
        return datetime.now().year

    def open_point_rules_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Punkteregeln dürfen nur Superadmins verwalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Punkteregeln ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Punkteregeln verwalten")
        try: self.track_window_geometry(dialog, "Punkteregeln verwalten")
        except Exception: pass
        dialog.geometry("1320x720")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Kalenderjahr:").pack(side="left")
        year_var = tk.StringVar(value=str(self._current_points_year()))
        ttk.Entry(top, textvariable=year_var, width=8).pack(side="left", padx=6)
        tree = ttk.Treeview(dialog, columns=("field", "source", "key", "label", "type", "check", "min", "points", "active"), show="headings", selectmode="browse")
        for col, label, width in [
            ("field", "Metadaten-Feld", 150),
            ("source", "Wertung", 90),
            ("key", "Regel", 220),
            ("label", "Beschreibung", 280),
            ("type", "Typ", 90),
            ("check", "Prüfung", 90),
            ("min", "Mindestwert", 90),
            ("points", "Punkte", 80),
            ("active", "Aktiv", 60),
        ]:
            tree.heading(col, text=label, anchor="w", command=lambda c=col: sort_point_rules_tree(c))
            tree.column(col, width=width, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=1, column=1, sticky="ns")
        form = ttk.Frame(dialog, padding=8)
        form.grid(row=2, column=0, sticky="ew")
        for value_col in (1, 3):
            form.columnconfigure(value_col, weight=1, uniform="point_rule_fields")
        rule_key_var = tk.StringVar()
        field_var = tk.StringVar()
        label_var = tk.StringVar()
        category_var = tk.StringVar()
        source_var = tk.StringVar()
        check_type_var = tk.StringVar(value="characters")
        min_value_var = tk.StringVar(value="1")
        points_var = tk.StringVar()
        active_var = tk.BooleanVar(value=True)
        metadata_fields = [
            ("archive_name", "Archiv / Sammlung"),
            ("archive_signature", "Archivsignatur"),
            ("copyright_author", "Urheber/in"),
            ("description", "Beschreibung"),
            ("document_date", "Datum / Zeitraum"),
            ("event", "Ereignis"),
            ("keywords", "Stichwörter"),
            ("rights_holder", "Rechteinhaber"),
            ("rights_note", "Rechtehinweis"),
            ("source", "Quelle / Herkunft"),
            ("usage_permission", "Nutzungsfreigabe"),
        ]
        field_labels = [f"{key} - {label}" for key, label in metadata_fields]
        field_by_label = {field_labels[i]: metadata_fields[i][0] for i in range(len(metadata_fields))}
        label_by_field = {key: label for key, label in metadata_fields}
        ttk.Label(form, text="Metadatenfeld:").grid(row=0, column=0, sticky="w", padx=(0,4), pady=3)
        field_combo = ttk.Combobox(form, textvariable=field_var, values=field_labels, state="readonly")
        field_combo.grid(row=0, column=1, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Beschreibung:").grid(row=0, column=2, sticky="w", padx=(0,4), pady=3)
        ttk.Entry(form, textvariable=label_var).grid(row=0, column=3, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Typ:").grid(row=1, column=0, sticky="w", padx=(0,4), pady=3)
        category_options = ["metadata", "system", "manual"]
        category_combo = ttk.Combobox(form, textvariable=category_var, values=category_options, state="readonly")
        category_combo.grid(row=1, column=1, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Punkte:").grid(row=1, column=2, sticky="w", padx=(0,4), pady=3)
        ttk.Entry(form, textvariable=points_var).grid(row=1, column=3, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Regel:").grid(row=2, column=0, sticky="w", padx=(0,4), pady=3)
        ttk.Entry(form, textvariable=rule_key_var, state="readonly").grid(row=2, column=1, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Wertung:").grid(row=2, column=2, sticky="w", padx=(0,4), pady=3)
        ttk.Entry(form, textvariable=source_var).grid(row=2, column=3, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Prüfung:").grid(row=3, column=0, sticky="w", padx=(0,4), pady=3)
        ttk.Combobox(form, textvariable=check_type_var, values=["characters", "words", "count", "none"], state="readonly").grid(row=3, column=1, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Mindestwert:").grid(row=3, column=2, sticky="w", padx=(0,4), pady=3)
        ttk.Entry(form, textvariable=min_value_var).grid(row=3, column=3, sticky="ew", padx=(0,10), pady=3)
        ttk.Checkbutton(form, text="Aktiv", variable=active_var).grid(row=3, column=3, sticky="w")
        def source_field_from_rule_key(rule_key: str) -> str:
            key = str(rule_key or "").strip()
            for suffix in ("_metadata", "_metadaten", "_manual", "_openAI"):
                if key.endswith(suffix):
                    return key[:-len(suffix)]
            return self.point_rule_source_field_from_key(key)

        def field_label_for_key(field_key: str) -> str:
            return f"{field_key} - {label_by_field.get(field_key, field_key)}"

        def selected_field_key() -> str:
            text = field_var.get().strip()
            return field_by_label.get(text, text.split(" - ", 1)[0].strip())

        def update_rule_from_field_category(*_args):
            field_key = selected_field_key()
            rule_type = category_var.get().strip()
            source = source_var.get().strip() or "manual"
            if field_key and rule_type == "metadata" and source in {"manual", "openAI"}:
                rule_key_var.set(f"{field_key}_{source}")
                if not label_var.get().strip():
                    label_var.set(f"{label_by_field.get(field_key, field_key)} angegeben")

        def sort_point_rules_tree(column: str) -> None:
            rows = [(tree.set(iid, column), iid) for iid in tree.get_children("")]
            numeric = column in {"points", "min"}
            reverse = getattr(tree, "_sort_reverse", {}).get(column, False)
            if numeric:
                rows.sort(key=lambda item: int(float(item[0] or 0)), reverse=reverse)
            else:
                rows.sort(key=lambda item: str(item[0]).lower(), reverse=reverse)
            for index, (_value, iid) in enumerate(rows):
                tree.move(iid, "", index)
            sort_state = dict(getattr(tree, "_sort_reverse", {}))
            sort_state[column] = not reverse
            tree._sort_reverse = sort_state

        def load_rules():
            for item in tree.get_children():
                tree.delete(item)
            try:
                resp = self.api.list_point_rules(self.api_token, int(year_var.get()))
                valid_rules = resp.get("valid_rules", []) or []
                valid_by_key = {str(rule.get("rule_key", "")): rule for rule in valid_rules if str(rule.get("rule_key", ""))}
                current_rules = resp.get("rules", []) or []
                current_by_key = {str(rule.get("rule_key", "")): rule for rule in current_rules if str(rule.get("rule_key", "")) in valid_by_key}
                loaded_keys = set()
                for valid_rule in valid_rules:
                    rule = dict(valid_rule)
                    current = current_by_key.get(str(valid_rule.get("rule_key", "")), {})
                    for keep in ("label", "points", "is_active"):
                        if keep in current:
                            rule[keep] = current.get(keep)
                    key = str(rule.get("rule_key", ""))
                    loaded_keys.add(key)
                    tree.insert("", "end", values=(
                        rule.get("source_field", ""),
                        rule.get("evaluation_source", rule.get("source", "")),
                        key,
                        rule.get("label", ""),
                        rule.get("rule_type", ""),
                        rule.get("check_type", "none"),
                        rule.get("min_value", 0),
                        rule.get("points", 0),
                        "ja" if int(rule.get("is_active", 1)) else "nein",
                    ))
                for rule in current_rules:
                    key = str(rule.get("rule_key", ""))
                    if key in loaded_keys or str(rule.get("rule_type", "")) != "manual":
                        continue
                    tree.insert("", "end", values=(
                        rule.get("source_field", "manual"),
                        rule.get("evaluation_source", "manual"),
                        key,
                        rule.get("label", ""),
                        "manual",
                        "none",
                        0,
                        rule.get("points", 0),
                        "ja" if int(rule.get("is_active", 1)) else "nein",
                    ))
            except Exception as exc:
                messagebox.showerror("Punkteregeln", str(exc))

        def select_rule(_event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            field_key = vals[0] or source_field_from_rule_key(vals[2])
            field_var.set(field_label_for_key(field_key))
            source_var.set(vals[1] if len(vals) > 1 else "")
            rule_key_var.set(vals[2] if len(vals) > 2 else "")
            label_var.set(vals[3] if len(vals) > 3 else "")
            category_var.set(vals[4] if len(vals) > 4 else "")
            check_type_var.set(vals[5] if len(vals) > 5 else "none")
            min_value_var.set(vals[6] if len(vals) > 6 else "0")
            points_var.set(vals[7] if len(vals) > 7 else "0")
            active_var.set(str(vals[8] if len(vals) > 8 else "ja").lower() in {"ja", "1", "true"})

        def apply_to_tree():
            update_rule_from_field_category()
            key = rule_key_var.get().strip()
            if not category_var.get().strip():
                category_var.set("metadata")
            if category_var.get().strip() == "system":
                messagebox.showinfo("Punkteregeln", "Sonderregeln sind Systemvorgaben und können hier nicht bearbeitet werden.")
                return
            source_field = selected_field_key() if category_var.get().strip() == "metadata" else source_var.get().strip()
            vals = (source_field, source_var.get().strip(), key, label_var.get().strip(), category_var.get().strip(), check_type_var.get().strip(), min_value_var.get().strip() or "0", points_var.get().strip() or "0", "ja" if active_var.get() else "nein")
            if not vals[2] or not vals[3]:
                messagebox.showwarning("Punkteregeln", "Regel und Beschreibung sind erforderlich.")
                return
            try:
                int(float(vals[6] or 0))
                int(float(vals[7] or 0))
            except Exception:
                messagebox.showwarning("Punkteregeln", "Mindestwert und Punkte müssen Zahlen sein.")
                return
            sel = tree.selection()
            if sel:
                tree.item(sel[0], values=vals)
            else:
                existing = next((iid for iid in tree.get_children() if str(tree.item(iid, "values")[2]) == key), None)
                if existing:
                    tree.selection_set(existing)
                    tree.item(existing, values=vals)
                else:
                    tree.insert("", "end", values=vals)

        def new_rule():
            tree.selection_remove(tree.selection())
            field_var.set(field_labels[0] if field_labels else "")
            rule_key_var.set("")
            label_var.set("")
            category_var.set("metadata")
            source_var.set("manual")
            check_type_var.set("characters")
            min_value_var.set("1")
            points_var.set("0")
            active_var.set(True)
            update_rule_from_field_category()
            field_combo.focus_set()

        def delete_rule():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Punkteregeln", "Bitte zuerst eine Regel in der Liste auswählen.", parent=dialog)
                return
            vals = tree.item(sel[0], "values")
            if len(vals) > 4 and str(vals[4]) == "system":
                messagebox.showinfo("Punkteregeln", "Sonderregeln sind Systemvorgaben und können nicht gelöscht werden.", parent=dialog)
                return
            key = str(vals[2] if len(vals) > 2 else vals[0] or "")
            if not messagebox.askyesno("Punkteregeln", f"Regel '{key}' wirklich löschen?\n\nWirksam wird die Löschung erst mit 'Speichern'.", parent=dialog):
                return
            tree.delete(sel[0])
            rule_key_var.set("")
            label_var.set("")
            source_var.set("")
            check_type_var.set("none")
            min_value_var.set("0")
            points_var.set("")
            active_var.set(True)

        def save_rules():
            rules = []
            for iid in tree.get_children():
                source_field, source, key, label, rule_type, check_type, min_value, points, active = tree.item(iid, "values")
                category = "manual" if rule_type == "manual" else ("metadata" if rule_type == "metadata" else source_field or "system")
                if rule_type == "system":
                    category = str(source_field or "")
                    if key in {"persons_image_marked", "persons_per_person"}:
                        category = "persons"
                    elif key in {"admin_review_accepted", "admin_file_organization"}:
                        category = "admin_review"
                    elif key == "special_collection":
                        category = "special_collection"
                    else:
                        category = "metadata"
                rules.append({
                    "rule_key": key,
                    "label": label,
                    "category": category,
                    "rule_type": rule_type,
                    "source_field": source_field,
                    "evaluation_source": source,
                    "check_type": check_type,
                    "min_value": int(float(min_value or 0)),
                    "points": int(float(points or 0)),
                    "is_active": str(active).lower() in {"ja", "1", "true"},
                    "is_system": rule_type == "system",
                })
            try:
                self.api.update_point_rules(self.api_token, int(year_var.get()), rules)
                messagebox.showinfo("Punkteregeln", "Punkteregeln wurden gespeichert.")
                load_rules()
            except Exception as exc:
                messagebox.showerror("Punkteregeln", str(exc))

        field_combo.bind("<<ComboboxSelected>>", update_rule_from_field_category)
        category_combo.bind("<<ComboboxSelected>>", update_rule_from_field_category)
        tree.bind("<<TreeviewSelect>>", select_rule)
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Button(top, text="Laden", command=load_rules).pack(side="left", padx=6)
        ttk.Button(buttons, text="Regel übernehmen", command=apply_to_tree).pack(side="left")
        ttk.Button(buttons, text="Neue Regel", command=new_rule).pack(side="left", padx=6)
        ttk.Button(buttons, text="Regel löschen", command=delete_rule).pack(side="left")
        ttk.Button(buttons, text="Speichern", command=save_rules).pack(side="left", padx=6)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load_rules()

    def open_my_points_dialog(self) -> None:
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für den Punktestand ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Mein Punktestand")
        try: self.track_window_geometry(dialog, "Mein Punktestand")
        except Exception: pass
        dialog.geometry("1040x660")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(2, weight=1)

        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Kalenderjahr:").pack(side="left")
        year_var = tk.StringVar(value=str(self._current_points_year()))
        ttk.Entry(top, textvariable=year_var, width=8).pack(side="left", padx=6)
        selected_user_var = tk.StringVar()
        user_map: dict[str, int] = {}
        if self.is_current_admin():
            ttk.Label(top, text="Bearbeiter:").pack(side="left", padx=(16, 4))
            labels, users = self.load_active_user_options()
            for lbl, u in users.items():
                try:
                    user_map[lbl] = int(u.get("id") or 0)
                except Exception:
                    pass
            own_id = self.current_user_id()
            default_label = next((lbl for lbl, uid in user_map.items() if uid == own_id), (labels[0] if labels else ""))
            selected_user_var.set(default_label)
            user_combo = ttk.Combobox(top, textvariable=selected_user_var, values=labels, state="readonly", width=34)
            user_combo.pack(side="left", padx=4)

        summary_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=summary_var, font=("", 11, "bold"), padding=8).grid(row=1, column=0, sticky="w")

        tree = ttk.Treeview(dialog, columns=("date", "document", "category", "reason", "points", "status", "credit"), show="headings")
        for col, label, width in [("date", "Datum", 140), ("document", "Dokument", 260), ("category", "Kategorie", 120), ("reason", "Grund", 310), ("points", "Punkte", 70), ("status", "Dokumentstatus", 110), ("credit", "Wertung", 110)]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=2, column=1, sticky="ns")
        row_upload_ids: dict[str, str] = {}
        load_pending = {"after_id": None}

        def load_my_points():
            for iid in tree.get_children():
                tree.delete(iid)
            row_upload_ids.clear()
            try:
                user_id = user_map.get(selected_user_var.get()) if self.is_current_admin() else None
                resp = self.api.my_points(self.api_token, int(year_var.get()), user_id=user_id)
                own = resp.get("own", {}) or {}
                rank = resp.get("rank")
                participant_count = resp.get("participant_count")
                total = own.get("total_points", 0)
                provisional = own.get("provisional_points", 0)
                summary_var.set(
                    f"{total} gewertete Punkte · {provisional} vorläufig · Rang {rank or '-'} von {participant_count or 0} · "
                    f"Metadaten {own.get('metadata_points', 0)} · Rechte/Sonder {own.get('manual_points', 0)} · "
                    f"Personen {own.get('persons_points', 0)} · Admin {own.get('admin_points', 0)}"
                )
                for idx, row in enumerate(resp.get("events", []) or []):
                    status = row.get("document_status", "")
                    credit = "gewertet" if status == "uebernommen" or int(row.get("is_manual", 0) or 0) == 1 else "vorläufig"
                    iid = f"row{idx}"
                    tree.insert("", "end", iid=iid, values=(row.get("created_at", ""), row.get("filename", row.get("upload_id", "")), row.get("category", ""), row.get("reason", ""), row.get("points", 0), status, credit))
                    row_upload_ids[iid] = str(row.get("upload_id") or "")
            except Exception as exc:
                messagebox.showerror("Mein Punktestand", str(exc), parent=dialog)

        def schedule_load(*_args):
            try:
                old_after = load_pending.get("after_id")
                if old_after:
                    try:
                        dialog.after_cancel(old_after)
                    except Exception:
                        pass
                load_pending["after_id"] = dialog.after(150, load_my_points)
            except Exception:
                load_my_points()

        def open_selected_from_points(_event=None):
            sel = tree.selection()
            if not sel:
                return
            upload_id = row_upload_ids.get(sel[0], "")
            dialog.destroy()
            self.open_document_in_admin_by_upload_id(upload_id)

        tree.bind("<Double-1>", open_selected_from_points)
        if self.is_current_admin():
            try:
                user_combo.bind("<<ComboboxSelected>>", lambda _e: schedule_load())
            except Exception:
                pass
        try:
            year_var.trace_add("write", lambda *_: schedule_load())
        except Exception:
            pass
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Label(buttons, text="Doppelklick öffnet das Dokument in 'Dateien bearbeiten'.", foreground="#555555").pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load_my_points()

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
        try: self.track_window_geometry(dialog, "Sonderpunkte vergeben")
        except Exception: pass
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
        try: self.track_window_geometry(dialog, "Punkte-Einstellungen")
        except Exception: pass
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
        try: self.track_window_geometry(dialog, "Sonderpunkte für Ortschronisten")
        except Exception: pass
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
        try: self.track_window_geometry(dialog, "Übersicht manuelle Sonderpunkte")
        except Exception: pass
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
        widths = {"date":110, "user":190, "place":120, "rule":240, "hours":90, "points":80, "reason":340, "created_by":180, "created_at":150}
        labels = {"date":"Datum", "user":"Ortschronist", "place":"Ort", "rule":"Tätigkeit", "hours":"Stunden", "points":"Punkte", "reason":"Begründung", "created_by":"Vergeben von", "created_at":"Erfasst am"}
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
