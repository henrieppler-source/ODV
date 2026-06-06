from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import load_config
from .file_service import normalize_date_for_filename, normalize_filename_component, strip_existing_date_prefix


DEFAULT_FILENAME_TEMPLATE = "{datum}_{ort}_{dateiname}"


def configured_filename_template(config: dict[str, Any] | None = None) -> str:
    data = config if config is not None else load_config()
    template = str(data.get("filename_normalization_template") or "").strip()
    return template or DEFAULT_FILENAME_TEMPLATE


def filename_normalization_rules(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = config if config is not None else load_config()
    rules = data.get("filename_normalization_rules")
    if not isinstance(rules, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for rule in rules:
        if isinstance(rule, dict):
            cleaned.append(
                {
                    "name": str(rule.get("name") or "").strip(),
                    "folder": str(rule.get("folder") or "").strip(),
                    "template": str(rule.get("template") or "").strip(),
                    "active": bool(rule.get("active", True)),
                }
            )
    return cleaned


def filename_template_is_safe(template: str) -> bool:
    """Sicherheitsregel: Regeln müssen mindestens Dateiname oder Datum enthalten."""
    text = str(template or "").strip()
    if not text:
        return False
    if "/" in text or "\\" in text or ":" in text:
        return False
    allowed = {
        "datum",
        "jahr",
        "monat",
        "tag",
        "ort",
        "ereignis",
        "quelle",
        "erfasst",
        "bearbeitet",
        "dateiname",
        "dateiname_mmdd",
        "original",
        "ordner",
    }
    allowed.update({f"ordner{i}" for i in range(1, 10)})
    placeholders = set(re.findall(r"{([a-zA-Z0-9_]+)}", text))
    if any(name.lower() not in allowed for name in placeholders):
        return False
    return any(name in placeholders for name in {"dateiname", "datum", "jahr", "dateiname_mmdd"})


def _metadata_path(metadata: dict[str, Any]) -> Path | None:
    for key in ("current_path", "target_folder"):
        value = str(metadata.get(key) or "").strip()
        if value:
            try:
                return Path(value)
            except Exception:
                pass
    return None


def _path_parts_for_placeholders(metadata: dict[str, Any]) -> list[str]:
    path = _metadata_path(metadata)
    if not path:
        return []
    parts = list(path.parts)
    if path.suffix:
        parts = parts[:-1]
    root_tokens = {
        "00_ortschronik",
        "01_ablage_ortschronik",
        "02_austausch",
        "03_information",
        "05_orga_chronisten",
        "06_arbeit_der_ortschronisten",
    }
    normalized = [normalize_filename_component(p) for p in parts]
    for idx, token in enumerate(normalized):
        if token in root_tokens:
            useful = parts[idx + 1 :]
            break
    else:
        known_roots = {"nextcloud_oc", "nextcloud", "c:", "d:", "e:"}
        useful = [p for p in parts if normalize_filename_component(p) not in known_roots]
    return useful[-9:]


def _rule_matches_folder(rule: dict[str, Any], metadata: dict[str, Any]) -> bool:
    folder = str(rule.get("folder") or "").strip()
    if not folder:
        return False
    wanted = normalize_filename_component(folder).replace("_", "")
    path = _metadata_path(metadata)
    if not path:
        return False
    candidates = [normalize_filename_component(part).replace("_", "") for part in path.parts]
    normalized_path = normalize_filename_component(" ".join(path.parts)).replace("_", "")
    return wanted in normalized_path or any(wanted == part or wanted in part for part in candidates)


def matching_filename_rule(metadata: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for rule in filename_normalization_rules(config):
        if rule.get("active") and filename_template_is_safe(str(rule.get("template") or "")) and _rule_matches_folder(rule, metadata):
            return rule
    return None


def _date_parts(date_text: str) -> tuple[str, str, str, str]:
    normalized = normalize_date_for_filename(date_text) or ""
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", normalized)
    if m:
        return normalized, m.group(1), m.group(2), m.group(3)
    m = re.match(r"^(\d{4})(\d{2})$", normalized)
    if m:
        return normalized, m.group(1), m.group(2), ""
    m = re.match(r"^(\d{4})", normalized)
    if m:
        return normalized, m.group(1), "", ""
    return normalized, "", "", ""


def _filename_mmdd(stem: str, date_text: str) -> str:
    _date, _year, month, day = _date_parts(date_text)
    if month and day:
        return f"{month}{day}"
    match = re.search(r"(?<!\d)(?:\d{4}[-_ .])?(\d{1,2})[-_ .](\d{1,2})(?!\d)", stem)
    if match:
        return f"{int(match.group(1)):02d}{int(match.group(2)):02d}"
    return ""


def filename_template_values(metadata: dict[str, Any], requested_filename: str) -> dict[str, str]:
    requested = (requested_filename or metadata.get("current_filename") or metadata.get("stored_filename") or metadata.get("original_filename") or "datei").strip()
    stem = strip_existing_date_prefix(Path(requested).stem if Path(requested).stem else requested)
    date_text = str(metadata.get("document_date") or metadata.get("date") or "")
    date_part, year, month, day = _date_parts(date_text)
    folders = _path_parts_for_placeholders(metadata)
    values = {
        "datum": date_part or "0000",
        "jahr": year or "0000",
        "monat": month,
        "tag": day,
        "ort": str(metadata.get("place") or metadata.get("ort") or ""),
        "ereignis": str(metadata.get("event") or metadata.get("ereignis") or ""),
        "quelle": str(metadata.get("primary_source") or metadata.get("source") or metadata.get("quelle") or ""),
        "erfasst": str(metadata.get("uploaded_by") or metadata.get("created_by") or ""),
        "bearbeitet": str(metadata.get("edited_by") or ""),
        "dateiname": stem,
        "dateiname_mmdd": _filename_mmdd(stem, date_text),
        "original": Path(str(metadata.get("original_filename") or requested)).stem,
        "ordner": folders[-1] if folders else "",
    }
    for idx in range(1, 10):
        values[f"ordner{idx}"] = folders[idx - 1] if idx <= len(folders) else ""
    return values


def render_filename_template(template: str, metadata: dict[str, Any], requested_filename: str) -> str:
    values = filename_template_values(metadata, requested_filename)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).lower()
        return normalize_filename_component(values.get(key, ""))

    rendered = re.sub(r"{([a-zA-Z0-9_]+)}", replace, str(template or ""))
    rendered = normalize_filename_component(rendered)
    rendered = re.sub(r"_+", "_", rendered).strip("_")
    return rendered or "datei"
