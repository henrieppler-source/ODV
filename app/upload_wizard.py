from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from .file_service import is_image_file

TRANSCRIPTION_TYPE_OPTIONS = [
    "",
    "kurze Transkription",
    "vollständige Transkription",
    "schwierige Handschrift",
    "Zeitung / Akte / Urkunde",
]


class UploadWizard:
    def __init__(self, owner, parent: ttk.Frame):
        self.owner = owner
        self.parent = parent
        self.current_step = 0
        self.pages: list[ttk.Frame] = []
        self.summary_text: tk.Text | None = None
        self.points_text: tk.Text | None = None
        self.create_upload_meta_vars()
        self.create_ui()

    def create_upload_meta_vars(self) -> None:
        if not hasattr(self.owner, "upload_filename_var"):
            self.owner.upload_filename_var = tk.StringVar()
        values = {
            "upload_id": tk.StringVar(),
            "document_type": tk.StringVar(),
            "status": tk.StringVar(),
            "current_filename": self.owner.upload_filename_var,
            "uploaded_by": tk.StringVar(),
            "uploaded_at": tk.StringVar(),
            "primary_source": tk.StringVar(),
            "secondary_source": tk.StringVar(),
            "original_location": tk.StringVar(),
            "archive_name": tk.StringVar(),
            "archive_signature": tk.StringVar(),
            "archive_accessed_at": tk.StringVar(),
            "document_date": tk.StringVar(),
            "event": tk.StringVar(),
            "place": tk.StringVar(),
            "gps_coordinates": tk.StringVar(),
            "gps_place": tk.StringVar(),
            "keywords": tk.StringVar(),
            "copyright_author": tk.StringVar(),
            "rights_holder": tk.StringVar(),
            "usage_permission": tk.StringVar(),
            "license_note": tk.StringVar(),
            "rights_note": tk.StringVar(),
            "transcription_done": tk.BooleanVar(value=False),
            "transcription_type": tk.StringVar(),
            "transcription_note": tk.StringVar(),
        }
        self.owner.meta_vars = values
        self.owner.upload_option_comboboxes = {}
        self.owner.upload_description_counter_var = tk.StringVar(value="Zeichen: 0 / 50")
        self.owner.person_status_var = tk.StringVar(value="none")
        self.owner.person_summary_var = tk.StringVar(value="Keine Personen markiert.")
        self.owner.upload_multiline_meta_widgets = {}
        for key in ("document_date", "place"):
            values[key].trace_add("write", lambda *_args: getattr(self.owner, "refresh_planned_upload_filename", lambda *a, **k: None)())

    def bind_multiline_meta_field(self, key: str, widget: tk.Text) -> None:
        var = self.owner.meta_vars[key]
        syncing = {"active": False}

        def var_to_widget(*_):
            if syncing["active"]:
                return
            value = var.get()
            current = widget.get("1.0", "end-1c")
            if current == value:
                return
            syncing["active"] = True
            try:
                widget.delete("1.0", "end")
                widget.insert("1.0", value)
            finally:
                syncing["active"] = False

        def widget_to_var(_event=None):
            if syncing["active"]:
                return
            value = widget.get("1.0", "end-1c")
            if var.get() == value:
                return
            syncing["active"] = True
            try:
                var.set(value)
            finally:
                syncing["active"] = False

        widget.bind("<KeyRelease>", widget_to_var)
        widget.bind("<FocusOut>", widget_to_var)
        var.trace_add("write", var_to_widget)
        self.owner.upload_multiline_meta_widgets[key] = widget

    def configure_archive_autocomplete(self, widget: ttk.Combobox) -> None:
        def refresh_values() -> list[str]:
            values = self.owner.archive_collection_options()
            widget.configure(values=values)
            return values

        def on_keyrelease(_event=None) -> None:
            typed = self.owner.meta_vars["archive_name"].get().strip().casefold()
            values = refresh_values()
            if typed:
                widget.configure(values=[value for value in values if typed in value.casefold()])

        def remember(_event=None) -> None:
            self.owner.remember_archive_collection(self.owner.meta_vars["archive_name"].get())
            refresh_values()

        refresh_values()
        widget.bind("<KeyRelease>", on_keyrelease)
        widget.bind("<<ComboboxSelected>>", remember)
        widget.bind("<FocusOut>", remember)

    def create_ui(self) -> None:
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        self.step_frame = ttk.Frame(self.parent)
        self.step_frame.grid(row=0, column=0, sticky="nsew")
        self.nav_frame = ttk.Frame(self.parent)
        self.nav_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        # left area holds the navigation buttons, right area expands
        self.nav_frame.columnconfigure(0, weight=0)
        self.nav_frame.columnconfigure(1, weight=1)

        self.pages = [
            self.build_step_details(),
            self.build_step_source(),
            self.build_step_persons(),
            self.build_step_description(),
            self.build_step_review(),
        ]

        # place both buttons in a small container so they sit adjacent with a small gap
        button_container = ttk.Frame(self.nav_frame)
        button_container.grid(row=0, column=0, sticky="w")
        self.prev_button = ttk.Button(button_container, text="Zurück", command=self.on_prev, width=12)
        self.prev_button.pack(side="left")
        self.next_button = ttk.Button(button_container, text="Weiter", command=self.on_next, width=12)
        self.next_button.pack(side="left", padx=6)

        self.show_step(0)

    def build_step_details(self) -> ttk.Frame:
        frame = ttk.Frame(self.step_frame)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)

        ttk.Label(frame, text="Schritt 1: Zeit / Ort / Inhalt", font=(None, 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="Datum / Zeitraum:").grid(row=1, column=0, sticky="w", pady=2, padx=(4,0))
        ttk.Entry(frame, textvariable=self.owner.meta_vars["document_date"]).grid(row=1, column=1, sticky="ew", padx=6, pady=2)

        ttk.Label(frame, text="Dokumenttyp:").grid(row=2, column=0, sticky="w", pady=2, padx=(4,0))
        ttk.Combobox(
            frame,
            textvariable=self.owner.meta_vars["document_type"],
            values=self.owner.document_type_options(),
            state="normal",
        ).grid(row=2, column=1, sticky="ew", padx=6, pady=2)

        # compact meta box for Ort/Ereignis/Stichwörter aligned to the Documenttyp width
        ttk.Label(frame, text="Ort:").grid(row=3, column=0, sticky="w", pady=2, padx=(4,0))
        ttk.Entry(frame, textvariable=self.owner.meta_vars["place"]).grid(row=3, column=1, sticky="ew", padx=6, pady=2)

        gps_label = ttk.Label(frame, text="GPS-Koordinaten:")
        gps_label.grid(row=4, column=0, sticky="w", pady=2, padx=(4,0))
        gps_display = ttk.Label(
            frame,
            textvariable=self.owner.meta_vars["gps_coordinates"],
            anchor="w",
            foreground="#555555",
        )
        gps_display.grid(row=4, column=1, sticky="ew", padx=6, pady=2)

        def refresh_gps_row(*_args):
            if self.owner.meta_vars["gps_coordinates"].get().strip():
                gps_label.grid()
                gps_display.grid()
            else:
                gps_label.grid_remove()
                gps_display.grid_remove()

        self.owner.meta_vars["gps_coordinates"].trace_add("write", refresh_gps_row)
        refresh_gps_row()

        ttk.Label(frame, text="Ereignis:").grid(row=5, column=0, sticky="nw", pady=2, padx=(4,0))
        event_text = tk.Text(frame, height=2, wrap="word", undo=True)
        event_text.grid(row=5, column=1, sticky="ew", padx=6, pady=2)
        self.bind_multiline_meta_field("event", event_text)

        ttk.Label(frame, text="Stichwörter:").grid(row=6, column=0, sticky="nw", pady=2, padx=(4,0))
        keywords_text = tk.Text(frame, height=4, wrap="word", undo=True)
        keywords_text.grid(row=6, column=1, sticky="ew", padx=6, pady=2)
        self.bind_multiline_meta_field("keywords", keywords_text)

        transcription_frame = ttk.Frame(frame)
        transcription_frame.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 2))
        transcription_frame.columnconfigure(2, weight=1)
        ttk.Label(transcription_frame, text="Transkribiertes Dokument:").grid(row=0, column=0, sticky="w")
        ttk.Label(transcription_frame, text="Art:").grid(row=0, column=1, sticky="w", padx=(12,4))
        ttk.Combobox(
            transcription_frame,
            textvariable=self.owner.meta_vars["transcription_type"],
            values=TRANSCRIPTION_TYPE_OPTIONS,
            state="readonly",
            width=48,
        ).grid(row=0, column=2, sticky="ew")
        # keep transcription_done in sync with transcription_type
        self.owner.meta_vars["transcription_type"].trace_add(
            "write",
            lambda *_: self.owner.meta_vars["transcription_done"].set(bool(self.owner.meta_vars["transcription_type"].get().strip())),
        )

        # No required fields — remove startup hint and do not gate navigation on fields
        self.owner.meta_vars["event"].trace_add("write", lambda *_: None)
        self.owner.meta_vars["place"].trace_add("write", lambda *_: None)

        return frame

    def build_step_source(self) -> ttk.Frame:
        frame = ttk.Frame(self.step_frame)
        frame.columnconfigure(1, weight=1, uniform="metadata_fields")
        frame.columnconfigure(3, weight=1, uniform="metadata_fields")

        ttk.Label(frame, text="Schritt 2: Quelle / Rechte / Transkription", font=(None, 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.source_hint_var = tk.StringVar(value="Quellenfelder helfen bei späterer Recherche und sollten so vollständig wie möglich sein. Ohne Quellenangaben können Dokumente nicht verwendet werden oder sind nicht belastbar.")
        ttk.Label(frame, textvariable=self.source_hint_var, foreground="#555555", wraplength=820).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 10))

        source_fields = [
            ("Primärquelle", "primary_source"),
            ("Sekundärquelle", "secondary_source"),
            ("Standort Original", "original_location"),
            ("Archiv / Sammlung", "archive_name"),
            ("Signatur", "archive_signature"),
            ("Abruf am", "archive_accessed_at"),
        ]
        rights_fields = [
            ("Urheber/in", "copyright_author"),
            ("Rechteinhaber", "rights_holder"),
            ("Nutzungsfreigabe", "usage_permission"),
            ("Lizenz / Einschränkungen", "license_note"),
            ("Rechtehinweis", "rights_note"),
        ]

        source_row = 2
        for label, key in source_fields:
            ttk.Label(frame, text=f"{label}:").grid(row=source_row, column=0, sticky="w", pady=2)
            if key == "archive_name":
                widget = ttk.Combobox(
                    frame,
                    textvariable=self.owner.meta_vars[key],
                    values=self.owner.archive_collection_options(),
                    state="normal",
                )
                self.owner.upload_option_comboboxes[key] = widget
                self.configure_archive_autocomplete(widget)
            else:
                widget = ttk.Entry(frame, textvariable=self.owner.meta_vars[key])
            widget.grid(row=source_row, column=1, sticky="ew", padx=6, pady=2)
            source_row += 1

        rights_row = 2
        for label, key in rights_fields:
            ttk.Label(frame, text=f"{label}:").grid(row=rights_row, column=2, sticky=("nw" if key == "rights_note" else "w"), pady=2)
            if key == "rights_note":
                widget = tk.Text(frame, height=3, wrap="word", undo=True)
                self.bind_multiline_meta_field(key, widget)
            elif key == "license_note":
                widget = ttk.Combobox(
                    frame,
                    textvariable=self.owner.meta_vars[key],
                    values=[
                        "",
                        "A – frei nutzbar mit Namensnennung",
                        "B – Nutzung nur nach Rücksprache",
                        "C – nur interne Recherche - nicht veröffentlichen",
                        "D – Rechte unklar",
                    ],
                    state="readonly",
                )
            else:
                widget = ttk.Entry(frame, textvariable=self.owner.meta_vars[key])
            widget.grid(row=rights_row, column=3, sticky="ew", padx=6, pady=2)
            rights_row += 1

        row = max(source_row, rights_row)
        self.owner.meta_vars["secondary_source"].trace_add("write", lambda *_: self.update_navigation_state())

        return frame

    def build_step_persons(self) -> ttk.Frame:
        frame = ttk.Frame(self.step_frame)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Schritt 3: Personen", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="Nur bei Bilddateien relevant.").grid(row=1, column=0, sticky="w", pady=(0, 12))

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, sticky="w")
        ttk.Button(button_frame, text="Personen modifizieren", command=self.owner.open_person_tagger).pack(side="left")
        ttk.Label(button_frame, textvariable=self.owner.person_summary_var).pack(side="left", padx=(12, 0))

        self.person_step_hint = tk.StringVar(value="Wenn keine Bilddatei ausgewählt ist, wird dieser Schritt übersprungen.")
        ttk.Label(frame, textvariable=self.person_step_hint, foreground="#555555").grid(row=3, column=0, sticky="w", pady=(10, 0))

        return frame

    def build_step_description(self) -> ttk.Frame:
        frame = ttk.Frame(self.step_frame)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Schritt 4: Beschreibung / Bemerkungen", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="Beschreibung:").grid(row=1, column=0, sticky="nw", pady=2)
        self.owner.description_text = tk.Text(frame, height=6, wrap="word")
        self.owner.description_text.grid(row=2, column=0, sticky="nsew", padx=0, pady=2)
        self.owner.description_text.bind("<KeyRelease>", lambda _e: self.update_description_counter())

        ttk.Label(frame, textvariable=self.owner.upload_description_counter_var, foreground="#555555").grid(row=3, column=0, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="Bemerkung:").grid(row=4, column=0, sticky="nw", pady=2)
        self.owner.note_text = tk.Text(frame, height=4, wrap="word")
        self.owner.note_text.grid(row=5, column=0, sticky="nsew", padx=0, pady=2)
        frame.rowconfigure(2, weight=1)
        frame.rowconfigure(5, weight=0)

        return frame

    def build_step_review(self) -> ttk.Frame:
        frame = ttk.Frame(self.step_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Schritt 5: Übersicht", font=(None, 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.summary_text = tk.Text(frame, height=18, wrap="word", state="disabled")
        self.summary_text.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=2)
        points_frame = ttk.LabelFrame(frame, text="Potentielle Punkte", padding=8)
        points_frame.grid(row=1, column=1, sticky="nsew", pady=2)
        points_frame.columnconfigure(0, weight=1)
        points_frame.rowconfigure(0, weight=1)
        self.points_text = tk.Text(points_frame, height=18, wrap="word", state="disabled")
        self.points_text.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)

        return frame

    def show_step(self, step: int) -> None:
        if step < 0:
            return
        if step >= len(self.pages):
            return
        if step == 2 and not self.is_persons_step_available():
            step = 3
        for widget in self.step_frame.winfo_children():
            widget.grid_forget()
        self.pages[step].grid(row=0, column=0, sticky="nsew")
        self.current_step = step
        self.update_navigation_state()
        if step == 4:
            self.update_summary()

    def update_navigation_state(self) -> None:
        self.prev_button.configure(state="normal" if self.current_step > 0 else "disabled")
        if self.current_step == 4:
            self.next_button.configure(text="Hochladen", state="normal")
        else:
            self.next_button.configure(text="Weiter", state="normal")

    def can_continue_step_0(self) -> bool:
        return bool(self.owner.meta_vars["event"].get().strip() and self.owner.meta_vars["place"].get().strip())

    def can_continue_step_1(self) -> bool:
        return bool(self.owner.meta_vars["secondary_source"].get().strip())

    def is_persons_step_available(self) -> bool:
        return bool(self.owner.selected_file and is_image_file(self.owner.selected_file))

    def on_next(self) -> None:
        if self.current_step == 4:
            self.owner.submit_upload()
            return
        next_step = self.current_step + 1
        if next_step == 2 and not self.is_persons_step_available():
            next_step = 3
        self.show_step(next_step)

    def on_prev(self) -> None:
        prev_step = self.current_step - 1
        if prev_step == 2 and not self.is_persons_step_available():
            prev_step = 1
        self.show_step(prev_step)

    def update_description_counter(self) -> None:
        text = self.owner.description_text.get("1.0", "end-1c").strip()
        self.owner.upload_description_counter_var.set(f"Zeichen: {len(text)} / 50{' – punktefähig' if len(text) >= 50 else ''}")

    def keyword_count(self, text: str) -> int:
        return len([part for part in text.replace(";", ",").split(",") if part.strip()])

    def current_point_rules(self) -> dict[str, int]:
        defaults = {
            "description_metadata": 2,
            "metadata_description": 2,
            "keywords_metadata": 2,
            "metadata_keywords": 2,
            "source_metadata": 2,
            "metadata_source": 2,
            "usage_permission_metadata": 3,
            "rights_usage_permission": 3,
            "rights_note_metadata": 2,
            "rights_note": 2,
            "copyright_author_metadata": 2,
            "rights_author": 2,
            "rights_holder_metadata": 2,
            "rights_holder": 2,
            "archive_name_metadata": 1,
            "archive_signature_metadata": 2,
            "archive_signature": 2,
            "document_date_metadata": 1,
            "document_date": 1,
            "event_metadata": 1,
            "event_topic": 1,
            "transcription_short": 3,
            "transcription_full": 5,
            "transcription_difficult": 8,
            "persons_marked": 1,
            "persons_named": 2,
            "openai_metadata": 2,
        }
        try:
            if getattr(self.owner, "api_token", ""):
                resp = self.owner.api.list_point_rules(self.owner.api_token, self.owner._current_points_year())
                for rule in resp.get("rules", []) or []:
                    if int(rule.get("is_active", 1)) == 1:
                        defaults[str(rule.get("rule_key") or "")] = int(rule.get("points", 0) or 0)
        except Exception:
            pass
        return defaults

    def rule_points(self, rules: dict[str, int], field: str, fallback: str, default: int) -> tuple[str, int]:
        for key in (f"{field}_metadata", f"{field}_metadaten", fallback):
            if key in rules:
                return key, int(rules.get(key, default) or 0)
        return fallback, default

    def potential_points_lines(self) -> list[str]:
        rules = self.current_point_rules()
        checks = [
            ("document_date", "document_date", "document_date", 1, "Datum/Zeitraum"),
            ("event", "event", "event_topic", 1, "Ereignis"),
            ("description", "description", "metadata_description", 2, "Beschreibung"),
            ("keywords", "keywords", "metadata_keywords", 2, "Stichwörter"),
            ("source", "primary_source", "metadata_source", 2, "Quelle/Herkunft"),
            ("usage_permission", "usage_permission", "rights_usage_permission", 3, "Nutzungsfreigabe"),
            ("rights_note", "rights_note", "rights_note", 2, "Rechtehinweis"),
            ("copyright_author", "copyright_author", "rights_author", 2, "Urheber/in"),
            ("rights_holder", "rights_holder", "rights_holder", 2, "Rechteinhaber"),
            ("archive_name", "archive_name", "archive_name", 1, "Archiv/Sammlung"),
            ("archive_signature", "archive_signature", "archive_signature", 2, "Signatur"),
        ]
        lines: list[str] = []
        total = 0
        for field, meta_key, fallback, default, label in checks:
            if field == "description":
                value = self.owner.description_text.get("1.0", "end-1c").strip()
                eligible = len(value) >= 50
            elif field == "keywords":
                value = self.owner.meta_vars[meta_key].get().strip()
                eligible = self.keyword_count(value) >= 3
            elif field == "source":
                value = (self.owner.meta_vars["primary_source"].get().strip() or self.owner.meta_vars["secondary_source"].get().strip())
                eligible = bool(value)
            else:
                value = self.owner.meta_vars[meta_key].get().strip()
                eligible = bool(value)
            if eligible:
                rule_key, points = self.rule_points(rules, field, fallback, default)
                if points > 0:
                    total += points
                    lines.append(f"+ {points} {label} ({rule_key})")
        if self.owner.meta_vars["transcription_done"].get():
            trans_type = self.owner.meta_vars["transcription_type"].get().strip().lower()
            rule_key = "transcription_short"
            if "schwierig" in trans_type or "handschrift" in trans_type:
                rule_key = "transcription_difficult"
            elif "voll" in trans_type or "zeitung" in trans_type or "akte" in trans_type or "urkunde" in trans_type:
                rule_key = "transcription_full"
            points = int(rules.get(rule_key, 0) or 0)
            if points > 0:
                total += points
                lines.append(f"+ {points} Transkription ({rule_key})")
        persons = getattr(self.owner, "persons", []) or []
        if persons:
            points = int(rules.get("persons_marked", 1) or 0)
            if points > 0:
                total += points
                lines.append(f"+ {points} Personen markiert (persons_marked)")
            def person_name(person) -> str:
                if isinstance(person, dict):
                    return str(person.get("display_name") or person.get("name") or "")
                return str(getattr(person, "display_name", "") or getattr(person, "name", "") or "")
            if any(person_name(p).strip() for p in persons):
                points = int(rules.get("persons_named", 2) or 0)
                if points > 0:
                    total += points
                    lines.append(f"+ {points} Personen benannt (persons_named)")
        openai_fields = getattr(self.owner, "openai_metadata_applied_fields", []) or []
        if openai_fields:
            points = int(rules.get("openai_metadata", 2) or 0)
            if points > 0:
                total += points
                lines.append(f"+ {points} OpenAI-Metadaten (openai_metadata)")
        if not lines:
            return ["0 Punkte aktuell erkennbar"]
        return [f"{total} potentielle Punkte"] + lines

    def update_summary(self) -> None:
        if self.summary_text is None or self.points_text is None:
            return
        fields = [
            ("Datei", self.owner.file_var.get().strip()),
            ("Geplanter Dateiname", self.owner.meta_vars["current_filename"].get().strip()),
            ("Dokumenttyp", self.owner.meta_vars["document_type"].get().strip()),
            ("Datum / Zeitraum", self.owner.meta_vars["document_date"].get().strip()),
            ("Ereignis", self.owner.meta_vars["event"].get().strip()),
            ("Ort", self.owner.meta_vars["place"].get().strip()),
            ("Stichwörter", self.owner.meta_vars["keywords"].get().strip()),
            ("Primärquelle", self.owner.meta_vars["primary_source"].get().strip()),
            ("Sekundärquelle", self.owner.meta_vars["secondary_source"].get().strip()),
            ("Standort Original", self.owner.meta_vars["original_location"].get().strip()),
            ("Archiv", self.owner.meta_vars["archive_name"].get().strip()),
            ("Signatur", self.owner.meta_vars["archive_signature"].get().strip()),
            ("Abruf am", self.owner.meta_vars["archive_accessed_at"].get().strip()),
            ("Urheber/in", self.owner.meta_vars["copyright_author"].get().strip()),
            ("Rechteinhaber", self.owner.meta_vars["rights_holder"].get().strip()),
            ("Nutzungsfreigabe", self.owner.meta_vars["usage_permission"].get().strip()),
            ("Lizenz / Einschränkungen", self.owner.meta_vars["license_note"].get().strip()),
            ("Rechtehinweis", self.owner.meta_vars["rights_note"].get().strip()),
            ("Transkribiertes Dokument", "Ja" if self.owner.meta_vars["transcription_done"].get() else "Nein"),
            ("Transkriptionsart", self.owner.meta_vars["transcription_type"].get().strip()),
            ("Beschreibung", self.owner.description_text.get("1.0", "end-1c").strip()),
            ("Bemerkung", self.owner.note_text.get("1.0", "end-1c").strip()),
            ("Personen", self.owner.person_summary_var.get().strip()),
        ]
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        for label, value in fields:
            self.summary_text.insert("end", f"{label}: {value or '-'}\n")
        self.summary_text.configure(state="disabled")
        self.points_text.configure(state="normal")
        self.points_text.delete("1.0", "end")
        for line in self.potential_points_lines():
            self.points_text.insert("end", f"{line}\n")
        self.points_text.configure(state="disabled")
