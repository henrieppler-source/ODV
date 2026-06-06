from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageFont

from .app_logging import app_log, app_log_exception
from .database import add_history
from .file_service import is_image_file, make_normalized_archive_filename, make_upload_id, save_metadata_file, unique_path_with_counter, append_metadata_history
from .models import HistoryEntry


class DocumentPdfManagerMixin:
    def create_person_master_sheet_pdf(self, path: Path, item: dict | None = None) -> None:
        """Erzeugt ein A4-Stammdatenblatt für Bilder mit Personenzuordnung."""
        item = item or self.item_for_local_path(path) or {}
        persons = item.get("persons") or []
        if not path.exists() or not is_image_file(path):
            messagebox.showwarning("Stammdatenblatt", "Bitte eine lokal vorhandene Bilddatei auswählen.")
            return
        if not persons:
            messagebox.showwarning("Stammdatenblatt", "Für dieses Bild sind keine Personen zugeordnet.")
            return
        target = filedialog.asksaveasfilename(
            title="Stammdatenblatt als PDF speichern",
            defaultextension=".pdf",
            initialfile=f"{path.stem}_stammdatenblatt.pdf",
            filetypes=[("PDF-Datei", "*.pdf")],
        )
        if not target:
            return
        try:
            page_w, page_h = 1240, 1754  # A4 bei ca. 150 dpi
            margin = 70
            page = Image.new("RGB", (page_w, page_h), "white")
            draw = ImageDraw.Draw(page)
            try:
                font_title = ImageFont.truetype("arial.ttf", 34)
                font_head = ImageFont.truetype("arial.ttf", 24)
                font = ImageFont.truetype("arial.ttf", 20)
                font_small = ImageFont.truetype("arial.ttf", 17)
            except Exception:
                font_title = font_head = font = font_small = ImageFont.load_default()

            title = "ODV-Stammdatenblatt mit Personenzuordnung"
            draw.text((margin, 35), title, fill="black", font=font_title)

            img = Image.open(path).convert("RGB")
            img.thumbnail((page_w - 2 * margin, 780))
            img, _legend = self.draw_person_overlays(img, persons, True, font_size=28)
            img_x = int((page_w - img.width) / 2)
            img_y = 95
            page.paste(img, (img_x, img_y))
            sep_y = 910
            draw.line((margin, sep_y, page_w - margin, sep_y), fill="black", width=2)

            y = sep_y + 25
            draw.text((margin, y), "Personen", fill="black", font=font_head)
            y += 35
            draw.text((margin, y), "Nr.", fill="black", font=font_small)
            draw.text((margin + 70, y), "Name", fill="black", font=font_small)
            draw.text((margin + 460, y), "Sicherheit", fill="black", font=font_small)
            draw.text((margin + 650, y), "Bemerkung", fill="black", font=font_small)
            y += 24
            draw.line((margin, y, page_w - margin, y), fill="#777777", width=1)
            y += 12
            for p in persons[:12]:
                number = str(p.get("number", ""))
                name = str(p.get("name") or p.get("display_name") or "")
                certainty = str(p.get("certainty") or "")
                note = str(p.get("note") or "")
                draw.text((margin, y), number, fill="black", font=font_small)
                draw.text((margin + 70, y), name[:38], fill="black", font=font_small)
                draw.text((margin + 460, y), certainty[:18], fill="black", font=font_small)
                draw.text((margin + 650, y), note[:45], fill="black", font=font_small)
                y += 26
            if len(persons) > 12:
                draw.text((margin, y), f"… weitere Personen: {len(persons) - 12}", fill="black", font=font_small)
                y += 28

            y += 12
            draw.text((margin, y), "Wichtige Dateidaten", fill="black", font=font_head)
            y += 34
            data_pairs = [
                ("Datei", item.get("current_filename") or path.name),
                ("Upload-/Erfassungs-ID", item.get("upload_id") or ""),
                ("Erfasst von", item.get("uploaded_by") or item.get("uploaded_by_name") or ""),
                ("Erfasst am", item.get("uploaded_at") or item.get("created_at") or ""),
                ("Ort", item.get("place") or ""),
                ("Datum / Zeitraum", item.get("document_date") or ""),
                ("Ereignis", item.get("event") or ""),
                ("Primärquelle", item.get("primary_source") or ""),
                ("Sekundärquelle", item.get("secondary_source") or item.get("source") or ""),
                ("Archiv / Signatur", " / ".join([v for v in [str(item.get("archive_name") or ""), str(item.get("archive_signature") or "")] if v])),
                ("Rechte", item.get("rights_note") or item.get("license_note") or ""),
            ]
            for label, value in data_pairs:
                if not value:
                    continue
                draw.text((margin, y), f"{label}:", fill="black", font=font_small)
                draw.text((margin + 260, y), str(value)[:80], fill="black", font=font_small)
                y += 25
            desc_lines = self.safe_text_lines(str(item.get("description") or ""), 85)[:4]
            if desc_lines:
                draw.text((margin, y), "Beschreibung:", fill="black", font=font_small)
                x = margin + 260
                for line in desc_lines:
                    draw.text((x, y), line, fill="black", font=font_small)
                    y += 23
            page.save(target, "PDF", resolution=150.0)
            messagebox.showinfo("Stammdatenblatt", f"Stammdatenblatt wurde erstellt:\n{target}")
        except Exception as exc:
            app_log_exception("Stammdatenblatt konnte nicht erstellt werden", exc, path=str(path))
            messagebox.showerror("Stammdatenblatt", f"PDF konnte nicht erstellt werden:\n{exc}")

    def show_file_tree_context_menu(self, event) -> None:
        iid = self.file_tree.identify_row(event.y)
        if not iid:
            return
        self.file_tree.selection_set(iid)
        values = self.file_tree.item(iid, "values")
        if not values:
            return
        path = Path(values[0])
        if not path.exists() or path.is_dir():
            return
        item = self.file_view_metadata_by_path.get(str(path)) or self.item_for_local_path(path) or {}
        self.file_view_current_path = path
        self.file_view_current_metadata = item if item else None
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Datei öffnen", command=lambda: self.open_file_with_default_app(path))
        menu.add_command(label="Download / Kopie speichern unter...", command=lambda: self.download_file_to_local_folder(path))
        if path.suffix.lower() == ".pdf":
            linked = self.linked_pdf_paths_for_item(item, path)
            if linked.get("ocr"):
                menu.add_command(label="OCR anzeigen", command=lambda p=linked["ocr"]: self.open_file_with_default_app(p))
            if linked.get("pdfa"):
                menu.add_command(label="Original / PDF-A anzeigen", command=lambda p=linked["pdfa"]: self.open_file_with_default_app(p))
            if self.is_current_admin():
                if self.pdf_size_mb(path) >= self.pdf_optimize_recommend_mb():
                    menu.add_command(label="PDF optimieren...", command=lambda: self.pdf_action_stub("PDF optimieren", path))
                if not linked.get("pdfa"):
                    menu.add_command(label="PDF/A erzeugen...", command=lambda: self.pdf_action_stub("PDF/A erzeugen", path))
        if is_image_file(path) and (item.get("persons") or []):
            menu.add_command(label="Stammdatenblatt als PDF speichern...", command=lambda: self.create_person_master_sheet_pdf(path, item))
        if is_image_file(path) and self.is_current_admin():
            menu.add_command(label="In PDF umwandeln...", command=lambda: self.convert_file_view_image_to_pdf(path))
        if self.is_current_admin():
            menu.add_separator()
            menu.add_command(label="Sonderpunkte zum Dokument...", command=lambda: self.open_manual_points_dialog(item=item if item.get("upload_id") else None))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def show_admin_tree_context_menu(self, event) -> None:
        iid = self.admin_tree.identify_row(event.y)
        if not iid:
            return
        # Bei Mehrfachauswahl darf ein Rechtsklick auf eine bereits markierte Zeile
        # die Auswahl nicht wieder auf eine Datei reduzieren. Sonst funktioniert
        # „Ausgewählte PDFs zusammenfassen“ praktisch nicht.
        if iid not in self.admin_tree.selection():
            self.admin_tree.selection_set(iid)
        self.show_selected_admin_details()
        item = self.selected_admin_upload()
        if not item:
            return
        self.normalize_admin_item_path_for_current_pc(item)
        path = self.resolve_document_local_path(item)
        menu = tk.Menu(self, tearoff=False)
        if path and path.exists() and path.is_file():
            menu.add_command(label="Datei öffnen", command=lambda: self.open_file_with_default_app(path))
            menu.add_command(label="Download / Kopie speichern unter...", command=lambda: self.download_file_to_local_folder(path, item))
            if path.suffix.lower() == ".pdf":
                linked = self.linked_pdf_paths_for_item(item, path)
                if linked.get("ocr"):
                    menu.add_command(label="OCR anzeigen", command=lambda p=linked["ocr"]: self.open_file_with_default_app(p))
                if linked.get("pdfa"):
                    menu.add_command(label="Original / PDF-A anzeigen", command=lambda p=linked["pdfa"]: self.open_file_with_default_app(p))
                if self.is_current_admin():
                    if self.pdf_size_mb(path) >= self.pdf_optimize_recommend_mb():
                        menu.add_command(label="PDF optimieren...", command=lambda: self.pdf_action_stub("PDF optimieren", path))
                    if not linked.get("pdfa"):
                        menu.add_command(label="PDF/A erzeugen...", command=lambda: self.pdf_action_stub("PDF/A erzeugen", path))
            if is_image_file(path) and (item.get("persons") or []):
                menu.add_command(label="Stammdatenblatt als PDF speichern...", command=lambda: self.create_person_master_sheet_pdf(path, item))
            if is_image_file(path):
                menu.add_command(label="Bild in PDF umwandeln", command=lambda: self.convert_admin_image_to_pdf(item))
            if len(self.admin_tree.selection()) >= 2:
                menu.add_command(label="Ausgewählte PDFs zusammenfassen...", command=self.merge_selected_admin_pdfs)
        else:
            menu.add_command(label="Datei nicht gefunden", state="disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def open_selected_admin_file(self) -> None:
        """Öffnet die in 'Dateien bearbeiten' gewählte Datei im Standardprogramm."""
        item = self.selected_admin_upload()
        if not item:
            return
        self.normalize_admin_item_path_for_current_pc(item)
        path = self.resolve_document_local_path(item)
        if not path or not path.exists() or not path.is_file():
            messagebox.showwarning("Datei öffnen", "Die Datei wurde im lokalen Nextcloud-Stammverzeichnis nicht gefunden.")
            return
        self.open_file_with_default_app(path)

    def merge_selected_admin_pdfs(self) -> None:
        if not self.require_admin():
            return
        if self.is_unified_file_view_active():
            selected_items = []
            selected_paths = []
            for iid in self.file_tree.selection():
                values = self.file_tree.item(iid, "values")
                if not values:
                    continue
                path = Path(values[0])
                if path.exists() and path.is_file() and path.suffix.lower() == ".pdf":
                    selected_paths.append(path)
                    item = self.file_view_metadata_by_path.get(str(path)) or self.item_for_local_path(path) or {
                        "current_filename": path.name,
                        "current_path": str(path),
                        "target_folder": str(path.parent),
                        "document_type": "PDF-Dokument",
                    }
                    selected_items.append(item)
            if len(selected_paths) < 2:
                messagebox.showwarning("PDF zusammenfassen", "Bitte mindestens zwei PDF-Dateien im Baum auswählen.")
                return
            pdf_paths = selected_paths
            default_name = make_normalized_archive_filename(selected_items[0], "zusammenfassung.pdf")
            initial_dir = str(pdf_paths[0].parent)
        else:
            selected_ids = list(self.admin_tree.selection())
            if len(selected_ids) < 2:
                messagebox.showwarning("PDF zusammenfassen", "Bitte mindestens zwei PDF-Dateien auswählen.")
                return
            # Reihenfolge: so wie die Dateien aktuell in der Liste angezeigt werden.
            ordered_ids = [iid for iid in self.admin_tree.get_children() if iid in selected_ids]
            selected_items = []
            for uid in ordered_ids:
                for item in self.admin_uploads:
                    if str(item.get("upload_id")) == str(uid):
                        self.normalize_admin_item_path_for_current_pc(item)
                        selected_items.append(item)
                        break
            pdf_paths: list[Path] = []
            for item in selected_items:
                p = self.resolve_document_local_path(item)
                if p and p.exists() and p.suffix.lower() == ".pdf":
                    pdf_paths.append(p)
            if len(pdf_paths) < 2:
                messagebox.showwarning("PDF zusammenfassen", "Unter der Auswahl wurden weniger als zwei lokal vorhandene PDF-Dateien gefunden.")
                return
            default_name = make_normalized_archive_filename(selected_items[0], "zusammenfassung.pdf")
            initial_dir = str(pdf_paths[0].parent)
        target = filedialog.asksaveasfilename(
            title="PDF zusammenfassen",
            initialdir=initial_dir,
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF-Datei", "*.pdf")],
        )
        if not target:
            return
        target_path = Path(target)
        try:
            from pypdf import PdfReader, PdfWriter
            writer = PdfWriter()
            for pdf in pdf_paths:
                reader = PdfReader(str(pdf))
                for page in reader.pages:
                    writer.add_page(page)
            with target_path.open("wb") as fh:
                writer.write(fh)
        except Exception as exc:
            app_log_exception("PDFs konnten nicht zusammengeführt werden", exc)
            messagebox.showerror("PDF zusammenfassen", f"PDF-Dateien konnten nicht zusammengeführt werden:\n{exc}")
            return
        source_item = dict(selected_items[0]) if selected_items else {}
        merged_item = dict(source_item)
        merged_item["upload_id"] = make_upload_id()
        merged_item["original_filename"] = "; ".join(p.name for p in pdf_paths)
        merged_item["stored_filename"] = target_path.name
        merged_item["current_filename"] = target_path.name
        merged_item["current_path"] = str(target_path)
        merged_item["target_folder"] = str(target_path.parent)
        merged_item["document_type"] = "PDF-Dokument"
        merged_item["status"] = "hochgeladen"
        merged_item["person_status"] = "none"
        merged_item["persons"] = []
        merged_item["history"] = []
        append_metadata_history(
            merged_item,
            self.display_name_var.get().strip() or "Admin",
            "PDFs zusammengeführt",
            " + ".join(p.name for p in pdf_paths) + f" → {target_path.name}",
        )
        api_ok, api_msg, metadata_file = self.register_pdf_item(merged_item)
        add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Admin", "PDFs zusammengeführt", f"{len(pdf_paths)} PDF-Dateien → {target_path.name} | {api_msg}", merged_item.get("upload_id")))
        self.refresh_admin_uploads(show_message=False)
        self.refresh_file_view_tree()
        self.refresh_history()
        messagebox.showinfo("PDF zusammenfassen", f"PDF wurde erstellt:\n{target_path}\n\nMetadaten:\n{metadata_file}\n\n{api_msg}")

    def image_to_pdf_file(self, image_path: Path, pdf_path: Path) -> None:
        """Wandelt eine einzelne Bilddatei in eine PDF-Datei um."""
        img = Image.open(image_path)
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, "white")
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(pdf_path, "PDF", resolution=300.0)

    def document_create_payload_from_item(self, item: dict) -> dict:
        return {
            "upload_id": item.get("upload_id"),
            "original_filename": item.get("original_filename") or item.get("current_filename") or "",
            "stored_filename": item.get("stored_filename") or item.get("current_filename") or "",
            "current_filename": item.get("current_filename") or item.get("stored_filename") or "",
            "target_folder": item.get("target_folder") or "",
            "current_path": item.get("current_path") or "",
            "uploaded_at": str(item.get("uploaded_at") or datetime.now().isoformat(timespec="seconds")).replace("T", " "),
            "status": item.get("status") or "hochgeladen",
            "person_status": item.get("person_status") or "none",
            "import_uploaded_by_user_id": item.get("import_uploaded_by_user_id") or "",
            "uploaded_by_user_id": item.get("uploaded_by_user_id") or "",
            "uploaded_by_name": item.get("uploaded_by_name") or item.get("uploaded_by") or "",
            "odv_capture_mode": item.get("odv_capture_mode") or "odv_upload",
            "odv_captured_by_admin": bool(item.get("odv_captured_by_admin", False)),
            "archived_from_path": item.get("archived_from_path", ""),
            "metadata": {
                "document_type": item.get("document_type", ""),
                "primary_source": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "primaerquelle": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "secondary_source": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "sekundaerquelle": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "source": item.get("secondary_source", item.get("source", "")),
                "quelle": item.get("secondary_source", item.get("source", "")),
                "original_location": item.get("original_location", ""),
                "standort_original": item.get("original_location", ""),
                "document_date": item.get("document_date", ""),
                "datum": item.get("document_date", ""),
                "event": item.get("event", ""),
                "ereignis": item.get("event", ""),
                "place": item.get("place", ""),
                "ort": item.get("place", ""),
                "description": item.get("description", ""),
                "beschreibung": item.get("description", ""),
                "note": item.get("note", ""),
                "bemerkung": item.get("note", ""),
                "copyright_author": item.get("copyright_author", ""),
                "urheber": item.get("copyright_author", ""),
                "rights_holder": item.get("rights_holder", ""),
                "rechteinhaber": item.get("rights_holder", ""),
                "usage_permission": item.get("usage_permission", ""),
                "nutzungsfreigabe": item.get("usage_permission", ""),
                "license_note": item.get("license_note", ""),
                "lizenz": item.get("license_note", ""),
                "rights_note": item.get("rights_note", ""),
                "rechte": item.get("rights_note", ""),
                "archive_name": item.get("archive_name", ""),
                "archiv": item.get("archive_name", ""),
                "archive_signature": item.get("archive_signature", ""),
                "signatur": item.get("archive_signature", ""),
                "archive_accessed_at": item.get("archive_accessed_at", ""),
                "abruf_am": item.get("archive_accessed_at", ""),
                "keywords": item.get("keywords", ""),
                "stichwoerter": item.get("keywords", ""),
                "transcription_done": item.get("transcription_done", ""),
                "transcription_type": item.get("transcription_type", ""),
                "transcription_note": item.get("transcription_note", ""),
            },
            "persons": item.get("persons", []) or [],
        }

    def create_pdf_metadata_item(self, source_path: Path, pdf_path: Path, source_item: dict | None) -> dict:
        display_name = self.display_name_var.get().strip() or "Benutzer"
        item = dict(source_item or {})
        item.pop("_metadata_file", None)
        item["upload_id"] = make_upload_id()
        item["original_filename"] = source_path.name
        item["stored_filename"] = pdf_path.name
        item["current_filename"] = pdf_path.name
        item["current_path"] = str(pdf_path)
        item["target_folder"] = str(pdf_path.parent)
        item["uploaded_by"] = display_name
        item["uploaded_at"] = datetime.now().isoformat(timespec="seconds")
        item["status"] = "hochgeladen"
        item["document_type"] = "PDF-Dokument"
        item["person_status"] = "none"
        item["persons"] = []
        item["source_image_path"] = str(source_path)
        item["history"] = []
        append_metadata_history(item, display_name, "PDF aus Bild erzeugt", f"{source_path} → {pdf_path}")
        return item

    def register_pdf_item(self, item: dict) -> tuple[bool, str, Path]:
        metadata_file = self.metadata_folder_path() / f"{item.get('upload_id')}.metadata.json"
        item["_metadata_file"] = str(metadata_file)
        save_metadata_file(metadata_file, item)
        api_ok, api_msg = False, "Kein API-Token vorhanden"
        if self.api_token:
            try:
                self.api.create_document(self.api_token, self.document_create_payload_from_item(item))
                api_ok, api_msg = True, "PDF-Metadaten wurden in MySQL gespeichert"
                append_metadata_history(item, self.display_name_var.get().strip() or "Benutzer", "MySQL gespeichert", api_msg)
                save_metadata_file(metadata_file, item)
            except ApiError as exc:
                api_msg = str(exc)
                append_metadata_history(item, self.display_name_var.get().strip() or "Benutzer", "MySQL nicht gespeichert", api_msg)
                save_metadata_file(metadata_file, item)
        return api_ok, api_msg, metadata_file

    def ask_delete_source_image(self, source_path: Path) -> None:
        if not source_path.exists():
            return
        if messagebox.askyesno("Bilddatei löschen?", "Die PDF-Datei wurde erzeugt.\n\nSoll die ursprüngliche Bilddatei gelöscht werden?\n\n" + str(source_path)):
            try:
                source_path.unlink()
                add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Benutzer", "Bilddatei gelöscht", str(source_path), None))
                app_log("info", "Bilddatei nach PDF-Umwandlung gelöscht", path=str(source_path))
            except Exception as exc:
                app_log_exception("Bilddatei konnte nicht gelöscht werden", exc, path=str(source_path))
                messagebox.showerror("Löschen fehlgeschlagen", f"Die Bilddatei konnte nicht gelöscht werden:\n{source_path}\n\n{exc}")

    def convert_file_view_image_to_pdf(self, path: Path | None = None) -> None:
        path = path or self.file_view_current_path
        if not path or not path.exists() or path.is_dir() or not is_image_file(path):
            messagebox.showwarning("Keine Bilddatei", "Bitte eine Bilddatei auswählen.")
            return
        default_pdf = unique_path_with_counter(path.with_suffix(".pdf"))
        target = filedialog.asksaveasfilename(
            title="Als PDF speichern",
            initialdir=str(path.parent),
            initialfile=default_pdf.name,
            defaultextension=".pdf",
            filetypes=[("PDF-Datei", "*.pdf")],
        )
        if not target:
            return
        pdf_path = Path(target)
        try:
            self.image_to_pdf_file(path, pdf_path)
        except Exception as exc:
            app_log_exception("Bild konnte nicht in PDF umgewandelt werden", exc, path=str(path))
            messagebox.showerror("PDF erzeugen", f"PDF konnte nicht erstellt werden:\n{exc}")
            return
        source_item = self.file_view_current_metadata or {}
        item = self.create_pdf_metadata_item(path, pdf_path, source_item)
        api_ok, api_msg, metadata_file = self.register_pdf_item(item)
        self.file_view_metadata_items.append(item)
        self.file_view_metadata_by_path[str(pdf_path)] = item
        add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Benutzer", "PDF aus Bild erzeugt", f"{path.name} → {pdf_path.name} | {api_msg}", item.get("upload_id")))
        messagebox.showinfo("PDF erzeugt", f"PDF wurde erstellt:\n{pdf_path}\n\nMetadaten:\n{metadata_file}\n\n{api_msg}")
        self.ask_delete_source_image(path)
        self.refresh_file_view_tree()
        self.refresh_admin_uploads(show_message=False)
        self.refresh_history()

    def convert_admin_image_to_pdf(self, item: dict | None = None) -> None:
        if not self.require_admin():
            return
        item = item or self.selected_admin_upload()
        if not item:
            return
        path_text = item.get("current_path") or ""
        path = Path(path_text) if path_text else None
        if not path or not path.exists() or path.is_dir() or not is_image_file(path):
            messagebox.showwarning("Keine Bilddatei", "Bitte eine Bilddatei auswählen.")
            return
        pdf_path = unique_path_with_counter(path.with_suffix(".pdf"))
        try:
            self.image_to_pdf_file(path, pdf_path)
        except Exception as exc:
            app_log_exception("Admin: Bild konnte nicht in PDF umgewandelt werden", exc, path=str(path))
            messagebox.showerror("PDF erzeugen", f"PDF konnte nicht erstellt werden:\n{exc}")
            return
        pdf_item = self.create_pdf_metadata_item(path, pdf_path, item)
        api_ok, api_msg, metadata_file = self.register_pdf_item(pdf_item)
        add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Admin", "PDF aus Bild erzeugt", f"{path.name} → {pdf_path.name} | {api_msg}", pdf_item.get("upload_id")))
        messagebox.showinfo("PDF erzeugt", f"PDF wurde erstellt:\n{pdf_path}\n\nMetadaten:\n{metadata_file}\n\n{api_msg}")
        self.ask_delete_source_image(path)
        self.refresh_admin_uploads(show_message=False)
        self.refresh_file_view_tree()
        self.refresh_history()

