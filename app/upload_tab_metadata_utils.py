from __future__ import annotations

import re


def normalize_upload_text_sample(text: str | None, max_chars: int = 4000) -> str | None:
    if not text:
        return None
    text = text.replace("\u00ad", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return None
    return text[:max_chars]


def local_places_from_text(text: str | None, local_place_names: list[str]) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for place in local_place_names:
        if re.search(rf"(?<!\w){re.escape(place)}(?!\w)", text, flags=re.IGNORECASE):
            found.append(place)
    return found


def merge_place_values(current: str, suggested: str) -> str:
    values: list[str] = []
    for raw in [current, suggested]:
        for part in re.split(r"[,;/\n]+", raw or ""):
            text = part.strip(" .;,-")
            if text and text.lower() not in {v.lower() for v in values}:
                values.append(text)
    return ", ".join(values)


def merge_metadata_values(current: str, suggested: str, separator: str = ", ") -> str:
    current = str(current or "").strip()
    suggested = str(suggested or "").strip()
    if not suggested:
        return current
    if not current:
        return suggested
    values: list[str] = []
    for raw in [current, suggested]:
        for part in re.split(r"[,;\n]+", raw):
            text = part.strip(" .;,-")
            if text and text.lower() not in {v.lower() for v in values}:
                values.append(text)
    if len(values) <= 1:
        return current
    return separator.join(values)


def append_openai_description(current: str, suggested: str, model: str) -> str:
    suggested = str(suggested or "").strip()
    if not suggested:
        return current
    model = str(model or "").strip()
    block = f"**{model}**: {suggested}"
    current = str(current or "").strip()
    if not current:
        return block
    if suggested.lower() in current.lower() or block.lower() in current.lower():
        return current
    return current + "\n\n" + block

