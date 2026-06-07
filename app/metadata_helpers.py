from __future__ import annotations

import json
import re
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ExifTags

from .app_logging import app_log_exception
from .config import save_config
from .file_service import is_image_file, load_metadata_files

TRANSCRIPTION_TYPE_OPTIONS = [
    "",
    "kurze Transkription",
    "vollständige Transkription",
    "schwierige Handschrift",
    "Zeitung / Akte / Urkunde",
]

RIGHTS_NOTE_OPTIONS = [
    "",
    "A – frei nutzbar mit Namensnennung",
    "B – Nutzung nur nach Rücksprache",
    "C – nur interne Recherche - nicht veröffentlichen",
    "D – Rechte unklar",
]

DEFAULT_DOCUMENT_TYPE_OPTIONS = [
    "",
    "Bild",
    "PDF-Dokument",
    "Textdatei",
    "Tabellen-Datei",
    "Word-Dokument",
    "Video-Datei",
    "Audio-Datei",
    "Mehrere Dateien",
    "Sonstiges",
]

UPLOAD_REQUIRED_FIELDS = {"document_type", "current_filename", "uploaded_by", "uploaded_at", "document_date", "place", "description"}
UPLOAD_SIMPLE_FIELDS = {
    "document_type",
    "current_filename",
    "uploaded_by",
    "uploaded_at",
    "document_date",
    "place",
    "gps_coordinates",
    "gps_place",
    "keywords",
}
METADATA_OPTION_KEYS = {
    "primary_source",
    "secondary_source",
    "original_location",
    "copyright_author",
    "rights_holder",
    "usage_permission",
    "license_note",
    "archive_name",
    "archive_signature",
}
FIELD_HELP_TEXTS = {
    "primary_source": "Direkte Herkunft, z. B. Fotoalbum Familie Müller, Original im Privatbesitz oder Vereinsarchiv.",
    "secondary_source": "Indirekte Quelle, z. B. Buch, Zeitung, Website, Datenbank oder mündlicher Hinweis.",
    "original_location": "Wo liegt das Original heute? Beispiel: Privatbesitz, Stadtarchiv, Vereinsarchiv.",
    "archive_name": "Name des Archivs oder Bestands, falls bekannt.",
    "archive_signature": "Archivsignatur, Aktenzeichen oder Inventarnummer.",
    "archive_accessed_at": "Datum des Abrufs oder der Einsichtnahme.",
    "copyright_author": "Wer hat Foto/Text/Scan erstellt, soweit bekannt.",
    "rights_holder": "Wer darf über die Nutzung entscheiden.",
    "usage_permission": "Kurz notieren, ob und wofür eine Nutzung erlaubt ist.",
    "license_note": "Lizenz, Sperrfrist oder Einschränkung, z. B. nur intern.",
    "rights_note": "Allgemeiner Rechtehinweis für spätere Veröffentlichung oder interne Nutzung.",
    "document_date": "Aufnahme-, Ereignis- oder Dokumentdatum. Auch Zeiträume sind möglich.",
    "place": "Fachlicher Ort oder Ortsbezug, z. B. Milz, Römhild oder ein Ortsteil.",
    "gps_coordinates": "GPS-Koordinaten aus Bild-EXIF-Daten, falls vorhanden. Der fachliche Ort wird dadurch nicht automatisch ersetzt.",
    "gps_place": "Aus GPS-Koordinaten ermittelter Ortsname mit Koordinaten. Der fachliche Ort bleibt separat.",
    "keywords": "Mindestens 3 Stichwörter, getrennt durch Komma oder Semikolon.",
}

class ToolTip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _event=None) -> None:
        if self.window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            self.window = tk.Toplevel(self.widget)
            self.window.wm_overrideredirect(True)
            self.window.wm_geometry(f"+{x}+{y}")
            label = ttk.Label(self.window, text=self.text, padding=6, relief="solid", borderwidth=1, wraplength=320)
            label.pack()
        except Exception:
            self.window = None

    def hide(self, _event=None) -> None:
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None

class MetadataHelpersMixin:
    def document_type_options(self) -> list[str]:
        values = list(DEFAULT_DOCUMENT_TYPE_OPTIONS)
        for dt in self.config_data.get("document_type_options", []) or []:
            text = str(dt or "").strip()
            if text and text not in values:
                values.append(text)
        return values

    def remember_document_type(self, value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        values = self.document_type_options()
        if text not in values:
            values.append(text)
            self.config_data["document_type_options"] = values
            save_config(self.config_data)
        self.update_document_type_comboboxes()

    def update_document_type_comboboxes(self) -> None:
        values = self.document_type_options()
        for name in ("upload_document_type_combo", "admin_document_type_combo"):
            widget = self.upload_document_type_combo if name == "upload_document_type_combo" else self.admin_document_type_combo
            if widget is not None:
                try:
                    widget["values"] = values
                except Exception:
                    pass

    def archive_collection_options(self, limit: int | None = None) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for text in self.config_data.get("archive_collection_options", []) or []:
            value = str(text or "").strip()
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                values.append(value)
        for text in self.metadata_value_options("archive_name", limit=500):
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                values.append(text)
        values.sort(key=str.casefold)
        return values[:limit] if limit else values

    def remember_archive_collection(self, value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        values = self.archive_collection_options()
        if text.casefold() not in {v.casefold() for v in values}:
            values.append(text)
            values.sort(key=str.casefold)
            self.config_data["archive_collection_options"] = values
            save_config(self.config_data)
        self.refresh_upload_metadata_option_comboboxes()

    def metadata_value_options(self, key: str, limit: int = 10) -> list[str]:
        counts: dict[str, int] = {}
        try:
            items = load_metadata_files(self.metadata_folder_path())
        except Exception:
            items = []
        aliases = {
            "primary_source": ["primary_source", "primaerquelle"],
            "secondary_source": ["secondary_source", "sekundaerquelle", "source", "quelle"],
            "copyright_author": ["copyright_author", "urheber"],
            "rights_holder": ["rights_holder", "rechteinhaber"],
            "usage_permission": ["usage_permission", "nutzungsfreigabe"],
            "license_note": ["license_note", "lizenz"],
            "rights_note": ["rights_note", "rechte"],
            "archive_name": ["archive_name", "archiv"],
            "archive_signature": ["archive_signature", "signatur"],
            "original_location": ["original_location", "standort_original"],
        }.get(key, [key])
        for item in items:
            for alias in aliases:
                text = str(item.get(alias) or "").strip()
                if text:
                    counts[text] = counts.get(text, 0) + 1
        if key == "archive_name":
            configured = {text.casefold(): text for text in self.config_data.get("archive_collection_options", []) or [] if str(text or "").strip()}
            for text in configured.values():
                counts.setdefault(text, 0)
            return [text for text, _count in sorted(counts.items(), key=lambda x: x[0].casefold())[:limit]]
        return [text for text, _count in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))[:limit]]

    def refresh_upload_metadata_option_comboboxes(self) -> None:
        for key, widget in self.upload_option_comboboxes.items():
            try:
                widget.configure(values=(self.archive_collection_options() if key == "archive_name" else self.metadata_value_options(key)))
            except Exception:
                pass

    def add_field_tooltip(self, label_widget: tk.Widget, key: str) -> None:
        text = FIELD_HELP_TEXTS.get(key, "")
        if text:
            ToolTip(label_widget, text)

    def exif_gps_decimal(self, values) -> float | None:
        try:
            parts = []
            for v in values:
                numerator = None
                denominator = None
                try:
                    numerator = v.numerator
                    denominator = v.denominator
                except Exception:
                    pass
                if numerator is not None and denominator is not None:
                    parts.append(float(numerator) / float(denominator))
                elif isinstance(v, tuple) and len(v) == 2:
                    parts.append(float(v[0]) / float(v[1]))
                else:
                    parts.append(float(v))
            return parts[0] + parts[1] / 60 + parts[2] / 3600
        except Exception:
            return None

    def image_metadata_suggestions(self, path: Path) -> dict[str, str]:
        suggestions: dict[str, str] = {}
        if not is_image_file(path):
            return suggestions
        try:
            with Image.open(path) as img:
                exif = img.getexif()
                if not exif:
                    return suggestions
                tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
                date_text = str(tag_map.get("DateTimeOriginal") or tag_map.get("DateTimeDigitized") or tag_map.get("DateTime") or "").strip()
                if date_text:
                    suggestions["document_date"] = date_text.replace(":", "-", 2)
                try:
                    ifd = ExifTags.IFD
                except Exception:
                    ifd = None
                gps_ifd = exif.get_ifd(ifd.GPSInfo) if ifd else {}
                if gps_ifd:
                    gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
                    lat = self.exif_gps_decimal(gps.get("GPSLatitude"))
                    lon = self.exif_gps_decimal(gps.get("GPSLongitude"))
                    if lat is not None and lon is not None:
                        if str(gps.get("GPSLatitudeRef", "")).upper() == "S":
                            lat *= -1
                        if str(gps.get("GPSLongitudeRef", "")).upper() == "W":
                            lon *= -1
                        coords = f"{lat:.6f}, {lon:.6f}"
                        gps_place = self.reverse_geocode_gps_place(lat, lon)
                        if gps_place:
                            suggestions["gps_coordinates"] = f"{coords} ({gps_place})"
                            suggestions["gps_place"] = gps_place
                        else:
                            suggestions["gps_coordinates"] = coords
        except Exception as exc:
            app_log_exception("EXIF-Metadaten konnten nicht gelesen werden", exc, path=str(path))
        return suggestions

    def reverse_geocode_gps_place(self, lat: float, lon: float) -> str:
        """Ermittelt einen deutschen Ortsnamen zu GPS-Koordinaten, sofern online möglich."""
        coords = f"{lat:.6f}, {lon:.6f}"
        try:
            query = urlencode({
                "format": "jsonv2",
                "lat": f"{lat:.6f}",
                "lon": f"{lon:.6f}",
                "zoom": "14",
                "addressdetails": "1",
                "accept-language": "de",
            })
            request = Request(
                f"https://nominatim.openstreetmap.org/reverse?{query}",
                headers={"User-Agent": "ODV-Ortschronik/1.0"},
            )
            with urlopen(request, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            address = data.get("address") if isinstance(data, dict) else {}
            if isinstance(address, dict):
                for key in ("city", "town", "village", "municipality", "hamlet", "suburb", "county"):
                    name = str(address.get(key) or "").strip()
                    if name:
                        return name
            display_name = str(data.get("display_name") or "").strip() if isinstance(data, dict) else ""
            if display_name:
                return display_name.split(",")[0].strip()
        except Exception as exc:
            app_log_exception("GPS-Ort konnte nicht ermittelt werden", exc)
        return ""

    def apply_image_metadata_suggestions(self, path: Path) -> None:
        suggestions = self.image_metadata_suggestions(path)
        gps_place = str(suggestions.get("gps_place") or "").strip()
        meta_vars = self.meta_vars
        if gps_place and isinstance(meta_vars, dict) and meta_vars.get("place") is not None:
            meta_vars["place"].set(gps_place)
        for key, value in suggestions.items():
            var = meta_vars.get(key) if isinstance(meta_vars, dict) else None
            if var is not None and not str(var.get() or "").strip():
                var.set(value)

    def refresh_document_type_options_from_documents(self, docs: list[dict]) -> None:
        changed = False
        values = self.document_type_options()
        for doc in docs:
            text = str(doc.get("document_type") or "").strip()
            if text and text not in values:
                values.append(text)
                changed = True
        if changed:
            self.config_data["document_type_options"] = values
            save_config(self.config_data)
            self.update_document_type_comboboxes()


    def description_char_count_text(self, widget: tk.Text) -> str:
        try:
            count = len(widget.get("1.0", "end-1c").strip())
        except Exception:
            count = 0
        suffix = " – punktefähig" if count >= 50 else ""
        return f"Zeichen: {count} / 50{suffix}"

    def update_description_counter(self, widget: tk.Text, label_var: tk.StringVar) -> None:
        label_var.set(self.description_char_count_text(widget))

    def normalize_description_text(self, text: str | None) -> str:
        """Speichert Beschreibungen mit einheitlichem Einstieg."""
        value = str(text or "").strip()
        if not value:
            return ""
        prefix = "enthält u.a."
        if value.casefold().startswith(prefix.casefold()):
            return value
        return f"{prefix} {value}"

    def make_scrolled_text(self, parent, height: int = 4, wrap: str = "word") -> tuple[tk.Text, ttk.Frame]:
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        txt = tk.Text(frame, height=height, wrap=wrap, undo=True)
        vbar = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        hbar = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        txt.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        if wrap == "none":
            hbar.grid(row=1, column=0, sticky="ew")
        return txt, frame

    def create_metadata_form_two_columns(self, parent: tk.Widget, target: str) -> dict[str, object]:
        """Erzeugt ein zweispaltiges Metadatenformular.

        target = "file_view", "admin" oder "upload". Die Rückgabe enthält Variablen,
        Textfelder und Widgets zur späteren Befüllung/Sperrung.
        """
        result: dict[str, object] = {"vars": {}, "widgets": [], "advanced_widgets": []}
        for c in (1, 3):
            parent.columnconfigure(c, weight=1, uniform=f"{target}_meta")

        row_offset = 1 if target == "upload" else 0
        technical_fields = [
                ("Upload-ID", "upload_id"),
                ("Dokumenttyp", "document_type"),
                ("Status", "status"),
                ("Geplanter Dateiname", "current_filename") if target == "upload" else ("Aktueller Dateiname", "current_filename"),
                ("Erfasst von", "uploaded_by"),
                ("Hochgeladen am", "uploaded_at"),
        ]
        if target in {"admin", "file_view"}:
            technical_fields.extend([
                ("Bearbeitet von", "edited_by"),
                ("Bearbeitet am", "edited_at"),
            ])
        lower_sections_row = row_offset + (10 if target in {"admin", "file_view"} else 8)
        sections = [
            (row_offset + 0, 0, "Technische Daten", technical_fields),
            (row_offset + 0, 2, "Quelle / Herkunft", [
                ("Primärquelle", "primary_source"),
                ("Sekundärquelle", "secondary_source"),
                ("Standort Original", "original_location"),
                ("Archiv", "archive_name"),
                ("Signatur", "archive_signature"),
                ("Abruf am", "archive_accessed_at"),
                ("Transkription", "_transcription_combined"),
            ]),
            (lower_sections_row, 0, "Zeit / Ort / Inhalt", [
                ("Datum / Zeitraum", "document_date"),
                ("Ort", "place"),
                ("GPS-Koordinaten", "gps_coordinates"),
                ("Ereignis", "event"),
                ("Stichwörter", "keywords"),
            ]),
            (lower_sections_row, 2, "Rechte", [
                ("Urheber/in", "copyright_author"),
                ("Rechteinhaber", "rights_holder"),
                ("Nutzungsfreigabe", "usage_permission"),
                ("Lizenz / Einschränkungen", "license_note"),
                ("Rechte / Nutzung allgemein", "rights_note"),
            ]),
        ]
        all_vars: dict[str, tk.Variable] = result["vars"]  # type: ignore[assignment]
        widgets: list[tk.Widget] = result["widgets"]  # type: ignore[assignment]
        advanced_widgets: list[tk.Widget] = result["advanced_widgets"]  # type: ignore[assignment]
        max_row = 0
        for row0, col0, heading, fields in sections:
            heading_widget = ttk.Label(parent, text=heading, font=("", 10, "bold"))
            heading_widget.grid(row=row0, column=col0, columnspan=2, sticky="w", pady=(8, 3), padx=(0 if col0 == 0 else 18, 4))
            if target == "upload" and all(key not in UPLOAD_SIMPLE_FIELDS for _label, key in fields):
                advanced_widgets.append(heading_widget)
            row = row0 + 1
            for label, key in fields:
                label_text = f"{label}{' *' if target == 'upload' and key in UPLOAD_REQUIRED_FIELDS else ''}:"
                label_widget = ttk.Label(parent, text=label_text)
                label_widget.grid(row=row, column=col0, sticky="w", pady=2, padx=(0 if col0 == 0 else 18, 4))
                if target == "upload":
                    self.add_field_tooltip(label_widget, key)
                    if key not in UPLOAD_SIMPLE_FIELDS:
                        advanced_widgets.append(label_widget)
                if key == "_transcription_combined":
                    trans_frame = ttk.Frame(parent)
                    trans_frame.grid(row=row, column=col0 + 1, sticky="w", padx=6, pady=2)
                    done_var = tk.BooleanVar(value=False)
                    type_var = tk.StringVar()
                    all_vars["transcription_done"] = done_var
                    all_vars["transcription_type"] = type_var
                    check = ttk.Checkbutton(trans_frame, text="ja", variable=done_var)
                    check.pack(side="left")
                    ttk.Label(trans_frame, text="Art:").pack(side="left", padx=(16, 4))
                    combo = ttk.Combobox(trans_frame, textvariable=type_var, values=TRANSCRIPTION_TYPE_OPTIONS, width=28, state="readonly")
                    combo.pack(side="left")
                    if target == "file_view":
                        check.configure(command=lambda: self.save_file_view_metadata(auto=True))
                        combo.bind("<<ComboboxSelected>>", lambda _e: self.save_file_view_metadata(auto=True))
                    elif target == "admin":
                        check.configure(command=lambda: self.admin_save_metadata_fields(auto=True))
                        combo.bind("<<ComboboxSelected>>", lambda _e: self.admin_save_metadata_fields(auto=True))
                    widgets.extend([check, combo])
                    if target == "upload":
                        advanced_widgets.append(trans_frame)
                    row += 1
                    continue
                elif key == "upload_id":
                    var = tk.StringVar()
                    all_vars[key] = var
                    widget = tk.Label(parent, textvariable=var, anchor="w", bg="#e6e6e6", padx=4, pady=2)
                    widget.grid(row=row, column=col0 + 1, sticky="ew", padx=6, pady=2)
                elif key == "uploaded_by" and target in {"admin", "file_view", "upload"}:
                    var = tk.StringVar()
                    all_vars[key] = var
                    if target == "admin":
                        widget = ttk.Combobox(parent, textvariable=var, values=[], width=32, state="readonly")
                        self.admin_uploaded_by_combo = widget
                        self.admin_uploaded_by_user_map = {}
                        widget.bind("<Button-1>", lambda _e: setattr(self, "_admin_uploaded_by_user_interaction", True), add="+")
                        widget.bind("<KeyPress>", lambda _e: setattr(self, "_admin_uploaded_by_user_interaction", True), add="+")
                        widget.bind("<<ComboboxSelected>>", self.admin_uploaded_by_changed)
                    elif target == "file_view":
                        widget = ttk.Combobox(parent, textvariable=var, values=[], width=32, state="readonly")
                        self.file_view_uploaded_by_combo = widget
                        self.file_view_uploaded_by_user_map = {}
                        widget.bind("<Button-1>", lambda _e: setattr(self, "_file_view_uploaded_by_user_interaction", True), add="+")
                        widget.bind("<KeyPress>", lambda _e: setattr(self, "_file_view_uploaded_by_user_interaction", True), add="+")
                        widget.bind("<<ComboboxSelected>>", self.file_view_uploaded_by_changed)
                    else:
                        widget = ttk.Entry(parent, textvariable=var, state="disabled")
                    widget.grid(row=row, column=col0 + 1, sticky="ew", padx=6, pady=2)
                elif key == "document_type":
                    var = tk.StringVar()
                    all_vars[key] = var
                    widget = ttk.Combobox(parent, textvariable=var, values=self.document_type_options(), width=28, state="normal")
                    widget.grid(row=row, column=col0 + 1, sticky="w", padx=6, pady=2)
                    if target == "file_view":
                        widget.bind("<<ComboboxSelected>>", lambda _e: self.save_file_view_metadata(auto=True))
                        widget.bind("<FocusOut>", lambda _e: self.save_file_view_metadata(auto=True))
                    elif target == "admin":
                        self.admin_document_type_combo = widget
                        widget.bind("<<ComboboxSelected>>", lambda _e: self.admin_save_metadata_fields(auto=True))
                        widget.bind("<FocusOut>", lambda _e: self.admin_save_metadata_fields(auto=True))
                    else:
                        self.upload_document_type_combo = widget
                elif key == "rights_note":
                    var = tk.StringVar()
                    all_vars[key] = var
                    widget_state = "normal" if target == "upload" else "readonly"
                    widget = ttk.Combobox(parent, textvariable=var, values=RIGHTS_NOTE_OPTIONS, width=42, state=widget_state)
                    widget.grid(row=row, column=col0 + 1, sticky="w", padx=6, pady=2)
                    if target == "file_view":
                        widget.bind("<<ComboboxSelected>>", lambda _e: self.save_file_view_metadata(auto=True))
                    elif target == "admin":
                        widget.bind("<<ComboboxSelected>>", lambda _e: self.admin_save_metadata_fields(auto=True))
                else:
                    var = tk.StringVar()
                    all_vars[key] = var
                    state = "disabled" if key in {"gps_coordinates", "gps_place", "edited_by", "edited_at"} or (target == "upload" and key in {"status", "current_filename", "uploaded_at"}) else "normal"
                    if target == "upload" and key in METADATA_OPTION_KEYS:
                        widget = ttk.Combobox(parent, textvariable=var, values=self.metadata_value_options(key), state="normal")
                        if not isinstance(self.upload_option_comboboxes, dict):
                            self.upload_option_comboboxes = {}
                        self.upload_option_comboboxes[key] = widget
                    else:
                        widget = ttk.Entry(parent, textvariable=var, state=state)
                    widget.grid(row=row, column=col0 + 1, sticky="ew", padx=6, pady=2)
                    if target == "file_view":
                        widget.bind("<FocusOut>", lambda _e: self.save_file_view_metadata(auto=True))
                    elif target == "admin":
                        widget.bind("<FocusOut>", lambda _e: self.admin_save_metadata_fields(auto=True))
                if key not in {"edited_by", "edited_at"}:
                    widgets.append(widget)
                if target == "upload" and key not in UPLOAD_SIMPLE_FIELDS:
                    advanced_widgets.append(widget)
                row += 1
                if key == "keywords":
                    ttk.Label(
                        parent,
                        text="Für Punkte: mind. 3 Stichwörter (Komma/Semikolon).",
                        foreground="#555555",
                    ).grid(row=row, column=col0 + 1, sticky="w", padx=6, pady=(0, 3))
                    row += 1
            max_row = max(max_row, row)

        row = max_row + 1
        desc_label = ttk.Label(parent, text=f"Beschreibung{' *' if target == 'upload' else ''}:")
        desc_label.grid(row=row, column=0, sticky="nw", pady=2)
        desc_text, desc_frame = self.make_scrolled_text(parent, height=4, wrap="word")
        desc_frame.grid(row=row, column=1, columnspan=3, sticky="ew", padx=6, pady=2)
        widgets.append(desc_text)
        desc_counter_var = tk.StringVar(value=self.description_char_count_text(desc_text))
        desc_text.bind("<KeyRelease>", lambda _e, w=desc_text, v=desc_counter_var: self.update_description_counter(w, v), add="+")
        row += 1
        ttk.Label(parent, textvariable=desc_counter_var, foreground="#555555").grid(row=row, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 0))
        row += 1
        ttk.Label(parent, text="Für Punkte: mind. 50 Zeichen.", foreground="#555555").grid(row=row, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 3))
        row += 1
        note_label = ttk.Label(parent, text="Bemerkung:")
        note_label.grid(row=row, column=0, sticky="nw", pady=2)
        note_text, note_frame = self.make_scrolled_text(parent, height=3, wrap="word")
        note_frame.grid(row=row, column=1, columnspan=3, sticky="ew", padx=6, pady=2)
        widgets.append(note_text)
        if target == "upload":
            advanced_widgets.extend([note_label, note_frame])
        row += 1
        json_label = ttk.Label(parent, text="Metadaten / Historie:")
        json_label.grid(row=row, column=0, sticky="nw", pady=2)
        json_text, json_frame = self.make_scrolled_text(parent, height=8, wrap="none")
        json_frame.grid(row=row, column=1, columnspan=3, sticky="nsew", padx=6, pady=2)
        small_font = tkfont.nametofont("TkDefaultFont").copy()
        try:
            small_font.configure(size=max(7, small_font.cget("size") - 1))
        except Exception:
            pass
        json_text.configure(state="disabled", font=small_font)
        parent.rowconfigure(row, weight=1)
        if target == "upload":
            advanced_widgets.extend([json_label, json_frame])

        if target == "file_view":
            desc_text.bind("<FocusOut>", lambda _e: self.save_file_view_metadata(auto=True))
            note_text.bind("<FocusOut>", lambda _e: self.save_file_view_metadata(auto=True))
            ttk.Button(parent, text="Metadaten speichern", command=lambda: self.save_file_view_metadata(auto=False)).grid(row=row + 1, column=1, sticky="w", padx=6, pady=6)
        elif target == "admin":
            desc_text.bind("<FocusOut>", lambda _e: self.admin_save_metadata_fields(auto=True))
            note_text.bind("<FocusOut>", lambda _e: self.admin_save_metadata_fields(auto=True))
            ttk.Button(parent, text="Metadaten speichern", command=lambda: self.admin_save_metadata_fields(auto=False)).grid(row=row + 1, column=3, sticky="e", padx=6, pady=6)
        else:
            json_text.configure(state="normal")
            json_text.delete("1.0", "end")
            json_text.insert("1.0", "Upload-ID und Historie werden beim Hochladen angelegt.")
            json_text.configure(state="disabled")

        result["description_text"] = desc_text
        result["description_counter_var"] = desc_counter_var
        result["note_text"] = note_text
        result["json_text"] = json_text
        return result


    def filename_keyword_suggestions(self, path: Path) -> list[str]:
        """Leitet einfache Stichwortvorschläge aus dem Dateinamen ab.

        Datum, Ort und Dateiendung werden herausgefiltert. Die Vorschläge werden
        nur als Vorbelegung genutzt und können vom Bearbeiter gelöscht/ergänzt werden.
        """
        stem = path.stem
        norm = self.normalize_folder_token(stem)
        # Technisch sauberer: Dateiname zunächst in Segmente zerlegen.
        raw = stem.replace('-', '_').replace(' ', '_')
        parts = [p for p in re.split(r"[_\s\-]+", raw) if p]
        stop = {
            "jpg", "jpeg", "png", "pdf", "doc", "docx", "odt", "xls", "xlsx", "tif", "tiff",
            "scan", "datei", "pxl", "img", "dsc", "dcim", "raw", "cover", "mp", "wa",
            "whatsapp", "image", "photo", "foto", "screenshot", "edited", "kopie",
        }
        place_tokens = set()
        try:
            place_tokens.add(self.normalize_folder_token(self.meta_vars.get("place").get()))
            place_tokens.add(self.normalize_folder_token(self.place_var.get()))
        except Exception:
            pass
        out=[]; seen=set()
        for part in parts:
            token = self.normalize_folder_token(part)
            if not token or token in seen:
                continue
            if token in stop or token in place_tokens:
                continue
            if any(ch.isdigit() for ch in token):
                continue
            if re.fullmatch(r"\d{2,8}", token) or token == "0000":
                continue
            if len(token) < 4:
                continue
            if re.fullmatch(r"[a-z]{1,4}", token) and token in stop:
                continue
            seen.add(token)
            out.append(token)
        return out

    def apply_filename_keyword_suggestions(self, path: Path) -> None:
        """Trägt Stichwortvorschläge aus dem Dateinamen ins Stichwortfeld ein."""
        if "keywords" not in self.meta_vars:
            return
        suggestions = self.filename_keyword_suggestions(path)
        if not suggestions:
            return
        current = str(self.meta_vars["keywords"].get() or "").strip()
        current_parts = [p.strip() for p in re.split(r"[,;]", current) if p.strip()]
        seen = {self.normalize_folder_token(p) for p in current_parts}
        for suggestion in suggestions:
            if self.normalize_folder_token(suggestion) not in seen:
                current_parts.append(suggestion)
                seen.add(self.normalize_folder_token(suggestion))
        self.meta_vars["keywords"].set(", ".join(current_parts))
