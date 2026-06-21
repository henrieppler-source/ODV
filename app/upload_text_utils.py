from __future__ import annotations

from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

from .app_logging import app_log_exception
from .config import OPENAI_DEFAULT_MODEL, OPENAI_PDF_SAMPLE_PAGES
from .upload_tab_metadata_utils import (
    append_openai_description as _utm_append_openai_description,
    local_places_from_text as _utm_local_places_from_text,
    merge_metadata_values as _utm_merge_metadata_values,
    merge_place_values as _utm_merge_place_values,
    normalize_upload_text_sample as _utm_normalize_upload_text_sample,
)

LOCAL_PLACE_NAMES = [
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
]


def extract_upload_text_sample(manager: Any, path: Path | None, max_chars: int = 4000, max_pdf_pages: int = OPENAI_PDF_SAMPLE_PAGES) -> str | None:
    """Liest einen kurzen Textauszug für OpenAI und lokale Metadatenableitung.

    Wichtig: Das ist nur eine lokale Dateianalyse. Es wird dabei kein OpenAI-Aufruf
    ausgelöst. Für DOCX wird der Text direkt aus dem ZIP/XML gelesen; dadurch werden
    Protokolle, Briefe usw. nicht nur nach Dateiname bewertet.
    """
    if path is None:
        return None
    cache_key = manager._upload_path_cache_key(path)
    sample_cache_key = None
    cache = getattr(manager, "_upload_text_sample_cache", None)
    if cache_key is not None:
        sample_cache_key = f"{cache_key}|chars={max_chars}|pages={max_pdf_pages}"
        if cache is not None and sample_cache_key in cache:
            return cache[sample_cache_key]
    try:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md", ".csv", ".log"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            sample = manager.normalize_upload_text_sample(text, max_chars=max_chars)
            if cache is not None and sample_cache_key is not None:
                cache[sample_cache_key] = sample
            return sample
        if suffix == ".xlsx":
            text = manager._extract_excel_text(path)
            sample = manager.normalize_upload_text_sample(text, max_chars=max_chars)
            if cache is not None and sample_cache_key is not None:
                cache[sample_cache_key] = sample
            return sample
        if suffix == ".pdf":
            text_parts: list[str] = []
            try:
                import warnings
                from pypdf import PdfReader

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    reader = PdfReader(str(path), strict=False)
                for page in reader.pages[:max_pdf_pages]:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(page_text)
                    if sum(len(part) for part in text_parts) >= max_chars:
                        break
            except Exception as exc:
                app_log_exception("PDF-Textauszug konnte nicht gelesen werden", exc, path=str(path))
            sample = manager.normalize_upload_text_sample("\n".join(text_parts), max_chars=max_chars)
            if cache is not None and sample_cache_key is not None:
                cache[sample_cache_key] = sample
            return sample
        if suffix == ".docx":
            text_parts: list[str] = []
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                xml_names = [n for n in names if n == "word/document.xml" or n.startswith("word/header") or n.startswith("word/footer")]
                for xml_name in xml_names:
                    try:
                        root = ET.fromstring(zf.read(xml_name))
                    except Exception:
                        continue
                    for node in root.iter():
                        if node.tag.endswith("}t") and node.text:
                            text_parts.append(node.text)
                        elif node.tag.endswith("}tab"):
                            text_parts.append("\t")
                        elif node.tag.endswith("}br") or node.tag.endswith("}p"):
                            text_parts.append("\n")
            sample = manager.normalize_upload_text_sample(" ".join(text_parts), max_chars=max_chars)
            if cache is not None and sample_cache_key is not None:
                cache[sample_cache_key] = sample
            return sample
        if suffix == ".odt":
            with zipfile.ZipFile(path) as zf:
                raw = zf.read("content.xml").decode("utf-8", errors="ignore")
            raw = re.sub(r"<text:p[^>]*>", "\n", raw)
            raw = re.sub(r"<[^>]+>", " ", raw)
            sample = manager.normalize_upload_text_sample(raw, max_chars=max_chars)
            if cache is not None and sample_cache_key is not None:
                cache[sample_cache_key] = sample
            return sample
    except Exception as exc:
        app_log_exception("OpenAI-Textauszug konnte nicht gelesen werden", exc, path=str(path))
    if cache is not None and sample_cache_key is not None:
        cache[sample_cache_key] = None
    return None


def _extract_excel_text(manager: Any, path: Path) -> str | None:
    try:
        try:
            import openpyxl
        except Exception:
            openpyxl = None

        if openpyxl is not None:
            text_chunks: list[str] = []
            workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                for worksheet in workbook.worksheets:
                    for row in worksheet.iter_rows(values_only=True):
                        for value in row:
                            text = str(value).strip() if value is not None else ""
                            if text:
                                text_chunks.append(text)
                        if len(text_chunks) > 20000:
                            break
                    if len(text_chunks) > 20000:
                        break
            finally:
                try:
                    workbook.close()
                except Exception:
                    pass
            return " ".join(text_chunks)

        with zipfile.ZipFile(path) as zf:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for item in shared_root:
                    piece: list[str] = []
                    for node in item.iter():
                        if node.tag.endswith("}t") and node.text:
                            piece.append(node.text)
                    value = "".join(piece).strip()
                    if value:
                        shared_strings.append(value)

            sheet_files = [name for name in zf.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")]
            if not sheet_files:
                return None

            text_chunks: list[str] = []
            for sheet_name in sheet_files:
                sheet_root = ET.fromstring(zf.read(sheet_name))
                for cell in sheet_root.iter():
                    if not cell.tag.endswith("}c"):
                        continue
                    value_type = cell.get("t")
                    value_text = ""
                    for child in cell:
                        tag = child.tag
                        if tag.endswith("}v"):
                            value_text = child.text or ""
                            break
                        if value_type == "inlineStr" and tag.endswith("}t"):
                            value_text = child.text or ""
                            break
                    if not value_text:
                        continue
                    if value_type == "s":
                        try:
                            index = int(value_text)
                            if 0 <= index < len(shared_strings):
                                value_text = shared_strings[index]
                        except Exception:
                            pass
                    value = str(value_text).strip()
                    if value:
                        text_chunks.append(value)
                if len(text_chunks) > 20000:
                    break
            return " ".join(text_chunks)
        return None
    except Exception as exc:
        app_log_exception("Excel-Textauszug konnte nicht gelesen werden", exc, path=str(path))
        return None


def normalize_upload_text_sample(text: str | None, max_chars: int = 4000) -> str | None:
    return _utm_normalize_upload_text_sample(text, max_chars=max_chars)


def local_places_from_text(text: str | None) -> list[str]:
    return _utm_local_places_from_text(text, LOCAL_PLACE_NAMES)


def merge_place_values(current: str, suggested: str) -> str:
    return _utm_merge_place_values(current, suggested)


def merge_metadata_values(current: str, suggested: str, separator: str = ", ") -> str:
    return _utm_merge_metadata_values(current, suggested, separator=separator)


def append_openai_description(manager: Any, current: str, suggested: str) -> str:
    model = str(getattr(manager, "openai_metadata_source_model", "") or manager.config_data.get("openai_model", "") or OPENAI_DEFAULT_MODEL).strip()
    return _utm_append_openai_description(current, suggested, model)


def derive_metadata_from_text(manager: Any, filename: str, extension: str, sample: str | None) -> dict[str, str]:
    """Robuste lokale Fallback-Ableitung für typische Protokolle/Niederschriften.

    Diese Werte kosten keine API-Tokens und verhindern, dass bei DOCX-Dateien mit
    klar erkennbarem Inhalt der Übernahme-Button leer bleibt, nur weil das Modell
    vorsichtig oder zu knapp antwortet.
    """
    metadata: dict[str, str] = {}
    text = sample or ""
    lower_name = filename.lower()
    lower_text = text.lower()

    if "niederschrift" in lower_name or "niederschrift" in lower_text:
        metadata["document_type"] = "Niederschrift / Protokoll"
    elif extension.lower() == ".docx":
        metadata["document_type"] = "Word-Dokument"

    date_match = re.search(r"(?:am|Zeit/Dauer:)\s*(\d{1,2}\.\d{1,2}\.\d{4})", text, flags=re.IGNORECASE)
    if not date_match:
        date_match = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", text)
    if date_match:
        metadata["document_date"] = date_match.group(1)

    place_match = re.search(r"(?:^|\n)\s*Ort:\s*([^\n]+)", text, flags=re.IGNORECASE)
    if place_match:
        metadata["place"] = place_match.group(1).strip(" .;,-")
    detected_places = manager.local_places_from_text(text)
    if detected_places:
        metadata["place"] = manager.merge_place_values(metadata.get("place", ""), ", ".join(detected_places))

    title_line = ""
    for line in text.splitlines():
        line = line.strip()
        if line:
            title_line = line
            break
    if title_line:
        event = title_line
        event = re.sub(r"^Niederschrift\s+über\s+die\s+", "", event, flags=re.IGNORECASE)
        event = re.sub(r"\s+am\s+\d{1,2}\.\d{1,2}\.\d{4}.*$", "", event, flags=re.IGNORECASE).strip()
        metadata["event"] = event[:160]

    keywords: list[str] = []
    keyword_candidates = [
        "Ortschronisten", "Stadt Römhild", "Sülzdorf", "Zeilfeld", "Gleichamberg",
        "Steinsburgfreunde", "altes Rathaus Römhild", "Geschichtsblätter", "Kinder wie die Zeit vergeht",
        "Datenschutz", "DSGVO", "Internetseite", "Fördermittel", "Thüringer Ehrenamtsstiftung",
        "Grabsteinprojekt", "Computergenealogie", "Ortschronistensatzung", "Flurnamenarchiv",
        "Kreisheimattag", "Tag des offenen Denkmals",
    ]
    for kw in keyword_candidates:
        if kw.lower() in lower_text:
            keywords.append(kw)
    if keywords:
        metadata["keywords"] = ", ".join(list(dict.fromkeys(keywords))[:12])

    if text:
        description_parts: list[str] = []
        if title_line:
            description_parts.append(title_line.rstrip("."))
        if metadata.get("place") or metadata.get("document_date"):
            description_parts.append(
                "Ort/Zeit: " + ", ".join(v for v in [metadata.get("place", ""), metadata.get("document_date", "")] if v)
            )
        topics: list[str] = []
        for kw in ["Steinsburgfreunde", "Arbeitsräume", "Geschichtsblätter", "Datenschutz", "Internetseite", "Fördermittel", "Grabsteinprojekt", "Ortschronistensatzung"]:
            if kw.lower() in lower_text:
                topics.append(kw)
        if topics:
            description_parts.append("Behandelte Themen: " + ", ".join(topics[:8]) + ".")
        if description_parts:
            metadata["description"] = " ".join(description_parts)[:600]

    if "ortschronisten" in lower_text:
        metadata.setdefault("primary_source", "Ortschronisten der Stadt Römhild")
    return metadata
