from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class PersonMark:
    number: int
    x: float
    y: float
    display_name: str = ""
    certainty: str = "unbekannt"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UploadMetadata:
    upload_id: str
    original_filename: str
    stored_filename: str
    uploaded_by: str
    uploaded_at: str
    target_folder: str
    current_path: str = ""
    current_filename: str = ""
    status: str = "hochgeladen"
    primary_source: str = ""
    secondary_source: str = ""
    source: str = ""
    original_location: str = ""
    document_date: str = ""
    event: str = ""
    place: str = ""
    gps_coordinates: str = ""
    gps_place: str = ""
    description: str = ""
    document_type: str = ""
    rights_note: str = ""
    copyright_author: str = ""
    rights_holder: str = ""
    usage_permission: str = ""
    license_note: str = ""
    archive_name: str = ""
    archive_signature: str = ""
    archive_accessed_at: str = ""
    keywords: str = ""
    transcription_done: bool = False
    transcription_type: str = ""
    transcription_note: str = ""
    ocr_pdf_path: str = ""
    ocr_pdf_filename: str = ""
    ocr_source_filename: str = ""
    ocr_created_at: str = ""
    openai_metadata_fields: list[str] = field(default_factory=list)
    openai_metadata_model: str = ""
    openai_metadata_applied_at: str = ""
    note: str = ""
    person_status: str = "none"
    persons: list[PersonMark] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["persons"] = [p.to_dict() for p in self.persons]
        return data


@dataclass
class HistoryEntry:
    timestamp: str
    user_display_name: str
    action: str
    details: str
    upload_id: str | None = None

    @classmethod
    def now(cls, user_display_name: str, action: str, details: str, upload_id: str | None = None) -> "HistoryEntry":
        return cls(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            user_display_name=user_display_name,
            action=action,
            details=details,
            upload_id=upload_id,
        )
