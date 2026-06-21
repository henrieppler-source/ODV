from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "REALTEST_CHECKLIST.md"
OUT = ROOT / "ODV_Realtest_Checkliste_v121.pdf"

PAGE_W, PAGE_H = 2480, 3508  # A4, 300 dpi
MARGIN_X = 110
MARGIN_TOP = 120
MARGIN_BOTTOM = 110
ROW_PAD_Y = 12


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in [
        Path("C:/Windows/Fonts") / name,
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


FONT_10PT = round(10 * 300 / 72)
FONT_TITLE = load_font("arialbd.ttf", FONT_10PT)
FONT_SUB = load_font("arial.ttf", FONT_10PT)
FONT_H1 = load_font("arialbd.ttf", FONT_10PT)
FONT_H2 = load_font("arialbd.ttf", FONT_10PT)
FONT_TH = load_font("arialbd.ttf", FONT_10PT)
FONT_BODY = load_font("arial.ttf", FONT_10PT)
FONT_SMALL = load_font("arial.ttf", FONT_10PT)


COLS = [
    ("☐", 58),
    ("Bereich / Funktion", 430),
    ("Pruefschritt", 1210),
    ("Notiz / Ergebnis", 562),
]


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    for raw in str(text).splitlines() or [""]:
        raw = raw.strip()
        if not raw:
            lines.append("")
            continue
        words = raw.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if text_size(draw, candidate, font)[0] <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def parse_checklist(path: Path) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_items: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if current_title:
                sections.append((current_title, current_items))
            current_title = line[3:].strip()
            current_items = []
            continue
        if line.startswith("- [ ] "):
            current_items.append(line[6:].strip())
    if current_title:
        sections.append((current_title, current_items))
    return sections


class PdfTableBuilder:
    def __init__(self) -> None:
        self.pages: list[Image.Image] = []
        self.page_no = 0
        self.new_page(title_page=True)

    def new_page(self, title_page: bool = False) -> None:
        self.page_no += 1
        self.page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        self.draw = ImageDraw.Draw(self.page)
        self.pages.append(self.page)
        self.y = MARGIN_TOP
        if title_page:
            self.draw.rectangle((0, 0, PAGE_W, 250), fill="#18324a")
            self.draw.text((MARGIN_X, 62), "ODV Realtest-Checkliste", fill="white", font=FONT_TITLE)
            self.draw.text((MARGIN_X, 136), "Abhakbare Liste fuer den praktischen Gesamttest", fill="#d7edf3", font=FONT_H2)
            self.y = 300
            self.paragraph(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Version: v121 | Projekt: Ortschronisten-Datei-Verwaltung")
            self.paragraph(
                "Hinweis: Die letzte Spalte ist fuer OK, Fehler, Rueckfragen, Testername, Datum oder kurze Notizen gedacht."
            )
        else:
            self.draw.text((MARGIN_X, 58), "ODV Realtest-Checkliste v121", fill="#18324a", font=FONT_H2)
            self.draw.text((PAGE_W - MARGIN_X - 130, 62), f"Seite {self.page_no}", fill="#666666", font=FONT_SMALL)
            self.y = 115

    def ensure(self, height: int) -> None:
        if self.y + height > PAGE_H - MARGIN_BOTTOM:
            self.new_page()

    def paragraph(self, text: str) -> None:
        width = PAGE_W - 2 * MARGIN_X
        lines = wrap_to_width(self.draw, text, FONT_SUB, width)
        line_h = 58
        self.ensure(len(lines) * line_h + 20)
        for line in lines:
            self.draw.text((MARGIN_X, self.y), line, fill="#222222", font=FONT_SUB)
            self.y += line_h
        self.y += 18

    def section(self, title: str) -> None:
        self.ensure(84)
        self.y += 12
        self.draw.rectangle((MARGIN_X, self.y, PAGE_W - MARGIN_X, self.y + 46), fill="#e8f2f5", outline="#a8ccd6")
        self.draw.text((MARGIN_X + 18, self.y + 10), title, fill="#18324a", font=FONT_H1)
        self.y += 66
        self.header()

    def header(self) -> None:
        x = MARGIN_X
        h = 82
        self.ensure(h)
        for label, width in COLS:
            self.draw.rectangle((x, self.y, x + width, self.y + h), fill="#f4f4f4", outline="#8f8f8f", width=2)
            self.draw.text((x + 8, self.y + 20), label, fill="#111111", font=FONT_TH)
            x += width
        self.y += h

    def row(self, values: list[str], shade: bool = False) -> None:
        line_h = 56
        wrapped: list[list[str]] = []
        for value, (_, width) in zip(values, COLS):
            wrapped.append(wrap_to_width(self.draw, value, FONT_BODY, width - 18))
        max_lines = max(len(lines) for lines in wrapped)
        row_h = max(62, max_lines * line_h + ROW_PAD_Y * 2)
        self.ensure(row_h)
        fill = "#fbfbfb" if shade else "white"
        x = MARGIN_X
        for lines, (_, width) in zip(wrapped, COLS):
            self.draw.rectangle((x, self.y, x + width, self.y + row_h), fill=fill, outline="#b0b0b0", width=1)
            yy = self.y + ROW_PAD_Y
            for line in lines:
                self.draw.text((x + 8, yy), line, fill="#1f1f1f", font=FONT_BODY)
                yy += line_h
            x += width
        self.y += row_h

    def save(self, path: Path) -> None:
        self.pages[0].save(path, "PDF", resolution=300.0, save_all=True, append_images=self.pages[1:])


def build() -> None:
    sections = parse_checklist(SOURCE)
    pdf = PdfTableBuilder()
    counter = 1
    for section_title, items in sections:
        pdf.section(section_title)
        for item in items:
            area = section_title.split(".", 1)[1].strip() if "." in section_title else section_title
            pdf.row(["☐", area, item, ""], shade=(counter % 2 == 0))
            counter += 1
    pdf.paragraph("Tipp: Nach dem Test bitte pro Zeile OK, Fehler oder kurze Notiz in der letzten Spalte ergänzen.")
    pdf.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
