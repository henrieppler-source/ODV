from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk, ImageDraw, ImageFont

from .file_service import is_image_file


class DisplayManagerMixin:
    def format_metadata_plain(self, item: dict) -> str:
        labels = {
            "upload_id": "Upload-ID",
            "original_filename": "Original-Dateiname",
            "stored_filename": "Gespeicherter Dateiname",
            "current_filename": "Aktueller Dateiname",
            "current_path": "Aktueller Pfad",
            "target_folder": "Zielordner",
            "uploaded_by": "Erfasst von",
            "uploaded_at": "Hochgeladen am",
            "status": "Status",
            "document_type": "Dokumenttyp",
            "primary_source": "Primärquelle",
            "secondary_source": "Sekundärquelle",
            "source": "Quelle",
            "original_location": "Standort Original",
            "document_date": "Datum / Zeitraum",
            "event": "Ereignis",
            "place": "Ort",
            "gps_coordinates": "GPS-Koordinaten",
            "gps_place": "GPS-Ort",
            "description": "Beschreibung",
            "status_note": "Statushinweis",
            "note": "Bemerkung",
            "rights_note": "Rechte / Nutzung allgemein",
            "copyright_author": "Urheber/in",
            "rights_holder": "Rechteinhaber",
            "usage_permission": "Nutzungsfreigabe",
            "license_note": "Lizenz / Einschränkungen",
            "archive_name": "Archiv",
            "archive_signature": "Signatur",
            "archive_accessed_at": "Abruf am",
            "person_status": "Personenstatus",
            "persons": "Personen",
            "history": "Historie",
        }
        order = [
            "upload_id", "original_filename", "stored_filename", "current_filename", "current_path",
            "uploaded_by", "uploaded_at", "status", "document_type", "primary_source", "secondary_source", "source", "original_location",
            "document_date", "event", "place", "gps_coordinates", "gps_place", "copyright_author", "rights_holder",
            "usage_permission", "license_note", "archive_name", "archive_signature", "archive_accessed_at",
            "description", "status_note", "note", "rights_note", "person_status", "persons", "history"
        ]
        lines: list[str] = []

        def add_value(label: str, value, indent: int = 0):
            prefix = "  " * indent
            if isinstance(value, list):
                lines.append(f"{prefix}{label}:")
                if not value:
                    lines.append(f"{prefix}  -")
                for i, entry in enumerate(value, 1):
                    if isinstance(entry, dict):
                        parts = []
                        if "timestamp" in entry:
                            parts.append(str(entry.get("timestamp", "")))
                        if "user_display_name" in entry:
                            parts.append(str(entry.get("user_display_name", "")))
                        if "action" in entry:
                            parts.append(str(entry.get("action", "")))
                        if "details" in entry:
                            parts.append(str(entry.get("details", "")))
                        if not parts:
                            parts = [f"{labels.get(k, k)}={v}" for k, v in entry.items()]
                        lines.append(f"{prefix}  {i}. " + " | ".join([p for p in parts if p]))
                    else:
                        lines.append(f"{prefix}  {i}. {entry}")
            elif isinstance(value, dict):
                lines.append(f"{prefix}{label}:")
                for k, v in value.items():
                    add_value(labels.get(k, k), v, indent + 1)
            else:
                text = "" if value is None else str(value)
                lines.append(f"{prefix}{label}: {text}")

        sections = [
            ("Technische Daten", ["upload_id", "original_filename", "stored_filename", "current_filename", "current_path", "target_folder", "status", "document_type"]),
            ("Upload / Bearbeitung", ["uploaded_by", "uploaded_at"]),
            ("Quelle / Herkunft", ["primary_source", "secondary_source", "source", "original_location"]),
            ("Zeit / Ort / Inhalt", ["document_date", "event", "place", "gps_coordinates", "gps_place", "description", "note"]),
            ("Rechte", ["copyright_author", "rights_holder", "usage_permission", "license_note", "rights_note"]),
            ("Archivdaten", ["archive_name", "archive_signature", "archive_accessed_at"]),
            ("Personen", ["person_status", "persons"]),
            ("Historie", ["history"]),
        ]
        seen = set()
        for heading, keys in sections:
            existing = [key for key in keys if key in item]
            if not existing:
                continue
            if lines:
                lines.append("")
            lines.append(heading)
            lines.append("-" * len(heading))
            for key in existing:
                add_value(labels.get(key, key), item.get(key))
                seen.add(key)
        rest = sorted(k for k in item.keys() if k not in seen)
        if rest:
            if lines:
                lines.append("")
            lines.append("Weitere Daten")
            lines.append("------------")
            for key in rest:
                add_value(labels.get(key, key), item.get(key))
        return "\n".join(lines)

    def draw_person_overlays(self, img: Image.Image, persons: list, show_persons: bool = True, font_size: int = 14) -> tuple[Image.Image, list[str]]:
        legend_lines: list[str] = []
        if not show_persons or not persons:
            return img, legend_lines
        draw = ImageDraw.Draw(img)
        w, h = img.size
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        for person in persons:
            try:
                x = float(person.get("x", 0)) * w
                y = float(person.get("y", 0)) * h
                number = str(person.get("number", "?"))
                name = str(person.get("name") or person.get("display_name") or "unbekannt")
                note = str(person.get("note") or "")
                certainty = str(person.get("certainty") or "")
                extra = ", ".join([v for v in [certainty, note] if v])
                legend_lines.append(f"{number}: {name}" + (f" ({extra})" if extra else ""))
                r = max(12, int(font_size * 0.9))
                draw.ellipse((x-r, y-r, x+r, y+r), fill="white", outline="red", width=2)
                bbox = draw.textbbox((0, 0), number, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((x - tw / 2, y - th / 2 - 1), number, fill="red", font=font)
            except Exception:
                continue
        return img, legend_lines

    def open_large_preview_window(self, path: Path, metadata: dict | None, title: str) -> None:
        if not path or not path.exists() or not is_image_file(path):
            return
        dialog = tk.Toplevel(self)
        dialog.title(title)
        try: self.track_window_geometry(dialog, title)
        except Exception: pass
        dialog.geometry("1100x800")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        show_var = tk.BooleanVar(value=True)
        top = ttk.Frame(dialog)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ttk.Checkbutton(top, text="Personen anzeigen", variable=show_var, command=lambda: render()).pack(side="left")
        label = ttk.Label(dialog, anchor="center")
        label.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        image_ref = {"img": None}
        persons = (metadata or {}).get("persons", []) or []
        def render():
            try:
                img = Image.open(path).convert("RGB")
                max_w = max(600, dialog.winfo_width() - 60)
                max_h = max(450, dialog.winfo_height() - 100)
                img.thumbnail((max_w, max_h))
                img, _legend = self.draw_person_overlays(img, persons, show_var.get(), font_size=18)
                image_ref["img"] = ImageTk.PhotoImage(img)
                label.configure(image=image_ref["img"], text="")
            except Exception as exc:
                label.configure(image="", text=f"Vorschaufehler:\n{exc}")
        dialog.bind("<Configure>", lambda _e: render())
        render()

    def open_large_file_preview(self) -> None:
        path = self.file_view_current_path
        if path and path.exists() and is_image_file(path):
            self.open_large_preview_window(path, self.file_view_current_metadata, path.name)

    def open_large_admin_preview(self) -> None:
        item = self.selected_admin_upload()
        if not item:
            return
        path_text = item.get("current_path") or ""
        path = Path(path_text) if path_text else None
        if path and path.exists() and is_image_file(path):
            self.open_large_preview_window(path, item, path.name)

