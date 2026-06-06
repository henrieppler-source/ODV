from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox


class PointsRulesManagerMixin:
    def open_point_rules_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Punkteregeln dürfen nur Superadmins verwalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Punkteregeln ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Punkteregeln verwalten")
        try:
            self.track_window_geometry(dialog, "Punkteregeln verwalten")
        except Exception:
            pass
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
        ttk.Label(form, text="Metadatenfeld:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=3)
        field_combo = ttk.Combobox(form, textvariable=field_var, values=field_labels, state="readonly")
        field_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=3)
        ttk.Label(form, text="Beschreibung:").grid(row=0, column=2, sticky="w", padx=(0, 4), pady=3)
        ttk.Entry(form, textvariable=label_var).grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=3)
        ttk.Label(form, text="Typ:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=3)
        category_options = ["metadata", "system", "manual"]
        category_combo = ttk.Combobox(form, textvariable=category_var, values=category_options, state="readonly")
        category_combo.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=3)
        ttk.Label(form, text="Punkte:").grid(row=1, column=2, sticky="w", padx=(0, 4), pady=3)
        ttk.Entry(form, textvariable=points_var).grid(row=1, column=3, sticky="ew", padx=(0, 10), pady=3)
        ttk.Label(form, text="Regel:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=3)
        ttk.Entry(form, textvariable=rule_key_var, state="readonly").grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=3)
        ttk.Label(form, text="Wertung:").grid(row=2, column=2, sticky="w", padx=(0, 4), pady=3)
        ttk.Entry(form, textvariable=source_var).grid(row=2, column=3, sticky="ew", padx=(0, 10), pady=3)
        ttk.Label(form, text="Prüfung:").grid(row=3, column=0, sticky="w", padx=(0, 4), pady=3)
        ttk.Combobox(form, textvariable=check_type_var, values=["characters", "words", "count", "none"], state="readonly").grid(row=3, column=1, sticky="ew", padx=(0, 10), pady=3)
        ttk.Label(form, text="Mindestwert:").grid(row=3, column=2, sticky="w", padx=(0, 4), pady=3)
        ttk.Entry(form, textvariable=min_value_var).grid(row=3, column=3, sticky="ew", padx=(0, 10), pady=3)
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
            vals = (
                source_field,
                source_var.get().strip(),
                key,
                label_var.get().strip(),
                category_var.get().strip(),
                check_type_var.get().strip(),
                min_value_var.get().strip() or "0",
                points_var.get().strip() or "0",
                "ja" if active_var.get() else "nein",
            )
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
            if str(vals[4]) == "system":
                messagebox.showinfo("Punkteregeln", "Systemregeln dürfen hier nicht gelöscht werden.")
                return
            if not messagebox.askyesno("Punkteregeln", f"Regel '{vals[2]}' wirklich löschen?", parent=dialog):
                return
            tree.delete(sel[0])

        def save_rules():
            try:
                rows = []
                for iid in tree.get_children():
                    vals = tree.item(iid, "values")
                    rows.append({
                        "source_field": vals[0],
                        "evaluation_source": vals[1],
                        "rule_key": vals[2],
                        "label": vals[3],
                        "rule_type": vals[4],
                        "check_type": vals[5],
                        "min_value": int(float(vals[6] or 0)),
                        "points": int(float(vals[7] or 0)),
                        "is_active": 1 if str(vals[8]).lower() in {"ja", "1", "true"} else 0,
                    })
                self.api.update_point_rules(self.api_token, int(year_var.get()), rows)
                messagebox.showinfo("Punkteregeln", "Regeln wurden gespeichert.", parent=dialog)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Punkteregeln", str(exc), parent=dialog)

        tree.bind("<<TreeviewSelect>>", select_rule)
        field_var.trace_add("write", lambda *_: update_rule_from_field_category())
        category_var.trace_add("write", lambda *_: update_rule_from_field_category())
        source_var.trace_add("write", lambda *_: update_rule_from_field_category())
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Button(buttons, text="Laden", command=load_rules).pack(side="left")
        ttk.Button(buttons, text="Neue Regel", command=new_rule).pack(side="left", padx=4)
        ttk.Button(buttons, text="Regel übernehmen", command=apply_to_tree).pack(side="left", padx=4)
        ttk.Button(buttons, text="Regel löschen", command=delete_rule).pack(side="left", padx=4)
        ttk.Button(buttons, text="Speichern", command=save_rules).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load_rules()

    def open_my_points_dialog(self) -> None:
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für den Punktestand ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Mein Punktestand")
        try:
            self.track_window_geometry(dialog, "Mein Punktestand")
        except Exception:
            pass
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
                    credit = "gewertet" if status in {"erfasst", "geprueft", "archiviert"} or int(row.get("is_manual", 0) or 0) == 1 else "vorläufig"
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
