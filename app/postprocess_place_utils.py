from __future__ import annotations

from pathlib import Path
import re


def admin_place_names_for_scan(place_folder_map: dict, current_place: str) -> list[str]:
    names: set[str] = set()
    for value in place_folder_map.keys():
        text = str(value or "").strip()
        if text:
            names.add(text)
    for value in place_folder_map.values():
        folder = Path(str(value or ""))
        name = folder.name.strip()
        if "_" in name:
            name = name.split("_", 1)[1]
        if name:
            names.add(name.replace("_", " "))
    if current_place.strip():
        names.add(current_place.strip())
    return sorted((name for name in names if len(name) >= 3), key=lambda name: (-len(name), name.casefold()))


def clean_place_context_text(text: str) -> str:
    """Glättet PDF-/OCR-Textausschnitte für Ortsanalyse und Anzeige."""
    value = str(text or "")
    if not value.strip():
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"(?<=[A-Za-zÄÖÜäöüß])-+\s*\n\s*(?=[A-Za-zÄÖÜäöüß])", "", value)
    value = re.sub(r"\s*\n\s*", " ", value)
    value = re.sub(r"(?<=[A-Za-zÄÖÜäöüß])-+\s+(?=[a-zäöüß])", "", value)
    value = re.sub(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])", " ", value)
    value = re.sub(r"\b([A-ZÄÖÜ])\s+([a-zäöüß]{2,})\b", r"\1\2", value)
    common_tail_words = {
        "d": {"em", "er", "ie", "as", "en"},
        "n": {"icht"},
        "a": {"us"},
        "s": {"ich"},
        "m": {"it"},
        "u": {"nd"},
    }
    for first_letter, tails in common_tail_words.items():
        tail_pattern = "|".join(sorted(tails, key=len, reverse=True))
        value = re.sub(
            rf"\b([A-Za-zÄÖÜäöüß]{{3,}})({first_letter})\s+({tail_pattern})\b",
            lambda match: f"{match.group(1)} {match.group(2)}{match.group(3)}",
            value,
            flags=re.IGNORECASE,
        )
    value = value.replace("„ ", "„").replace(" “", "“").replace(" ,", ",").replace(" .", ".")
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def find_place_contexts_in_text(
    text: str,
    places: list[str],
    context_chars: int = 650,
    max_contexts: int = 30,
) -> list[dict[str, str]]:
    contexts: list[dict[str, str]] = []
    seen: set[tuple[str, int]] = set()
    normalized_text = str(text or "")
    for place in places:
        variants = {place}
        variants.add(
            place.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("Ä", "Ae")
            .replace("Ö", "Oe")
            .replace("Ü", "Ue")
            .replace("ß", "ss")
        )
        variants.add(
            place.replace("ä", "a")
            .replace("ö", "o")
            .replace("ü", "u")
            .replace("Ä", "A")
            .replace("Ö", "O")
            .replace("Ü", "U")
            .replace("ß", "ss")
        )
        variant_pattern = "|".join(re.escape(variant) for variant in sorted(variants, key=len, reverse=True) if variant)
        if not variant_pattern:
            continue
        pattern = re.compile(rf"(?<!\w)(?:{variant_pattern})(?!\w)", flags=re.IGNORECASE)
        for match in pattern.finditer(normalized_text):
            start = max(0, match.start() - context_chars)
            end = min(len(normalized_text), match.end() + context_chars)
            key = (place.casefold(), start)
            if key in seen:
                continue
            seen.add(key)
            snippet = clean_place_context_text(normalized_text[start:end])
            if snippet:
                contexts.append({"place": place, "text": snippet})
            if len(contexts) >= max_contexts:
                return contexts
    return contexts


def place_context_counts(contexts: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for context in contexts:
        place = str(context.get("place") or "").strip()
        if place:
            counts[place] = counts.get(place, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0].casefold()))


def compact_openai_place_contexts(contexts: list[dict[str, str]]) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    for context in contexts:
        place = str(context.get("place") or "").strip()
        text = clean_place_context_text(str(context.get("text") or ""))
        if not place or not text:
            continue
        compact.append({"place": place, "text": text[:1500]})
    return compact
