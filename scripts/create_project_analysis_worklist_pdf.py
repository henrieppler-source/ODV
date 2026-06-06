from __future__ import annotations

from datetime import datetime
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ODV_Arbeitsliste_Projektanalyse_v121.pdf"
FONT_10PT = round(10 * 300 / 72)


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts") / name,
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


FONT_TITLE = load_font("arialbd.ttf", FONT_10PT)
FONT_H1 = load_font("arialbd.ttf", FONT_10PT)
FONT_H2 = load_font("arialbd.ttf", FONT_10PT)
FONT_BODY = load_font("arial.ttf", FONT_10PT)
FONT_SMALL = load_font("arial.ttf", FONT_10PT)
FONT_BOLD = load_font("arialbd.ttf", FONT_10PT)


PAGE_W, PAGE_H = 2480, 3508  # A4 at 300 dpi
MARGIN_X = 170
MARGIN_TOP = 150
MARGIN_BOTTOM = 150
LINE_GAP = 12
PARA_GAP = 28
SECTION_GAP = 42


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class PdfBuilder:
    def __init__(self) -> None:
        self.pages: list[Image.Image] = []
        self.new_page()

    def new_page(self) -> None:
        self.page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        self.draw = ImageDraw.Draw(self.page)
        self.y = MARGIN_TOP
        if self.pages:
            self.draw.text((MARGIN_X, PAGE_H - 95), "ODV Projektanalyse - Arbeitsliste", fill="#777777", font=FONT_SMALL)
        self.pages.append(self.page)

    def ensure_space(self, height: int) -> None:
        if self.y + height > PAGE_H - MARGIN_BOTTOM:
            self.new_page()

    def text(self, value: str, font: ImageFont.ImageFont = FONT_BODY, fill: str = "#1f1f1f", gap: int = PARA_GAP) -> None:
        max_width = PAGE_W - 2 * MARGIN_X
        lines = wrap_text(value, font, max_width)
        line_height = int(font.getbbox("Ag")[3] - font.getbbox("Ag")[1]) + LINE_GAP
        self.ensure_space(line_height * len(lines) + gap)
        for line in lines:
            self.draw.text((MARGIN_X, self.y), line, fill=fill, font=font)
            self.y += line_height
        self.y += gap

    def heading(self, value: str, level: int = 1) -> None:
        font = FONT_H1 if level == 1 else FONT_H2
        fill = "#18324a" if level == 1 else "#2d4c64"
        self.ensure_space(80)
        if level == 1:
            self.y += 8
            self.draw.rectangle((MARGIN_X, self.y + 8, MARGIN_X + 18, self.y + 56), fill="#1f6f8b")
            self.draw.text((MARGIN_X + 32, self.y), value, fill=fill, font=font)
            self.y += 88
        else:
            self.draw.text((MARGIN_X, self.y), value, fill=fill, font=font)
            self.y += 70

    def bullet(self, value: str, checked: bool = False) -> None:
        max_width = PAGE_W - 2 * MARGIN_X - 70
        lines = wrap_text(value, FONT_BODY, max_width)
        line_height = int(FONT_BODY.getbbox("Ag")[3] - FONT_BODY.getbbox("Ag")[1]) + LINE_GAP
        self.ensure_space(line_height * len(lines) + 18)
        box_y = self.y + 2
        self.draw.rectangle((MARGIN_X, box_y, MARGIN_X + 28, box_y + 28), outline="#1f6f8b", width=3)
        if checked:
            self.draw.line((MARGIN_X + 5, box_y + 14, MARGIN_X + 12, box_y + 24, MARGIN_X + 25, box_y + 5), fill="#1f6f8b", width=4)
        x = MARGIN_X + 50
        for line in lines:
            self.draw.text((x, self.y), line, fill="#1f1f1f", font=FONT_BODY)
            self.y += line_height
        self.y += 18

    def callout(self, title: str, body: str) -> None:
        max_width = PAGE_W - 2 * MARGIN_X - 60
        title_h = int(FONT_BOLD.getbbox("Ag")[3] - FONT_BOLD.getbbox("Ag")[1]) + 18
        lines = wrap_text(body, FONT_BODY, max_width)
        line_height = int(FONT_BODY.getbbox("Ag")[3] - FONT_BODY.getbbox("Ag")[1]) + LINE_GAP
        height = title_h + line_height * len(lines) + 52
        self.ensure_space(height + PARA_GAP)
        y0 = self.y
        self.draw.rounded_rectangle((MARGIN_X, y0, PAGE_W - MARGIN_X, y0 + height), radius=22, fill="#eef6f8", outline="#9cc8d3", width=2)
        self.draw.text((MARGIN_X + 30, y0 + 22), title, fill="#18324a", font=FONT_BOLD)
        y = y0 + title_h + 28
        for line in lines:
            self.draw.text((MARGIN_X + 30, y), line, fill="#1f1f1f", font=FONT_BODY)
            y += line_height
        self.y = y0 + height + PARA_GAP

    def save(self, path: Path) -> None:
        first, rest = self.pages[0], self.pages[1:]
        first.save(path, "PDF", resolution=300.0, save_all=True, append_images=rest)


def build() -> None:
    b = PdfBuilder()
    b.draw.rectangle((0, 0, PAGE_W, 260), fill="#18324a")
    b.draw.text((MARGIN_X, 74), "ODV Projektanalyse", fill="white", font=FONT_TITLE)
    b.draw.text((MARGIN_X, 148), "Arbeitsliste zur Bereinigung und Weiterentwicklung", fill="#d7edf3", font=FONT_H2)
    b.y = 330
    b.text(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Version: v121", FONT_SMALL, "#666666")
    b.callout(
        "Kurzfazit",
        "Das Projekt ist funktional und die Python-Module kompilieren, aber es hat durch die schnelle fachliche Erweiterung technische Schulden aufgebaut. "
        "Der nächste sinnvolle Schritt ist keine neue Großfunktion, sondern eine gezielte Bereinigung der Übergangspfade.",
    )

    b.heading("1. Kritische Stolperstellen")
    for item in [
        "Sehr breites Mixin-Geflecht im Hauptfenster: Namenskonflikte und verdeckte Abhängigkeiten werden wahrscheinlicher.",
        "Alte Tabellenlogik aus 'Dateien bearbeiten' lebt noch als Fallback, obwohl 'Dateien anzeigen/bearbeiten' fachlich führend ist.",
        "Doppelte Methoden in upload_tab.py: set_upload_status, evaluate_upload_status, is_upload_metadata_ready und update_upload_status_indicator.",
        "Große Module mit hohem Änderungsrisiko: mail_manager.py, upload_tab.py, postprocess_manager.py, pdf_management_manager.py, admin_operations.py.",
        "Serverseitig ist routes_shared.php mit über 2300 Zeilen der zentrale Alles-Knoten.",
        "Viele hasattr/getattr-Schutzabfragen verschleiern, welche UI-Zustände wirklich garantiert vorhanden sind.",
        "Lokale PDF-Aktionen und zentrale Nextcloud-Sicht sind fachlich richtig, aber technisch noch nicht sauber getrennt.",
    ]:
        b.bullet(item)

    b.heading("2. Offene Arbeitspunkte")
    for item in [
        "Legacy-Tabellenmodus endgültig entfernen oder klar isolieren.",
        "Upload-Statuslogik entdoppeln und in einen einzigen gültigen Ablauf bringen.",
        "PDF-Workflow schärfen: lokale Verfügbarkeit, Sync-Hinweise, Arbeits-PDF, _ocr.pdf, _pdfa.pdf und gemeinsames Umbenennen/Verschieben.",
        "OpenAI-/Ortsanalyse-Persistenz konsolidieren: Cache, Modell-Sperren, gespeicherte Fundstellen, Übernahmehistorie.",
        "Dialoge und Buttonpositionen weiter vereinheitlichen.",
        "Projekt-Health-Prüfung einführen: Versionen, Statuswerte, doppelte Methoden, große Module, alte Begriffe.",
    ]:
        b.bullet(item)

    b.heading("3. Kandidaten für Rückbau")
    for item in [
        "Alter Admin-Tabellenmodus, sofern der gemeinsame Baum-/Metadaten-Reiter final bleibt.",
        "Alte Begriffe 'Dateien anzeigen' und 'Dateien bearbeiten' in UI und Doku, wo fachlich nur noch 'Dateien anzeigen/bearbeiten' gilt.",
        "Historische Statusreste wie 'uebernommen', soweit sie nicht bewusst in der Versionshistorie stehen.",
        "Platzhalter- oder Kompatibilitätsmodule, wenn sie nicht mehr importiert werden.",
        "Doppelte lokale Fallbacks, sobald API/MySQL und Nextcloud-Pfadlogik stabil zentralisiert sind.",
    ]:
        b.bullet(item)

    b.heading("4. Sinnvolle Ergänzungen")
    for item in [
        "Zentrales Statusmodul: Statuswerte, Anzeigenamen, Übergangsregeln und Bewertungsstatus.",
        "Zentrales PDF-Begleitdatei-Modul: Arbeitsdatei, OCR-Datei, PDF/A-Datei, Originalgröße, Prüffunktionen.",
        "Gemeinsame Fortschrittsdialog-Hilfe für lange Tkinter-Aktionen.",
        "Automatisches Projekt-Health-Script für Entwicklerstarts.",
        "Server-Hilfsmodule für Punkte, Nextcloud, Schema/Migrationen und Mail statt eines riesigen routes_shared.php.",
    ]:
        b.bullet(item)

    b.heading("5. Priorisierte Reihenfolge")
    steps = [
        "upload_tab.py bereinigen: doppelte Methoden entfernen, Statuslogik einmalig definieren.",
        "Legacy-Admin-Tabellenlogik prüfen und schrittweise entfernen.",
        "PDF-Begleitdateien in ein Hilfsmodul auslagern und Umbenennen/Verschieben zentral absichern.",
        "OpenAI-/Ortsanalyse-Workflow final konsolidieren.",
        "Server routes_shared.php fachlich aufteilen.",
        "Projekt-Health-Script einbauen.",
        "Dokumentation sprachlich glätten: einheitliche Reiter, Statuswerte, PDF-Begriffe.",
    ]
    for index, item in enumerate(steps, 1):
        b.bullet(f"{index}. {item}")

    b.heading("6. Arbeitscheckliste")
    for item in [
        "Vor jeder Etappe git status prüfen.",
        "Nur zusammenhängende Bereiche anfassen.",
        "Nach jeder Etappe py_compile bzw. passende Tests ausführen.",
        "README.md, Handbuch.md, Admin-Handbuch.md und stand.md fortschreiben.",
        "Keine fremden Änderungen zurücksetzen.",
        "Nach jeder Etappe gezielte Bedienprüfung in ODV durchführen.",
    ]:
        b.bullet(item)

    b.callout(
        "Empfehlung",
        "Als nächstes sollte die technische Bereinigung beginnen, nicht die nächste Großfunktion. "
        "Der größte Nutzen liegt zuerst in upload_tab.py und der Entfernung der alten Tabellen-/Reiterreste.",
    )
    b.save(OUT)


if __name__ == "__main__":
    build()
    print(OUT)
