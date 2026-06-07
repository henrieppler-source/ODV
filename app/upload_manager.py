from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import shutil

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from .app_logging import app_log_exception
from .config import save_config
from .file_service import copy_with_metadata, make_upload_id, save_metadata_file, unique_path_with_counter, append_metadata_history
from .upload_tab_openai_cache_utils import file_sha256
from .models import HistoryEntry, UploadMetadata
from .database import add_history
from .api_client import ApiError
import re


class UploadManagerMixin:
    def api_document_to_item(self, document: dict, persons: list | None = None, history: list | None = None) -> dict:
        """Wandelt einen API-Dokumentdatensatz in die lokale Metadatenstruktur der Oberfläche um."""
        item = dict(document or {})
        item["uploaded_by"] = item.get("uploaded_by_name") or item.get("uploaded_by") or ""
        item.setdefault("uploaded_by_user_id", item.get("user_id", ""))
        item["persons"] = persons if persons is not None else item.get("persons", []) or []
        item["history"] = history if history is not None else item.get("history", []) or []
        # Zusatzinformationen aus json_metadata übernehmen, sofern vorhanden.
        raw_json_metadata = item.get("json_metadata")
        if isinstance(raw_json_metadata, str) and raw_json_metadata.strip():
            try:
                parsed_json_metadata = json.loads(raw_json_metadata)
                if isinstance(parsed_json_metadata, dict):
                    for extra_key in (
                        "odv_capture_mode",
                        "odv_captured_by_admin",
                        "archived_from_path",
                        "ocr_pdf_path",
                        "ocr_pdf_filename",
                        "ocr_source_filename",
                        "ocr_created_at",
                        "openai_metadata_fields",
                        "openai_metadata_model",
                        "openai_metadata_applied_at",
                        "openai_model_results",
                        "edited_by",
                        "edited_at",
                        "openai_place_contexts",
                        "openai_place_contexts_updated_at",
                        "openai_place_contexts_model",
                        "openai_place_model_results",
                        "status_note",
                        "gps_coordinates",
                        "gps_place",
                    ):
                        if extra_key in parsed_json_metadata and extra_key not in item:
                            item[extra_key] = parsed_json_metadata.get(extra_key)
                    metadata = parsed_json_metadata.get("metadata") if isinstance(parsed_json_metadata.get("metadata"), dict) else {}
                    for meta_key in (
                        "primary_source",
                        "secondary_source",
                        "source",
                        "original_location",
                        "document_date",
                        "event",
                        "place",
                        "gps_coordinates",
                        "gps_place",
                        "description",
                        "note",
                        "copyright_author",
                        "rights_holder",
                        "usage_permission",
                        "license_note",
                        "rights_note",
                        "archive_name",
                        "archive_signature",
                        "archive_accessed_at",
                        "keywords",
                        "transcription_done",
                        "transcription_type",
                        "transcription_note",
                    ):
                        if meta_key in metadata and not item.get(meta_key):
                            item[meta_key] = metadata.get(meta_key)
                    if "gps_coordinates" in metadata and "gps_coordinates" not in item:
                        item["gps_coordinates"] = metadata.get("gps_coordinates")
                    if "gps_place" in metadata and "gps_place" not in item:
                        item["gps_place"] = metadata.get("gps_place")
                    if "edited_by" in metadata and "edited_by" not in item:
                        item["edited_by"] = metadata.get("edited_by")
                    if "edited_at" in metadata and "edited_at" not in item:
                        item["edited_at"] = metadata.get("edited_at")
                    for extra_key in (
                        "openai_metadata_fields",
                        "openai_metadata_model",
                        "openai_metadata_applied_at",
                        "openai_model_results",
                        "openai_place_contexts",
                        "openai_place_contexts_updated_at",
                        "openai_place_contexts_model",
                        "openai_place_model_results",
                    ):
                        if extra_key in metadata and not item.get(extra_key):
                            item[extra_key] = metadata.get(extra_key)
            except Exception:
                pass
        # Kompatibilitätsfelder für ältere JSON-Ansichten
        item.setdefault("primary_source", item.get("primaerquelle", ""))
        item.setdefault("secondary_source", item.get("sekundaerquelle", item.get("source", item.get("quelle", ""))))
        item.setdefault("source", item.get("secondary_source", item.get("quelle", "")))
        item.setdefault("original_location", item.get("standort_original", ""))
        item.setdefault("document_date", item.get("datum", ""))
        item.setdefault("event", item.get("ereignis", ""))
        item.setdefault("place", item.get("ort", ""))
        item.setdefault("gps_coordinates", item.get("gps", item.get("gps_koordinaten", "")))
        item.setdefault("gps_place", item.get("gps_ort", item.get("gps_location", "")))
        item.setdefault("description", item.get("beschreibung", ""))
        item.setdefault("status_note", item.get("status_note", item.get("rueckfrage_hinweis", "")))
        item.setdefault("note", item.get("bemerkung", ""))
        item.setdefault("keywords", item.get("stichwoerter", ""))
        item.setdefault("transcription_done", item.get("transcription_done", ""))
        item.setdefault("transcription_type", item.get("transcription_type", ""))
        item.setdefault("transcription_note", item.get("transcription_note", ""))
        return item

    def api_get_document_item(self, upload_id: str) -> dict | None:
        if not self.api_token or not upload_id:
            return None
        try:
            response = self.api.get_document(self.api_token, upload_id)
            return self.api_document_to_item(
                response.get("document", {}) or {},
                response.get("persons", []) or [],
                response.get("history", []) or [],
            )
        except ApiError as exc:
            messagebox.showwarning("API", f"Dokument konnte nicht aus MySQL geladen werden:\n{exc}")
            return None

    def item_payload_for_api(self, item: dict) -> dict:
        """Erzeugt aus einem lokalen/API-Item den Payload für PUT /api/documents/{upload_id}."""
        return {
            "current_filename": item.get("current_filename") or item.get("stored_filename") or item.get("original_filename") or "",
            "target_folder": item.get("target_folder") or "",
            "current_path": item.get("current_path") or "",
            "status": item.get("status") or "hochgeladen",
            "person_status": item.get("person_status") or ("identified" if item.get("persons") else "none"),
            "uploaded_by_user_id": item.get("uploaded_by_user_id") or item.get("user_id") or "",
            "uploaded_by_name": item.get("uploaded_by_name") or item.get("uploaded_by") or "",
            "odv_capture_mode": item.get("odv_capture_mode") or "odv_upload",
            "odv_captured_by_admin": bool(item.get("odv_captured_by_admin", False)),
            "archived_from_path": item.get("archived_from_path", ""),
            "ocr_pdf_path": item.get("ocr_pdf_path", ""),
            "ocr_pdf_filename": item.get("ocr_pdf_filename", ""),
            "ocr_source_filename": item.get("ocr_source_filename", ""),
            "ocr_created_at": item.get("ocr_created_at", ""),
            "openai_metadata_fields": item.get("openai_metadata_fields", []) or [],
            "openai_metadata_model": item.get("openai_metadata_model", ""),
            "openai_metadata_applied_at": item.get("openai_metadata_applied_at", ""),
            "openai_model_results": item.get("openai_model_results", {}) or {},
            "edited_by": item.get("edited_by", ""),
            "edited_at": item.get("edited_at", ""),
            "openai_place_contexts": item.get("openai_place_contexts", []) or [],
            "openai_place_contexts_updated_at": item.get("openai_place_contexts_updated_at", ""),
            "openai_place_contexts_model": item.get("openai_place_contexts_model", ""),
            "openai_place_model_results": item.get("openai_place_model_results", {}) or {},
            "status_note": item.get("status_note", ""),
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
                "gps_coordinates": item.get("gps_coordinates", ""),
                "gps_koordinaten": item.get("gps_coordinates", ""),
                "gps_place": item.get("gps_place", ""),
                "gps_ort": item.get("gps_place", ""),
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
                "ocr_pdf_path": item.get("ocr_pdf_path", ""),
                "ocr_pdf_filename": item.get("ocr_pdf_filename", ""),
                "ocr_source_filename": item.get("ocr_source_filename", ""),
                "ocr_created_at": item.get("ocr_created_at", ""),
                "openai_metadata_fields": item.get("openai_metadata_fields", []) or [],
                "openai_metadata_model": item.get("openai_metadata_model", ""),
                "openai_metadata_applied_at": item.get("openai_metadata_applied_at", ""),
                "openai_model_results": item.get("openai_model_results", {}) or {},
                "edited_by": item.get("edited_by", ""),
                "edited_at": item.get("edited_at", ""),
                "openai_place_contexts": item.get("openai_place_contexts", []) or [],
                "openai_place_contexts_updated_at": item.get("openai_place_contexts_updated_at", ""),
                "openai_place_contexts_model": item.get("openai_place_contexts_model", ""),
                "openai_place_model_results": item.get("openai_place_model_results", {}) or {},
                "status_note": item.get("status_note", ""),
            },
        }


    def item_create_payload_for_api(self, item: dict) -> dict:
        """Erzeugt aus einem lokalen Item den Payload für POST /api/documents.

        Wird auch für Dateien verwendet, die physisch bereits im Nextcloud-Ordner liegen
        und erst durch die Metadatenerfassung in ODV/MySQL übernommen werden.
        """
        payload = self.item_payload_for_api(item)
        payload.update({
            "upload_id": item.get("upload_id") or "",
            "original_filename": item.get("original_filename") or item.get("current_filename") or Path(str(item.get("current_path", ""))).name,
            "stored_filename": item.get("stored_filename") or item.get("current_filename") or Path(str(item.get("current_path", ""))).name,
            "current_filename": item.get("current_filename") or item.get("stored_filename") or item.get("original_filename") or Path(str(item.get("current_path", ""))).name,
            "target_folder": (item.get("target_folder") or (str(Path(str(item.get("current_path", ""))).parent) if item.get("current_path") else "")),
            "current_path": item.get("current_path") or "",
            "uploaded_at": str(item.get("uploaded_at", "")).replace("T", " ") or datetime.now().isoformat(timespec="seconds").replace("T", " "),
            "uploaded_by_user_id": item.get("uploaded_by_user_id") or item.get("user_id") or "",
            "uploaded_by_name": item.get("uploaded_by_name") or item.get("uploaded_by") or "",
            "import_uploaded_by_user_id": item.get("uploaded_by_user_id") or item.get("user_id") or "",
            "status": item.get("status") or "hochgeladen",
            "person_status": item.get("person_status") or ("identified" if item.get("persons") else "none"),
            "odv_capture_mode": item.get("odv_capture_mode") or "odv_upload",
            "odv_captured_by_admin": bool(item.get("odv_captured_by_admin", False)),
            "persons": item.get("persons", []) or [],
        })
        return payload

    def save_item_to_api(self, item: dict) -> tuple[bool, str]:
        upload_id = str(item.get("upload_id", "") or "")
        if not self.api_token or not upload_id:
            return False, "Kein API-Token oder keine Upload-ID vorhanden"
        try:
            try:
                self.api.lock_document(self.api_token, upload_id)
            except ApiError as lock_exc:
                return False, str(lock_exc)
            self.api.update_document(self.api_token, upload_id, self.item_payload_for_api(item))
            return True, "MySQL aktualisiert"
        except ApiError as exc:
            app_log_exception("Upload-Metadaten konnten nicht in MySQL gespeichert werden", exc, upload_id=upload_id)
            return False, str(exc)

    def save_item_json_if_present(self, item: dict) -> None:
        metadata_file = item.get("_metadata_file")
        if metadata_file:
            try:
                save_metadata_file(Path(str(metadata_file)), item)
            except Exception:
                pass

    def metadata_payload_for_api(self, metadata: UploadMetadata) -> dict:
        data = metadata.to_dict()
        return {
            "upload_id": data.get("upload_id"),
            "original_filename": data.get("original_filename"),
            "stored_filename": data.get("stored_filename"),
            "current_filename": data.get("current_filename"),
            "target_folder": data.get("target_folder"),
            "current_path": data.get("current_path"),
            "uploaded_at": str(data.get("uploaded_at", "")).replace("T", " "),
            "sha256": data.get("source_sha256", ""),
            "status": data.get("status", "hochgeladen"),
            "person_status": data.get("person_status", "none"),
            "metadata": {
                "document_type": data.get("document_type", ""),
                "primary_source": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "primaerquelle": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "secondary_source": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "sekundaerquelle": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "source": data.get("secondary_source", data.get("source", "")),
                "quelle": data.get("secondary_source", data.get("source", "")),
                "original_location": data.get("original_location", ""),
                "standort_original": data.get("original_location", ""),
                "document_date": data.get("document_date", ""),
                "datum": data.get("document_date", ""),
                "event": data.get("event", ""),
                "ereignis": data.get("event", ""),
                "place": data.get("place", ""),
                "ort": data.get("place", ""),
                "gps_coordinates": data.get("gps_coordinates", ""),
                "gps_koordinaten": data.get("gps_coordinates", ""),
                "gps_place": data.get("gps_place", ""),
                "gps_ort": data.get("gps_place", ""),
                "description": data.get("description", ""),
                "beschreibung": data.get("description", ""),
                "note": data.get("note", ""),
                "bemerkung": data.get("note", ""),
                "copyright_author": data.get("copyright_author", ""),
                "urheber": data.get("copyright_author", ""),
                "rights_holder": data.get("rights_holder", ""),
                "rechteinhaber": data.get("rights_holder", ""),
                "usage_permission": data.get("usage_permission", ""),
                "nutzungsfreigabe": data.get("usage_permission", ""),
                "license_note": data.get("license_note", ""),
                "lizenz": data.get("license_note", ""),
                "rights_note": data.get("rights_note", ""),
                "rechte": data.get("rights_note", ""),
                "archive_name": data.get("archive_name", ""),
                "archiv": data.get("archive_name", ""),
                "archive_signature": data.get("archive_signature", ""),
                "signatur": data.get("archive_signature", ""),
                "archive_accessed_at": data.get("archive_accessed_at", ""),
                "abruf_am": data.get("archive_accessed_at", ""),
                "keywords": data.get("keywords", ""),
                "stichwoerter": data.get("keywords", ""),
                "transcription_done": data.get("transcription_done", False),
                "transcription_type": data.get("transcription_type", ""),
                "transcription_note": data.get("transcription_note", ""),
                "ocr_pdf_path": data.get("ocr_pdf_path", ""),
                "ocr_pdf_filename": data.get("ocr_pdf_filename", ""),
                "ocr_source_filename": data.get("ocr_source_filename", ""),
                "ocr_created_at": data.get("ocr_created_at", ""),
                "openai_metadata_fields": data.get("openai_metadata_fields", []) or [],
                "openai_metadata_model": data.get("openai_metadata_model", ""),
                "openai_metadata_applied_at": data.get("openai_metadata_applied_at", ""),
            },
            "persons": data.get("persons", []),
        }

    def save_upload_to_api(self, metadata: UploadMetadata) -> tuple[bool, str]:
        if not self.api_token:
            return False, "Kein API-Token vorhanden"
        try:
            payload = self.metadata_payload_for_api(metadata)
            self.api.create_document(self.api_token, payload)
            persons = payload.get("persons") or []
            if persons:
                self.api.update_persons(self.api_token, metadata.upload_id, persons)
            return True, "Metadaten wurden in MySQL gespeichert"
        except ApiError as exc:
            app_log_exception(
                "Upload-Metadaten konnten nicht in MySQL gespeichert werden",
                exc,
                upload_id=metadata.upload_id,
            )
            return False, str(exc)

    def _rollback_upload_artifacts(self, target_file: Path | None, json_file: Path | None, ocr_target: Path | None) -> None:
        """Entfernt lokale Upload-Artefakte bei fehlgeschlagenem Upload."""
        for candidate in (target_file, json_file, ocr_target):
            if not candidate:
                continue
            try:
                if candidate.exists() and candidate.is_file():
                    candidate.unlink()
            except Exception as exc:
                app_log_exception("Upload-Artefakt konnte nicht bereinigt werden", exc, path=str(candidate))

    def compute_source_sha256(self, source: Path) -> str:
        try:
            return file_sha256(source)
        except Exception as exc:
            app_log_exception("SHA-256 konnte nicht berechnet werden", exc, path=str(source))
            return ""

    def find_duplicates_by_file_sha256(self, sha256: str) -> list[dict]:
        normalized_sha256 = sha256.strip().lower()
        if not self.api_token or not normalized_sha256:
            return []
        try:
            response = self.api.find_documents_by_sha256(self.api_token, normalized_sha256)
            documents = response.get("documents")
            if isinstance(documents, list) and documents:
                return documents
        except ApiError as exc:
            app_log_exception("Duplikatprüfung via SHA-256 fehlgeschlagen", exc, sha256=normalized_sha256)

        # Fallback: lokale Fallbacks via Dokumentenliste, falls der neue Endpunkt
        # keine Treffer liefert oder keine Treffer in der erwarteten JSON-Struktur findet.
        return [doc for doc in self._find_duplicates_in_document_list(normalized_sha256)]

    @staticmethod
    def _normalize_sha256(value: object) -> str:
        value_text = str(value or "").strip().lower()
        if len(value_text) != 64 or any(ch not in "0123456789abcdef" for ch in value_text):
            return ""
        return value_text

    @staticmethod
    def _extract_sha256_from_document_payload(document: dict) -> str:
        if not isinstance(document, dict):
            return ""

        direct = UploadManagerMixin._normalize_sha256(document.get("sha256", ""))
        if direct:
            return direct

        nested = UploadManagerMixin._normalize_sha256(document.get("source_sha256", ""))
        if nested:
            return nested

        metadata = document.get("metadata")
        if isinstance(metadata, dict):
            nested = UploadManagerMixin._normalize_sha256(metadata.get("sha256", ""))
            if nested:
                return nested

        raw_json_metadata = document.get("json_metadata")
        if isinstance(raw_json_metadata, str):
            try:
                payload = json.loads(raw_json_metadata)
                if isinstance(payload, dict):
                    nested = UploadManagerMixin._normalize_sha256(payload.get("sha256", ""))
                    if nested:
                        return nested
                    nested = UploadManagerMixin._normalize_sha256(payload.get("source_sha256", ""))
                    if nested:
                        return nested
                    nested_data = payload.get("metadata")
                    if isinstance(nested_data, dict):
                        nested = UploadManagerMixin._normalize_sha256(nested_data.get("sha256", ""))
                        if nested:
                            return nested
            except Exception:
                return ""
        return ""

    def _find_duplicates_in_document_list(self, normalized_sha256: str) -> list[dict]:
        try:
            visible_documents: list[dict] = []
            responses = [
                self.api.list_documents(self.api_token, status=None, only_own=False),
                self.api.list_documents(self.api_token, status="archiviert", only_own=False),
            ]
            for response in responses:
                documents = response.get("documents")
                if isinstance(documents, list):
                    visible_documents.extend(documents)

            unique_documents: dict[str, dict] = {}
            for document in visible_documents:
                upload_id = str(document.get("upload_id") or "")
                if upload_id:
                    unique_documents.setdefault(upload_id, document)
                else:
                    unique_documents[str(id(document))] = document

            return [
                doc for doc in unique_documents.values()
                if self._extract_sha256_from_document_payload(doc) == normalized_sha256
            ]
        except ApiError as exc:
            app_log_exception("Fallback-Duplikatprüfung via Dokumentenliste fehlgeschlagen", exc, sha256=normalized_sha256)
            return []

    def confirm_upload_for_duplicate(self, source: Path, sha256: str) -> bool:
        documents = self.find_duplicates_by_file_sha256(sha256)
        if not documents:
            return True

        dialog = tk.Toplevel(self)
        dialog.title("Duplikatprüfung")
        dialog.geometry("860x420")
        dialog.minsize(740, 320)
        dialog.transient(self)
        dialog.grab_set()
        try:
            dialog.focus_force()
        except Exception:
            pass
        main = ttk.Frame(dialog, padding=10)
        main.pack(fill="both", expand=True)
        ttk.Label(
            main,
            text=(
                f"{len(documents)} Treffer für denselben SHA-256-Wert gefunden.\n"
                "Die Datei wurde wahrscheinlich bereits über ODV hochgeladen."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        cols = ("typ", "datei", "hochgeladen", "benutzer", "pfad")
        list_frame = ttk.Frame(main)
        list_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse", height=10)
        tree.heading("typ", text="Typ")
        tree.heading("datei", text="Datei")
        tree.heading("hochgeladen", text="Hochgeladen")
        tree.heading("benutzer", text="Benutzer")
        tree.heading("pfad", text="Pfad / Ort")
        tree.column("typ", width=90, anchor="w", stretch=False)
        tree.column("datei", width=220, anchor="w")
        tree.column("hochgeladen", width=140, anchor="w")
        tree.column("benutzer", width=120, anchor="w")
        tree.column("pfad", width=250, anchor="w")
        vsb = ttk.Scrollbar(main, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True, in_=list_frame)
        vsb.pack(side="right", fill="y", in_=list_frame)

        row_paths: dict[str, Path | None] = {}

        source_uploaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_row = tree.insert("", "end", values=(
            "Ausgewählt",
            source.name,
            source_uploaded,
            self.display_name_var.get().strip() or "",
            str(source),
        ))
        row_paths[source_row] = source

        for doc in documents:
            filename = doc.get("original_filename") or doc.get("current_filename") or "unbekannte Datei"
            uploaded_at = doc.get("uploaded_at", "") or "Datum fehlt"
            uploaded_by = doc.get("uploaded_by_name", "") or ""
            path_text = str(doc.get("current_path") or doc.get("target_folder") or "").strip()
            tree.insert("", "end", values=(
                "ODV",
                filename,
                uploaded_at,
                uploaded_by,
                path_text,
            ))
            row_paths[str(tree.get_children()[-1])] = Path(path_text) if path_text else None

        action = {"value": False}

        button_bar = ttk.Frame(main)
        button_bar.pack(fill="x", pady=(8, 0))

        def selected_path() -> Path | None:
            selected = tree.selection()
            if not selected:
                return None
            return row_paths.get(selected[0], None)

        def can_open_selected() -> bool:
            item_path = selected_path()
            return bool(item_path and item_path.exists() and item_path.is_file())

        def update_open_state() -> None:
            open_btn.configure(state=("normal" if can_open_selected() else "disabled"))

        def on_open_selected() -> None:
            item_path = selected_path()
            if not item_path:
                messagebox.showwarning("Datei anzeigen", "Bitte zuerst einen Eintrag wählen.")
                return
            if not item_path.exists() or not item_path.is_file():
                messagebox.showwarning("Datei anzeigen", f"Die ausgewählte Datei ist lokal nicht vorhanden:\n{item_path}")
                return
            self.open_file_with_default_app(item_path)

        def on_accept() -> None:
            action["value"] = True
            dialog.destroy()

        def on_cancel() -> None:
            action["value"] = False
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        open_btn = ttk.Button(button_bar, text="Ausgewählte Datei öffnen", command=on_open_selected)
        open_btn.pack(side="left")

        ttk.Button(button_bar, text="Trotzdem hochladen", command=on_accept).pack(side="right", padx=(0, 6))
        ttk.Button(button_bar, text="Abbrechen", command=on_cancel).pack(side="right")

        def on_double_click(_event: tk.Event) -> None:
            on_open_selected()

        tree.bind("<Double-1>", on_double_click)
        tree.bind("<<TreeviewSelect>>", lambda _event: update_open_state())
        try:
            first_iid = tree.get_children()[0]
            tree.selection_set(first_iid)
            update_open_state()
        except Exception:
            pass
        self.wait_window(dialog)
        return action["value"]

    def _suggest_unique_stored_filename(self, target_folder: Path, stored_filename: str) -> str:
        candidate = Path(stored_filename)
        stem = candidate.stem
        suffix = candidate.suffix
        base_stem = stem
        match = re.match(r"^(.*)_v(\d+)$", stem)
        if match:
            base_stem = match.group(1)

        attempt = 1
        current = stored_filename
        while (target_folder / current).exists():
            current = f"{base_stem}_v{attempt}{suffix}"
            attempt += 1
        return current

    def build_upload_metadata_for_source(self, source: Path, target_folder: Path, display_name: str, source_sha256: str = "", stored_filename: str | None = None) -> UploadMetadata:
        upload_id = make_upload_id()
        requested_filename = str(self.meta_vars.get("current_filename", tk.StringVar()).get()).strip()
        if self.selected_folder is not None:
            requested_filename = source.name
        planned_filename = self.planned_upload_filename(source, requested_filename)
        stored_filename = stored_filename or planned_filename
        current_path = str(target_folder / stored_filename)
        document_type = self.meta_vars["document_type"].get().strip()
        if document_type in {"", "Mehrere Dateien"}:
            document_type = detect_document_type(source)
        self.remember_document_type(document_type)
        self.remember_archive_collection(self.meta_vars["archive_name"].get().strip())
        ocr_source = self.current_upload_ocr_pdf_path() if self.selected_file == source else None
        ocr_planned_path = self.planned_upload_ocr_pdf_path(source, target_folder, stored_filename) if ocr_source else ""
        openai_fields = list(dict.fromkeys(str(field) for field in (self.openai_metadata_applied_fields or []) if str(field).strip()))
        return UploadMetadata(
            upload_id=upload_id,
            original_filename=source.name,
            stored_filename=stored_filename,
            current_filename=stored_filename,
            current_path=current_path,
            status="hochgeladen",
            uploaded_by=display_name,
            uploaded_at=datetime.now().isoformat(timespec="seconds"),
            target_folder=str(target_folder),
            primary_source=self.meta_vars.get("primary_source", tk.StringVar()).get().strip(),
            secondary_source=self.meta_vars.get("secondary_source", tk.StringVar()).get().strip(),
            source=self.meta_vars.get("secondary_source", tk.StringVar()).get().strip(),
            original_location=self.meta_vars["original_location"].get().strip(),
            document_date=self.meta_vars["document_date"].get().strip(),
            event=self.meta_vars["event"].get().strip(),
            place=self.meta_vars["place"].get().strip(),
            gps_coordinates=self.meta_vars.get("gps_coordinates", tk.StringVar()).get().strip(),
            gps_place=self.meta_vars.get("gps_place", tk.StringVar()).get().strip(),
            document_type=document_type,
            rights_note=self.meta_vars["rights_note"].get().strip(),
            copyright_author=self.meta_vars["copyright_author"].get().strip(),
            rights_holder=self.meta_vars["rights_holder"].get().strip(),
            usage_permission=self.meta_vars["usage_permission"].get().strip(),
            license_note=self.meta_vars["license_note"].get().strip(),
            archive_name=self.meta_vars["archive_name"].get().strip(),
            archive_signature=self.meta_vars["archive_signature"].get().strip(),
            archive_accessed_at=self.meta_vars["archive_accessed_at"].get().strip(),
            keywords=str(self.meta_vars.get("keywords", tk.StringVar()).get()).strip(),
            transcription_done=bool(self.meta_vars.get("transcription_done", tk.BooleanVar(value=False)).get()),
            transcription_type=str(self.meta_vars.get("transcription_type", tk.StringVar()).get()).strip(),
            transcription_note=self.meta_vars.get("transcription_note", tk.StringVar()).get().strip(),
            ocr_pdf_path=ocr_planned_path,
            ocr_pdf_filename=Path(ocr_planned_path).name if ocr_planned_path else "",
            ocr_source_filename=ocr_source.name if ocr_source else "",
            ocr_created_at=datetime.now().isoformat(timespec="seconds") if ocr_source else "",
            source_sha256=source_sha256,
            openai_metadata_fields=openai_fields,
            openai_metadata_model=str(self.config_data.get("openai_model", "") or "") if openai_fields else "",
            openai_metadata_applied_at=datetime.now().isoformat(timespec="seconds") if openai_fields else "",
            description=self.normalize_description_text(self.description_text.get("1.0", "end").strip()),
            note=self.note_text.get("1.0", "end").strip(),
            person_status=self.person_status_var.get() if self.selected_file else "none",
            persons=self.persons if self.selected_file else [],
        )


    def planned_upload_ocr_pdf_path(self, source: Path, target_folder: Path, stored_filename: str) -> str:
        if self.selected_file != source:
            return ""
        ocr_source = self.current_upload_ocr_pdf_path()
        if not ocr_source:
            return ""
        target = target_folder / f"{Path(stored_filename).stem}_ocr.pdf"
        return str(unique_path_with_counter(target))

    def upload_single_source_file(self, source: Path, target_folder: Path, display_name: str) -> tuple[bool, str]:
        source_sha256 = self.compute_source_sha256(source)
        if source_sha256 and not self.confirm_upload_for_duplicate(source, source_sha256):
            return False, "Upload abgebrochen: Es wurde bereits eine identische Datei in ODV gefunden."

        requested_filename = str(self.meta_vars.get("current_filename", tk.StringVar()).get()).strip()
        if self.selected_folder is not None and not requested_filename:
            requested_filename = source.name
        suggested_name = self.planned_upload_filename(source, requested_filename)
        unique_stored_filename = self._suggest_unique_stored_filename(target_folder, suggested_name)

        metadata = self.build_upload_metadata_for_source(
            source,
            target_folder,
            display_name,
            source_sha256=source_sha256,
            stored_filename=unique_stored_filename,
        )
        metadata_folder = self.metadata_folder_path()

        target_file: Path | None = None
        json_file: Path | None = None
        ocr_target: Path | None = None

        try:
            target_file, json_file = copy_with_metadata(source, target_folder, metadata, metadata_folder)
            with json_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)

            if unique_stored_filename != suggested_name:
                append_metadata_history(
                    data,
                    display_name,
                    "Dateiname kollidiert",
                    f"{suggested_name} → {unique_stored_filename}",
                )

            ocr_source = self.current_upload_ocr_pdf_path() if self.selected_file == source else None
            ocr_target_text = str(data.get("ocr_pdf_path") or "")
            if ocr_source and ocr_target_text:
                ocr_target = Path(ocr_target_text)
                try:
                    ocr_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ocr_source, ocr_target)
                    data["ocr_pdf_path"] = str(ocr_target)
                    data["ocr_pdf_filename"] = ocr_target.name
                    data["ocr_source_filename"] = ocr_source.name
                    append_metadata_history(data, display_name, "OCR-PDF verknüpft", f"{ocr_source.name} → {ocr_target}")
                except Exception as exc:
                    self._rollback_upload_artifacts(target_file, json_file, ocr_target)
                    app_log_exception("OCR-PDF konnte nicht zum Upload kopiert werden", exc, source=str(ocr_source), target=ocr_target_text)
                    raise RuntimeError(f"Original wurde kopiert, aber OCR-PDF konnte nicht verknüpft werden:\n{exc}") from exc

            save_metadata_file(json_file, data)
            api_ok, api_message = self.save_upload_to_api(metadata)
            if not api_ok:
                append_metadata_history(data, display_name, "MySQL nicht gespeichert", api_message)
                save_metadata_file(json_file, data)
                self._rollback_upload_artifacts(target_file, json_file, ocr_target)
                raise RuntimeError(api_message or "Die Datei wurde lokal kopiert, konnte aber nicht in MySQL/API gespeichert werden.")

            append_metadata_history(data, display_name, "Datei hochgeladen", f"{source.name} → {target_file}")
            append_metadata_history(data, display_name, "MySQL gespeichert", "Metadaten wurden über die API in MySQL gespeichert")
            save_metadata_file(json_file, data)

            add_history(HistoryEntry.now(display_name, "Datei hochgeladen", f"{source.name} → {target_file} | Metadaten: {json_file}", metadata.upload_id))
            add_history(HistoryEntry.now(display_name, "MySQL gespeichert", api_message, metadata.upload_id))
            if metadata.persons:
                add_history(HistoryEntry.now(display_name, "Personen markiert", f"{len(metadata.persons)} Personen in {metadata.stored_filename}", metadata.upload_id))

            return True, str(target_file)
        except Exception:
            self._rollback_upload_artifacts(target_file, json_file, ocr_target)
            raise

    def submit_upload(self) -> None:
        base = self.nextcloud_base_path(show_message=True)
        if base is None:
            return
        selected_target = self.target_folder_var.get().strip()
        target_folder = self.target_folder_map.get(selected_target)
        if target_folder is None and selected_target:
            candidate = Path(selected_target).expanduser()
            if not candidate.is_absolute():
                candidate = base / selected_target
            target_folder = candidate
        if target_folder is None or not target_folder.exists() or not target_folder.is_dir() or not self.is_path_under_base(target_folder, base):
            messagebox.showerror("Fehler", "Bitte einen gültigen Zielordner innerhalb des Nextcloud-Stammverzeichnisses auswählen.")
            return

        display_name = self.display_name_var.get().strip() or "Ortschronist/in"
        self.ensure_standard_metadata_folder()
        save_config(self.config_data)

        if self.selected_folder:
            source_folder = self.selected_folder
            if not source_folder.exists() or not source_folder.is_dir():
                messagebox.showerror("Fehler", "Bitte einen gültigen Ordner auswählen.")
                return
            files = [p for p in sorted(source_folder.rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and not p.name.startswith(".")]
            if not files:
                messagebox.showinfo("Ordnerupload", "Im ausgewählten Ordner wurden keine Dateien gefunden.")
                return
            if not messagebox.askyesno("Ordner hochladen", f"{len(files)} Datei(en) mit den aktuell erfassten Metadaten hochladen?\n\nOrdner:\n{source_folder}"):
                return
            ok_count = 0
            fail_count = 0
            skipped_count = 0
            for source in files:
                try:
                    rel_parent = source.relative_to(source_folder).parent
                    file_target_folder = target_folder / rel_parent if str(rel_parent) != "." else target_folder
                    file_target_folder.mkdir(parents=True, exist_ok=True)
                    api_ok, _ = self.upload_single_source_file(source, file_target_folder, display_name)
                    if not api_ok:
                        skipped_count += 1
                        continue
                    ok_count += 1
                except Exception as exc:
                    fail_count += 1
                    app_log_exception("Datei im Ordnerupload konnte nicht hochgeladen werden", exc, path=str(source))
            self.refresh_history()
            self.refresh_admin_uploads(show_message=False)
            skip_info = f"\nÜbersprungen: {skipped_count}" if skipped_count else ""
            messagebox.showinfo("Ordnerupload", f"Hochgeladen: {ok_count}\nFehler: {fail_count}{skip_info}")
            self.clear_upload_form(keep_target_folder=True)
            return

        source = self.selected_file or Path(self.file_var.get().strip())
        if not source.exists() or not source.is_file():
            messagebox.showerror("Fehler", "Bitte eine gültige Datei oder einen Ordner auswählen.")
            return
        try:
            api_ok, target_file = self.upload_single_source_file(source, target_folder, display_name)
        except Exception as exc:
            app_log_exception("Datei konnte beim Hochladen nicht kopiert werden", exc, path=str(source), target_folder=str(target_folder))
            messagebox.showerror("Fehler beim Kopieren", str(exc))
            return
        if not api_ok:
            messagebox.showinfo("Hinweis", target_file)
            return
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        messagebox.showinfo("Erfolg", f"Datei wurde hochgeladen:\n{target_file}")
        self.clear_upload_form(keep_target_folder=True)

