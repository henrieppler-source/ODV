from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def slugify(value: str, counts: dict[str, int]) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    text = re.sub(r"[\s-]+", "-", text).strip("-") or "kapitel"
    counts[text] = counts.get(text, 0) + 1
    return text if counts[text] == 1 else f"{text}-{counts[text]}"


def replace_toc(path: str, toc_heading_pattern: str, max_level: int = 2) -> None:
    file_path = Path(path)
    lines = file_path.read_text(encoding="utf-8").splitlines()
    headings: list[tuple[int, str, str]] = []
    counts: dict[str, int] = {}
    excluded = {"ODV-Handbuch für Bearbeiter", "ODV-Admin-Handbuch", "Inhalt", "Inhaltsübersicht"}
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        title = match.group(2).strip()
        if level == 1 and title in excluded:
            continue
        if level <= max_level:
            headings.append((level, title, slugify(title, counts)))

    toc = ["# Inhalt", ""]
    for level, title, slug in headings:
        toc.append(f"{'  ' * (level - 1)}- [{title}](#{slug})")
    toc.append("")

    start = None
    for index, line in enumerate(lines):
        if re.match(toc_heading_pattern, line):
            start = index
            break
    if start is None:
        new_lines = lines[:1] + [""] + toc + lines[1:]
    else:
        end = start + 1
        next_section = re.compile(r"^#\s+(?:\d+\.|Anlage|Ergänzung|Fortschreibung)")
        while end < len(lines) and not next_section.match(lines[end]):
            end += 1
        new_lines = lines[:start] + toc + lines[end:]
    file_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    replace_toc("Handbuch.md", r"^#\s+Inhalt\s*$")
    replace_toc("Admin-Handbuch.md", r"^#\s+Inhaltsübersicht\s*$")
