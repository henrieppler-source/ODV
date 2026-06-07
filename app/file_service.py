from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from .models import UploadMetadata

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
WORD_EXTENSIONS = {".doc", ".docx", ".dot", ".dotx", ".rtf", ".odt"}
EXCEL_EXTENSIONS = {".xls", ".xlsx", ".ods", ".csv"}
POWERPOINT_EXTENSIONS = {".ppt", ".pptx", ".odp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v"}
TEXT_EXTENSIONS = {".txt", ".md"}
ROEMHILD_PLACE_NAMES = (
    "Bedheim",
    "Eicha",
    "Gleicherwiesen",
    "Gleichamberg",
    "Hindfeld",
    "Milz",
    "Mendhausen",
    "Roth",
    "Haina",
    "Römhild",
    "Sülzdorf",
    "Westenfeld",
    "Zeilfeld",
    "Mönchshof",
    "Simmershausen",
)
_ROEMHILD_PLACE_TOKENS = None


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def detect_document_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return "PDF-Dokument"
    if suffix in WORD_EXTENSIONS:
        return "Word-/Textdokument"
    if suffix in IMAGE_EXTENSIONS:
        return "Bild"
    if suffix in EXCEL_EXTENSIONS:
        return "Tabellen-Datei"
    if suffix in POWERPOINT_EXTENSIONS:
        return "Präsentation"
    if suffix in AUDIO_EXTENSIONS:
        return "Audio-Datei"
    if suffix in VIDEO_EXTENSIONS:
        return "Video-Datei"
    if suffix in TEXT_EXTENSIONS:
        return "Textdatei"
    return "Sonstige Datei"


def is_writable_folder(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    test_file = path / f".ortschronik_write_test_{uuid.uuid4().hex}.tmp"
    try:
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        return True
    except OSError:
        try:
            if test_file.exists():
                test_file.unlink()
        except OSError:
            pass
        return False


def find_writable_folders(base_folder: Path, max_depth: int = 3) -> list[Path]:
    if not base_folder.exists() or not base_folder.is_dir():
        return []

    folders: list[Path] = []
    base_depth = len(base_folder.parts)
    for item in base_folder.rglob("*"):
        if not item.is_dir():
            continue
        ignored = {"_internal", "__pycache__", ".venv", "venv", "build", "dist", "PIL", "pypdf", "tk_data", "tcl", "tcl8", "ODV_UPDATE", "odv_update"}
        if any(part.startswith(".ortschronik_") or part in ignored or part.upper() == "ODV_UPDATE" for part in item.parts):
            continue
        depth = len(item.parts) - base_depth
        if depth > max_depth:
            continue
        if is_writable_folder(item):
            folders.append(item)
    if is_writable_folder(base_folder):
        folders.insert(0, base_folder)
    return folders


def safe_filename(name: str) -> str:
    allowed = []
    for ch in name:
        if ch.isalnum() or ch in {".", "-", "_"}:
            allowed.append(ch)
        elif ch.isspace():
            allowed.append("_")
    result = "".join(allowed).strip("._")
    return result or "datei"


def normalize_filename_component(value: str) -> str:
    """Normiert Text für Dateinamen: kleinschreibung, Umlaute, Leerzeichen."""
    text = (value or "").strip().lower()
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "Ä": "ae", "Ö": "oe", "Ü": "ue",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[.]+", "_", text)
    text = re.sub(r"[^a-z0-9_#-]+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("._-")
    return text or "datei"


def split_place_values(value: str) -> list[str]:
    """Teilt ein Ortsfeld wie \"A, B; C\" in einzelne Ortsnamen auf."""
    parts: list[str] = []
    for raw in re.split(r"[,;/\n]+", str(value or "")):
        text = raw.strip(" .;,-")
        if text:
            parts.append(text)
    return parts


def _normalize_place_token_for_grouping(value: str) -> str:
    token = normalize_filename_component(value)
    token = re.sub(r"^(?:stadt|gemeinde)_", "", token)
    return token


def _roemhild_place_tokens() -> set[str]:
    """Liefert normalisierte Ortsnamen, die zur Römhild-Gemeinden-Liste gehören."""
    global _ROEMHILD_PLACE_TOKENS
    if _ROEMHILD_PLACE_TOKENS is None:
        _ROEMHILD_PLACE_TOKENS = {normalize_filename_component(name) for name in ROEMHILD_PLACE_NAMES}
    return _ROEMHILD_PLACE_TOKENS


def _build_filename_cleanup_tokens(place_part: str, place_candidates: list[str] | None = None) -> set[str]:
    place_part = normalize_filename_component(place_part)
    tokens = {normalize_filename_component(t) for t in (place_part or "").split("_") if t}
    cleaned_candidates = {token for token in (place_candidates or []) if token}
    if place_part in {"andere_orte", "other_places"}:
        tokens.update({"andere", "orte"})
        tokens.update(cleaned_candidates)
        return tokens

    if place_part in {"gemeinden_roemhild", "roemhild"}:
        tokens.update({"gemeinden", "roemhild"})
        # Remove old "andere_orte"-Artefakte, falls vorhandene Dateinamen aus älteren Logiken übernommen wurden.
        tokens.update({"andere", "orte"})
        roemhild_tokens = _roemhild_place_tokens()
        tokens.update(cleaned_candidates.intersection(roemhild_tokens))
        return tokens

    tokens.update(cleaned_candidates)
    return tokens


def _extract_filename_place_part(places_value: str) -> str:
    places = split_place_values(places_value)
    if not places:
        return ""

    normalized = [_normalize_place_token_for_grouping(place) for place in places if place]
    if len(normalized) <= 1:
        return normalized[0] if normalized else ""

    roemhild_tokens = _roemhild_place_tokens()
    all_known_roemhild = all(place in roemhild_tokens for place in normalized)
    has_roemhild_place = any(place in roemhild_tokens for place in normalized)

    if len(normalized) > 1:
        if all_known_roemhild and has_roemhild_place:
            return "Gemeinden_Römhild"
        return "andere_Orte"

    return normalized[0]


def normalize_date_for_filename(value: str) -> str:
    """Erzeugt einen Dateinamen-tauglichen Datums-/Zeitraum-Anteil.

    Unterstützt u.a. YYYY, DD.MM.YYYY, YYYY-MM-DD, YYYY-MM, YYYY-YYYY.
    Nicht eindeutig parsebare Angaben werden nur technisch normiert.
    """
    text = (value or "").strip()
    if not text:
        return ""
    # ISO mit Uhrzeit: 2026-05-16T11:32 oder 2026-05-16 11:32
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    # Deutsches Datum: 16.05.2026 oder 16.5.2026
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", text)
    if m:
        return f"{m.group(3)}{int(m.group(2)):02d}{int(m.group(1)):02d}"
    # Jahr oder Zeitraum: 1978, 1978-1980, 1978/79
    # Diese Prüfung steht vor YYYY-MM, weil 1978-80 ein Zeitraum und kein Monat ist.
    m = re.match(r"^(\d{4})(\s*[-/–]\s*(\d{2,4}))?$", text)
    if m:
        if m.group(3):
            end = m.group(3)
            # YYYY-MM mit echtem Monat soll Monat/Jahr bleiben; 1978-80 ist dagegen ein Zeitraum.
            if len(end) == 2 and 1 <= int(end) <= 12:
                pass
            else:
                if len(end) == 2:
                    end = m.group(1)[:2] + end
                return f"{m.group(1)}-{end}"
        else:
            return m.group(1)
    # Monat/Jahr: 05.2026 oder 2026-05
    m = re.match(r"^(\d{1,2})\.(\d{4})$", text)
    if m:
        return f"{m.group(2)}{int(m.group(1)):02d}"
    m = re.match(r"^(\d{4})-(\d{2})$", text)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}{m.group(2)}"
    # Jahr oder Zeitraum: 1978, 1978-1980, 1978/79
    m = re.match(r"^(\d{4})(\s*[-/–]\s*(\d{2,4}))?$", text)
    if m:
        if m.group(3):
            end = m.group(3)
            if len(end) == 2:
                end = m.group(1)[:2] + end
            return f"{m.group(1)}-{end}"
        return m.group(1)
    return normalize_filename_component(text)


def strip_existing_date_prefix(stem: str) -> str:
    """Entfernt häufige Upload-/Datums-Präfixe aus einem Dateinamenstamm."""
    text = stem or ""
    patterns = [
        r"^\d{8}_\d{6}_+",
        r"^\d{8}[-_]\d{4,6}[-_][0-9a-f]{4,12}_+",
        r"^\d{8}_+",
        r"^\d{4}(?:[-_]\d{2})?(?:[-_]\d{2})?_+",
        r"^\d{4}(?:[-/–]\d{2,4})?_+",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text or stem


def make_normalized_archive_filename(metadata: dict, requested_filename: str) -> str:
    """Normiert den endgültigen Dateinamen für die Admin-Bearbeitung.

    Datum/Zeitraum aus den Metadaten hat Vorrang. Fehlt es, wird das Upload-Datum verwendet.
    Der Datumsanteil wird als Präfix gesetzt. Die Erweiterung wird kleingeschrieben.
    Punkte im Stammnamen werden zu ``_``; die echte Dateiendung bleibt aber als
    Endung erhalten. Altdaten wie ``datei_jpg`` werden nicht mehr zu
    ``datei_jpg.jpg`` verdoppelt, sondern zu ``datei.jpg`` bereinigt.
    """
    requested = (requested_filename or metadata.get("current_filename") or metadata.get("stored_filename") or metadata.get("original_filename") or "datei").strip()

    suffix = Path(requested).suffix.lower()
    if not suffix:
        for key in ("current_filename", "stored_filename", "original_filename"):
            suffix = Path(str(metadata.get(key) or "")).suffix.lower()
            if suffix:
                break

    stem = Path(requested).stem if Path(requested).stem else requested

    # Wenn keine echte Endung vorhanden ist, aber der Name mit _jpg/_pdf/etc. endet,
    # daraus wieder eine echte Endung machen.
    known_exts = sorted(
        IMAGE_EXTENSIONS | PDF_EXTENSIONS | WORD_EXTENSIONS | EXCEL_EXTENSIONS | POWERPOINT_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS | TEXT_EXTENSIONS,
        key=len,
        reverse=True,
    )
    lower_stem = stem.lower()
    for ext in known_exts:
        token = ext.lstrip(".")
        for sep in ("_", "-", " "):
            tail = sep + token
            if lower_stem.endswith(tail):
                if not suffix:
                    suffix = ext
                if suffix == ext:
                    stem = stem[: -len(tail)]
                break
        else:
            continue
        break

    try:
        from .normalization_rules import (
            DEFAULT_FILENAME_TEMPLATE,
            configured_filename_template,
            filename_template_is_safe,
            matching_filename_rule,
            render_filename_template,
        )

        rule = matching_filename_rule(metadata)
        template = str(rule.get("template") or "") if rule else configured_filename_template()
        if template and template != DEFAULT_FILENAME_TEMPLATE and filename_template_is_safe(template):
            return render_filename_template(template, metadata, requested) + suffix
    except Exception:
        pass

    stem = strip_existing_date_prefix(stem)
    stem = normalize_filename_component(stem)
    date_text = metadata.get("document_date") or metadata.get("date") or ""
    date_part = normalize_date_for_filename(str(date_text)) or "0000"
    place_input = str(metadata.get("place") or metadata.get("ort") or "")
    place_candidates = [
        _normalize_place_token_for_grouping(part)
        for part in split_place_values(place_input)
        if part
    ]
    place_part = _extract_filename_place_part(place_input)
    place_part = normalize_filename_component(place_part)

    # v79: Dateiname ist immer DATUM_ORT_rest.ext.
    # Datum fehlt -> 0000. Ort kommt immer aus den Metadaten in das Präfix.
    # Kommt der Ort im Restdateinamen erneut vor, wird er dort entfernt.
    stem_tokens = [tok for tok in stem.split("_") if tok]
    cleanup_tokens = _build_filename_cleanup_tokens(place_part, place_candidates)
    if place_part and place_part != "datei":
        stem_tokens = [tok for tok in stem_tokens if tok not in cleanup_tokens]
    stem = "_".join(stem_tokens) or "datei"

    parts = []
    parts.append(date_part or "0000")
    if place_part and place_part != "datei":
        parts.append(place_part)
    parts.append(stem)
    return "_".join(part for part in parts if part) + suffix


def unique_path_with_counter(path: Path) -> Path:
    """Liefert einen freien Pfad. Bei Kollisionen: name_#1.ext, name_#2.ext ..."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_#{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def make_upload_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def copy_with_metadata(
    source_file: Path,
    target_folder: Path,
    metadata: UploadMetadata,
    metadata_folder: Path | None = None,
) -> tuple[Path, Path]:
    target_folder.mkdir(parents=True, exist_ok=True)
    target_file = target_folder / metadata.stored_filename
    if target_file.exists():
        raise FileExistsError(f"Zieldatei existiert bereits: {target_file}")

    shutil.copy2(source_file, target_file)

    if metadata_folder is None:
        metadata_folder = target_folder / ".ortschronik_metadaten"
    metadata_folder.mkdir(parents=True, exist_ok=True)

    json_file = metadata_folder / f"{metadata.upload_id}.metadata.json"
    with json_file.open("w", encoding="utf-8") as fh:
        json.dump(metadata.to_dict(), fh, ensure_ascii=False, indent=2)

    return target_file, json_file


def load_metadata_files(metadata_folder: Path) -> list[dict]:
    """Liest alle zentralen JSON-Metadatendateien ein."""
    if not metadata_folder.exists() or not metadata_folder.is_dir():
        return []
    items: list[dict] = []
    for json_file in sorted(metadata_folder.glob("*.metadata.json")):
        try:
            with json_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            data["_metadata_file"] = str(json_file)
            items.append(data)
        except Exception:
            # Defekte JSON-Dateien im MVP überspringen; später im Adminbereich gesondert melden.
            continue
    return items


def save_metadata_file(metadata_file: Path, data: dict) -> None:
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    with metadata_file.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def append_metadata_history(data: dict, user_display_name: str, action: str, details: str, old_value: str | None = None, new_value: str | None = None) -> None:
    history = data.setdefault("history", [])
    history.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "user_display_name": user_display_name,
        "action": action,
        "details": details,
        "old_value": old_value,
        "new_value": new_value,
    })


def update_metadata_after_move(metadata_file: Path, user_display_name: str, new_file: Path, action: str, details: str, old_value: str | None = None, new_value: str | None = None) -> dict:
    with metadata_file.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    data["current_filename"] = new_file.name
    data["current_path"] = str(new_file)
    data["status"] = "archiviert" if action == "Datei verschoben" else data.get("status", "hochgeladen")
    append_metadata_history(data, user_display_name, action, details, old_value=old_value, new_value=new_value)
    save_metadata_file(metadata_file, data)
    return data
