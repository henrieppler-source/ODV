from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .config import save_config
from .database import HistoryEntry, add_history
from .normalization_rules import (
    DEFAULT_FILENAME_TEMPLATE,
    filename_normalization_rules,
    filename_template_is_safe,
    render_filename_template,
)


class NormalizationUiManagerMixin:
    def open_filename_normalization_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Normalisierungsregeln dürfen nur Superadmins ändern.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Dateinamen-Normalisierung")
        try:
            self.track_window_geometry(dialog, "Dateinamen-Normalisierung")
        except Exception:
            pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(1, weight=1)

        ttk.Label(dialog, text="Dateinamen-Normalisierung", font=("", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6))

        rules = filename_normalization_rules(self.config_data)
        selected_index = tk.IntVar(value=-1)
        standard_template_var = tk.StringVar(value=str(self.config_data.get("filename_normalization_template") or DEFAULT_FILENAME_TEMPLATE))
        active_var = tk.BooleanVar(value=True)
        name_var = tk.StringVar()
        folder_var = tk.StringVar()
        template_var = tk.StringVar()
        preview_var = tk.StringVar(value="Vorschau: -")

        left = ttk.LabelFrame(dialog, text="Regeln", padding=8)
        left.grid(row=1, column=0, sticky="nsw", padx=(12, 6), pady=6)
        left.rowconfigure(0, weight=1)
        rule_list = tk.Listbox(left, width=32, height=18)
        rule_list.grid(row=0, column=0, columnspan=2, sticky="nsew")
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=rule_list.yview)
        scrollbar.grid(row=0, column=2, sticky="ns")
        rule_list.configure(yscrollcommand=scrollbar.set)

        right = ttk.LabelFrame(dialog, text="Regel bearbeiten", padding=8)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)
        right.columnconfigure(1, weight=1)

        ttk.Label(right, text="Standardvorlage:").grid(row=0, column=0, sticky="w")
        ttk.Entry(right, textvariable=standard_template_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(right, text="Sicherheitsregel: keine Pfade, nur bekannte Platzhalter; empfohlen: {datum}_{ort}_{dateiname}.", wraplength=680).grid(row=1, column=1, sticky="w", padx=6, pady=(2, 10))

        ttk.Separator(right).grid(row=2, column=0, columnspan=3, sticky="ew", pady=6)

        ttk.Label(right, text="Name:").grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(right, textvariable=name_var).grid(row=3, column=1, sticky="ew", padx=6, pady=(4, 0))
        ttk.Checkbutton(right, text="Regel aktiv", variable=active_var).grid(row=3, column=2, sticky="w", pady=(4, 0))

        ttk.Label(right, text="Ordner enthält:").grid(row=4, column=0, sticky="w", pady=(6, 0))
        folder_entry = ttk.Entry(right, textvariable=folder_var)
        folder_entry.grid(row=4, column=1, sticky="ew", padx=6, pady=(6, 0))

        def choose_folder() -> None:
            try:
                selected = self.open_folder_tree_dialog("Ordner für Normalisierungsregel auswählen", self.writable_folders, folder_var.get())
            except Exception:
                selected = ""
            if selected:
                folder_var.set(str(selected))
                update_preview()

        ttk.Button(right, text="Baum...", command=choose_folder).grid(row=4, column=2, sticky="ew", pady=(6, 0))

        ttk.Label(right, text="Vorlage:").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(right, textvariable=template_var).grid(row=5, column=1, columnspan=2, sticky="ew", padx=6, pady=(6, 0))

        placeholders = (
            "Platzhalter: {datum}, {jahr}, {monat}, {tag}, {ort}, {ereignis}, {quelle}, "
            "{erfasst}, {bearbeitet}, {dateiname}, {dateiname_mmdd}, {original}, {ordner}, {ordner1} ... {ordner9}"
        )
        ttk.Label(right, text=placeholders, wraplength=760).grid(row=6, column=1, columnspan=2, sticky="w", padx=6, pady=(4, 8))

        ttk.Label(right, textvariable=preview_var, foreground="#444").grid(row=7, column=1, columnspan=2, sticky="w", padx=6, pady=(0, 8))

        sample = {
            "current_filename": "2021-02-04.pdf",
            "original_filename": "2021-02-04.pdf",
            "document_date": "2026-02-01",
            "place": "Milz",
            "event": "Zeitungsartikel",
            "primary_source": "Freies Wort",
            "uploaded_by": "Henri Eppler",
            "edited_by": "Admin",
            "current_path": r"C:\Nextcloud_OC\00_ORTSCHRONIK\90_Archive_und_Quellen\90-10_Zeitungen\Freies_Wort\2026\2026_02\2021-02-04.pdf",
        }

        def refresh_list() -> None:
            current = selected_index.get()
            rule_list.delete(0, "end")
            for idx, rule in enumerate(rules):
                marker = "" if rule.get("active", True) else " (inaktiv)"
                rule_list.insert("end", f"{rule.get('name') or 'Regel'}{marker}")
            if 0 <= current < len(rules):
                rule_list.selection_set(current)

        def load_rule(index: int) -> None:
            selected_index.set(index)
            if 0 <= index < len(rules):
                rule = rules[index]
                active_var.set(bool(rule.get("active", True)))
                name_var.set(str(rule.get("name") or ""))
                folder_var.set(str(rule.get("folder") or ""))
                template_var.set(str(rule.get("template") or ""))
            else:
                active_var.set(True)
                name_var.set("")
                folder_var.set("")
                template_var.set("")
            update_preview()

        def selected_from_list(_event: object | None = None) -> None:
            sel = rule_list.curselection()
            if sel:
                load_rule(int(sel[0]))

        def update_preview(*_args: object) -> None:
            template = template_var.get().strip() or standard_template_var.get().strip()
            if not filename_template_is_safe(template):
                preview_var.set("Vorschau: Vorlage ist nicht sicher/ungueltig.")
                return
            preview_item = dict(sample)
            if folder_var.get().strip():
                preview_item["current_path"] = rf"C:\Nextcloud_OC\{folder_var.get().strip()}\2021-02-04.pdf"
            preview_item["_normalization_preview_template"] = template
            try:
                suffix = ".pdf"
                preview_var.set(f"Vorschau: {render_filename_template(template, preview_item, preview_item['current_filename'])}{suffix}")
            except Exception:
                preview_var.set("Vorschau: konnte nicht erzeugt werden.")

        def new_rule() -> None:
            rule = {"name": "Neue Regel", "folder": "", "template": "{datum}_{ort}_{dateiname}", "active": True}
            rules.append(rule)
            selected_index.set(len(rules) - 1)
            refresh_list()
            load_rule(len(rules) - 1)

        def save_rule() -> None:
            template = template_var.get().strip()
            if template and not filename_template_is_safe(template):
                messagebox.showwarning("Normalisierung", "Die Regelvorlage ist nicht sicher oder enthält unbekannte Platzhalter.", parent=dialog)
                return
            idx = selected_index.get()
            rule = {
                "name": name_var.get().strip() or "Regel",
                "folder": folder_var.get().strip(),
                "template": template or "{datum}_{ort}_{dateiname}",
                "active": active_var.get(),
            }
            if idx < 0:
                rules.append(rule)
                selected_index.set(len(rules) - 1)
            else:
                rules[idx] = rule
            refresh_list()
            update_preview()

        def delete_rule() -> None:
            idx = selected_index.get()
            if 0 <= idx < len(rules):
                del rules[idx]
                selected_index.set(min(idx, len(rules) - 1))
                refresh_list()
                load_rule(selected_index.get())

        def move_rule(delta: int) -> None:
            idx = selected_index.get()
            new_idx = idx + delta
            if 0 <= idx < len(rules) and 0 <= new_idx < len(rules):
                rules[idx], rules[new_idx] = rules[new_idx], rules[idx]
                selected_index.set(new_idx)
                refresh_list()
                load_rule(new_idx)

        def save_all() -> None:
            standard_template = standard_template_var.get().strip() or DEFAULT_FILENAME_TEMPLATE
            if not filename_template_is_safe(standard_template):
                messagebox.showwarning("Normalisierung", "Die Standardvorlage ist nicht sicher oder enthält unbekannte Platzhalter.", parent=dialog)
                return
            if selected_index.get() >= 0 or name_var.get().strip() or folder_var.get().strip() or template_var.get().strip():
                save_rule()
            self.config_data["filename_normalization_template"] = standard_template
            self.config_data["filename_normalization_rules"] = rules
            save_config(self.config_data)
            add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Superadmin", "Normalisierungsregeln geändert", f"{len(rules)} Regel(n) gespeichert"))
            messagebox.showinfo("Normalisierung", "Normalisierungsregeln wurden gespeichert.", parent=dialog)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 12))
        ttk.Button(buttons, text="Neu", command=new_rule).pack(side="left")
        ttk.Button(buttons, text="Speichern", command=save_all).pack(side="left", padx=6)
        ttk.Button(buttons, text="Loeschen", command=delete_rule).pack(side="left")
        ttk.Button(buttons, text="▲", width=3, command=lambda: move_rule(-1)).pack(side="left", padx=(12, 2))
        ttk.Button(buttons, text="▼", width=3, command=lambda: move_rule(1)).pack(side="left")
        ttk.Button(buttons, text="Schliessen", command=dialog.destroy).pack(side="right")

        rule_list.bind("<<ListboxSelect>>", selected_from_list)
        for var in (standard_template_var, folder_var, template_var):
            var.trace_add("write", update_preview)
        refresh_list()
        load_rule(0 if rules else -1)
