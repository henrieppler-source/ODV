from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def text_of(element: ET.Element) -> str:
    parts: list[str] = []
    for node in element.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "t" and node.text:
            parts.append(node.text)
        elif tag in {"tab"}:
            parts.append(" ")
        elif tag in {"br", "cr"}:
            parts.append("\n")
    return re.sub(r"[ \t]+", " ", "".join(parts)).strip()


def paragraph_style(paragraph: ET.Element) -> str:
    node = paragraph.find("./w:pPr/w:pStyle", NS)
    if node is None:
        return ""
    return node.attrib.get(f"{{{NS['w']}}}val", "")


def markdown_paragraph(paragraph: ET.Element) -> str:
    text = text_of(paragraph)
    if not text:
        return ""
    style = paragraph_style(paragraph).lower()
    match = re.search(r"heading([1-6])|berschrift([1-6])", style)
    if match:
        level = int(match.group(1) or match.group(2))
        return f"{'#' * level} {text}"
    if style.startswith("title") or "titel" in style:
        return f"# {text}"
    return text


def markdown_table(table: ET.Element) -> str:
    rows: list[list[str]] = []
    for tr in table.findall("./w:tr", NS):
        row: list[str] = []
        for tc in tr.findall("./w:tc", NS):
            cell_parts = [markdown_paragraph(p) for p in tc.findall("./w:p", NS)]
            cell = "<br>".join(part for part in cell_parts if part)
            row.append(cell.replace("|", "\\|"))
        if row:
            rows.append(row)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def convert_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find("w:body", NS)
    if body is None:
        return ""
    blocks: list[str] = []
    for child in body:
        name = child.tag.rsplit("}", 1)[-1]
        if name == "p":
            block = markdown_paragraph(child)
        elif name == "tbl":
            block = markdown_table(child)
        else:
            block = ""
        if block:
            blocks.append(block)
    text = "\n\n".join(blocks).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--title", default="")
    args = parser.parse_args()
    source = Path(args.source)
    target = Path(args.target)
    content = convert_docx(source)
    if args.title:
        content = f"# {args.title}\n\n" + re.sub(r"^# .+?\n+", "", content, count=1)
    target.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
