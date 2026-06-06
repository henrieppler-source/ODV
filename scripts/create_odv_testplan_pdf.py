from __future__ import annotations

from datetime import datetime
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ODV_Pruef_Testplan_v121.pdf"
FONT_10PT = round(10 * 300 / 72)

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


FONT_TITLE = load_font("arialbd.ttf", FONT_10PT)
FONT_SUB = load_font("arial.ttf", FONT_10PT)
FONT_H1 = load_font("arialbd.ttf", FONT_10PT)
FONT_H2 = load_font("arialbd.ttf", FONT_10PT)
FONT_TH = load_font("arialbd.ttf", FONT_10PT)
FONT_BODY = load_font("arial.ttf", FONT_10PT)
FONT_SMALL = load_font("arial.ttf", FONT_10PT)


COLS = [
    ("Nr.", 92),
    ("Bereich / Funktion", 315),
    ("Testschritt", 660),
    ("Erwartetes Ergebnis", 640),
    ("Pruefergebnis / Notizen", 515),
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
            self.draw.text((MARGIN_X, 62), "ODV Pruef-Testplan", fill="white", font=FONT_TITLE)
            self.draw.text((MARGIN_X, 136), "Gezielter Funktionstest fuer Eingaben, Formulare und Workflows", fill="#d7edf3", font=FONT_H2)
            self.y = 300
            self.paragraph(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Version: v121 | Projekt: Ortschronisten-Datei-Verwaltung")
            self.paragraph(
                "Ziel: Dieser Plan fuehrt systematisch durch die wichtigsten ODV-Funktionen. "
                "Die letzte Spalte ist bewusst frei fuer OK, Fehler, Rueckfrage, Testername, Datum oder kurze Notizen."
            )
        else:
            self.draw.text((MARGIN_X, 58), "ODV Pruef-Testplan v121", fill="#18324a", font=FONT_H2)
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
        self.ensure(70)
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


SECTIONS: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "A. Start, Anmeldung und Grundzustand",
        [
            ("Programmstart", "ODV per launcher.py -q starten.", "Hauptfenster erscheint, keine Tracebacks im Terminal."),
            ("Login", "Mit Superadmin, Admin und Bearbeiter jeweils anmelden.", "Rolle, Name und Ortszuordnung werden korrekt angezeigt."),
            ("API-Status", "Hilfe > Systemstatus oeffnen.", "API verbunden, Version v121 passend, Wartungsstatus sichtbar."),
            ("Fehlerlogs", "Hilfe > Logdateien oeffnen und app.log/error.log pruefen.", "Keine neuen unerwarteten Fehler beim Start."),
            ("Benutzerwechsel", "Abmelden/Benutzer wechseln und Dialog abbrechen.", "Vorheriger Benutzer bleibt aktiv oder Wechsel erfolgt kontrolliert."),
            ("Fensterzustand", "Fenster verschieben/groesse aendern, ODV neu starten.", "Geometrie wird sinnvoll wiederhergestellt."),
        ],
    ),
    (
        "B. Stammdaten, Einstellungen und Sicherheit",
        [
            ("Stammdaten", "Datei > Stammdaten oeffnen, Nextcloud-Stammverzeichnis pruefen.", "Pfad ist korrekt, Metadatenordner wird angezeigt."),
            ("Admin-Einstellungen", "Admin > Admin-Einstellungen oeffnen und alle Reiter ansehen.", "Dialog oeffnet ohne Fehler, Werte sind plausibel."),
            ("Passwortfelder", "FTP/OpenAI/Nextcloud/Benutzerpasswort mit gespeichertem Wert ansehen.", "Gespeicherte Passwoerter werden als *** angezeigt, nicht im Klartext."),
            ("FTP-Test", "FTP-Verbindung pruefen.", "Erfolgreicher Test oder klare Fehlermeldung."),
            ("OpenAI-Test", "OpenAI-Schluessel pruefen.", "Schluesseltest liefert ein Ergebnis, keine NameError/Tracebacks."),
            ("Nextcloud-Test", "Technischen Nextcloud-Zugang pruefen.", "Test erfolgreich oder nachvollziehbare WebDAV/Anmelde-Meldung."),
            ("Admin-Ordner", "Admin-Bearbeitungsordner bearbeiten/speichern.", "Auswahl bleibt erhalten, Dateiansicht aktualisiert sich."),
            ("PDF-Schwellwerte", "Warnung/Empfehlung/Blockade und Optimierungsprofil speichern.", "Werte werden gespeichert und nach erneutem Oeffnen angezeigt."),
        ],
    ),
    (
        "C. Benutzer, Rechte und Sichtbarkeit",
        [
            ("Benutzerliste", "Benutzerverwaltung als Superadmin oeffnen.", "Alle Benutzer werden geladen, E-Mail/Rolle/Ort sichtbar."),
            ("Benutzerpasswort", "Bestehenden Benutzer waehlen.", "Passwortfeld zeigt *** bei gespeichertem Passwort."),
            ("Benutzer speichern", "Benutzer ohne Passwortaenderung speichern.", "Bestehendes Passwort bleibt erhalten."),
            ("Nextcloud-Benutzerdaten", "Nextcloud-Name/Passwort beim Benutzer erfassen und speichern.", "Passwort wird nicht im Klartext wieder angezeigt."),
            ("Rollenrechte", "Als Bearbeiter anmelden.", "Admin-/Superadmin-Menues sind ausgeblendet oder gesperrt."),
            ("Leserechte", "Dateien anzeigen/bearbeiten als Bearbeiter pruefen.", "Nur leseberechtigte Ordner/Dateien sichtbar."),
            ("Schreibrechte", "Metadaten bei nicht berechtigter Datei anklicken.", "Felder sind gesperrt und Hinweis erklaert die fehlende Berechtigung."),
        ],
    ),
    (
        "D. Upload und Metadatenerfassung",
        [
            ("Datei auswaehlen", "Bild, PDF, DOCX/ODT nacheinander auswaehlen.", "Dokumenttyp, Zielname und Statusanzeige werden plausibel gesetzt."),
            ("Drag & Drop", "Einzelne Datei in Upload-Reiter ziehen.", "Datei wird uebernommen, kein Sofortupload."),
            ("Mehrfach-Drop", "Mehrere Dateien ziehen.", "ODV zeigt Hinweis und nutzt kontrolliert eine Datei oder lehnt ab."),
            ("Metadatenpflicht", "Upload ohne Pflichtangaben versuchen.", "ODV verhindert Upload oder zeigt klare Hinweise."),
            ("OpenAI Upload", "Lesbares Dokument mit OpenAI pruefen.", "Vorschlaege werden angezeigt/uebernommen und Modell/Kosten sichtbar."),
            ("OpenAI Cache", "Dasselbe Dokument erneut mit gleichem Modell pruefen.", "Kein doppelter kostenpflichtiger Aufruf; Cache/Blockade greift."),
            ("OCR Upload", "Bild-PDF ohne Text auswaehlen.", "OCR-Hinweis erscheint, OCR kann erzeugt und verknuepft werden."),
            ("Personenmarkierung", "Bild auswaehlen und Personen markieren.", "Markierungen werden gespeichert, Personstatus aktualisiert."),
            ("Upload speichern", "Datei hochladen.", "Datei liegt im Zielordner, JSON/ODV-Metadaten und API-Datensatz werden erzeugt."),
        ],
    ),
    (
        "E. Dateien anzeigen/bearbeiten",
        [
            ("Baumansicht", "Reiter Dateien anzeigen/bearbeiten oeffnen.", "Baum zeigt Nextcloud-Struktur gemaess Rechten."),
            ("Statusfilter alle", "Status 'alle' waehlen.", "ODV-Dateien und Dateien ohne ODV-Eintrag werden angezeigt."),
            ("Statusfilter ohne", "Status 'ohne' waehlen.", "Nur physische Dateien ohne ODV-Eintrag werden angezeigt."),
            ("Stern-Markierung", "Dateien ohne ODV-Eintrag suchen.", "Dateiname hat * vorangestellt, Sortierung bleibt nach echtem Namen."),
            ("Groesse-Markierung", "Grosse PDF pruefen.", "Datei wird mit !! markiert, falls Schwellwert ueberschritten."),
            ("Metadaten anzeigen", "ODV-Datei anklicken.", "Metadaten erscheinen rechts, Upload-ID nur als grauer Text."),
            ("Metadaten speichern", "Feld aendern und Fokus verlassen / Speichern druecken.", "Aenderung bleibt nach Dateiwahlwechsel erhalten."),
            ("Bearbeitet von/am", "Metadaten aendern.", "Bearbeitet von/am werden auf letzten Bearbeiter/Zeitpunkt gesetzt."),
            ("Erfasst von", "Als Admin Erfasser aendern.", "Aenderung wird gespeichert, keine Tracebacks."),
            ("Vorschau-Reiter", "Bilddatei auswaehlen.", "Reiter Vorschau/Personen erscheint; bei Nicht-Bild verschwindet er."),
            ("Bildzoom", "Mausrad auf Bildvorschau nutzen.", "Bild vergroessert/verkleinert sich kontrolliert."),
            ("Rechtsklick", "Datei im Baum rechts anklicken.", "Kontextmenue zeigt nur passende Aktionen."),
        ],
    ),
    (
        "F. Umbenennen, Verschieben und Normalisierung",
        [
            ("Admin-Dateiaktion", "Als Admin Datei ablegen in und Neuer Dateiname setzen.", "Datei wird verschoben/umbenannt, Metadaten werden aktualisiert."),
            ("Bearbeiter-Dateiaktion", "Als Bearbeiter eigene/berechtigte Datei umbenennen.", "Nur erlaubte Felder sichtbar, Statuslogik greift."),
            ("OCR-Mitfuehrung", "Datei mit _ocr.pdf umbenennen/verschieben.", "OCR-Begleitdatei wird mitgezogen und bleibt verknuepft."),
            ("PDF/A-Mitfuehrung", "Datei mit _pdfa.pdf umbenennen/verschieben.", "PDF/A-Begleitdatei bleibt kongruent."),
            ("Normalisierung Standard", "Normalen Dateinamen erzeugen lassen.", "Umlaute/Kleinschreibung/Unterstriche entsprechend Standard."),
            ("Sonderregel", "Datei in Zeitungsordner normalisieren.", "Ordner-/Platzhalterregel wird angewandt, z. B. freies_wort_YYYY_MMDD.pdf."),
            ("Sicherheitsregel", "Ungueltige Normalisierungsvorlage speichern.", "ODV blockiert oder warnt nachvollziehbar."),
        ],
    ),
    (
        "G. OpenAI und Orte pruefen",
        [
            ("OpenAI pruefen", "Lesbares Dokument in Dateiansicht pruefen.", "Modelldialog erscheint; Metadatenvorschlaege werden angezeigt."),
            ("Felduebernahme", "Je Feld uebernehmen/ueberschreiben/anhaengen testen.", "Nur gewaehlte Felder werden geaendert."),
            ("Leere Felder", "Dokument mit leeren Metadaten pruefen.", "Leere Felder sind mit uebernehmen vorbelegt."),
            ("Dokumenttyp", "OpenAI liefert anderen Dokumenttyp.", "Dokumenttyp wird nicht durch OpenAI veraendert."),
            ("Doppeltes Modell", "Dasselbe Dokument mit gleichem Modell erneut pruefen.", "Erneuter kostenpflichtiger Aufruf wird verhindert oder Cache genutzt."),
            ("Anderes Modell", "Admin waehlt anderes Modell.", "Neuer Aufruf moeglich; Modell wird dokumentiert."),
            ("Orte lokal", "Dokument mit bekannten Ortsnamen pruefen.", "ODV zeigt gefundene Orte/Fundstellen vor OpenAI-Start."),
            ("Orte kein Treffer", "Dokument ohne Ortsnamen pruefen.", "Fallback-Textprobe nach Einstellungen wird angeboten."),
            ("Fundstellen anzeigen", "Nach Ortsanalyse Fundstellen anzeigen.", "Fundstellen sind lesbar gruppiert und ressourcenschonend gespeichert."),
            ("Beschreibung", "OpenAI-Beschreibung uebernehmen.", "Beschreibung beginnt mit 'enthaelt u.a.' bzw. wird entsprechend normalisiert."),
        ],
    ),
    (
        "H. PDF, OCR, PDF/A und Optimierung",
        [
            ("PDF-Uebersicht", "Uebersichten > PDF-Dateien oeffnen.", "Tabelle zeigt PDF-Arbeitsdateien, Pfad, Groessen und Begleitfassungen."),
            ("Filter Ordner", "In PDF-Uebersicht Ordner auswaehlen.", "Nur PDFs dieses Ordners werden angezeigt."),
            ("Filter Groesse", "Dateigroesse groesser als z. B. 250 MB setzen.", "Nur groessere PDFs bleiben sichtbar."),
            ("Spaltensortierung", "Spaltentitel anklicken.", "Sortierung wechselt nachvollziehbar."),
            ("PDF optimieren", "PDF per Rechtsklick optimieren.", "Fortschrittsdialog erscheint; Datei wird nur ersetzt, wenn kleiner."),
            ("Gesperrte PDF", "PDF in Adobe/Explorer offen lassen und optimieren.", "ODV meldet Dateisperre verstaendlich, kein roher WinError."),
            ("Kein Gewinn", "Optimierung ohne kleinere Datei provozieren.", "Arbeitsdatei bleibt unveraendert, Uebersicht zeigt X."),
            ("PDF/A erzeugen", "PDF/A per Rechtsklick erzeugen.", "_pdfa.pdf entsteht oder Ghostscript-Hinweis erscheint."),
            ("OCR anzeigen", "Datei mit OCR-Begleitfassung rechtsklicken.", "OCR-Anzeige wird nur angeboten, wenn _ocr.pdf vorhanden ist."),
            ("PDF/A oeffnen", "Datei oeffnen bei vorhandener PDF/A.", "ODV oeffnet bevorzugt PDF/A-Fassung, falls vorgesehen."),
            ("Log CSV", "PDF-Uebersicht aktualisieren.", "pdf_sizes.csv wird ohne Fehler geschrieben."),
        ],
    ),
    (
        "I. Punkte und Sonderpunkte",
        [
            ("Mein Punktestand", "Punkte > Mein Punktestand oeffnen.", "Eigene Punkte werden geladen; Admin kann Benutzer wechseln."),
            ("Automatische Punkte", "Metadaten/Personen/Bearbeitung ausfuehren.", "Punkte werden gemaess Regeln berechnet."),
            ("Punktdetails", "Datei waehlen und Punktdetails oeffnen.", "Details zeigen automatische und manuelle Punkte."),
            ("Sonderpunkte", "Admin vergibt Sonderpunkte zum Dokument.", "Eintrag wird gespeichert und ist editierbar."),
            ("Sonderpunkte loeschen", "Manuellen Sonderpunkt loeschen.", "Punkteuebersicht aktualisiert sich."),
            ("Jahresabschluss", "Punktejahr pruefen/schliessen, falls Testumgebung.", "Geschlossenes Jahr ist gegen Aenderung geschuetzt."),
        ],
    ),
    (
        "J. Mail, Verteiler und Historie",
        [
            ("Menuesicht Bearbeiter", "Als Bearbeiter Menue Mail oeffnen.", "Rundmail, Verteiler verwalten und Mailhistorie gemaess Rechten sichtbar."),
            ("Verteiler Bearbeiter", "Bearbeiter legt Verteiler an.", "Benutzer mit E-Mail sind sichtbar; Speichern erlaubt fuer eigene/ortsbezogene Verteiler."),
            ("Verteiler Admin", "Admin/Superadmin verwaltet Verteiler.", "Admin sieht passende Admin-Verteiler, keine falschen Bearbeiterlisten."),
            ("Rundmail Antwort an", "Rundmail oeffnen.", "Antwort-an ist mit aktueller Benutzer-Mail vorbelegt."),
            ("Betreff", "Rundmail neu oeffnen.", "Betreff ist leer."),
            ("Empfaengerlogik", "Verteiler waehlen.", "Empfaenger werden markiert und rollenbasiert begrenzt."),
            ("Standardtexte", "Als Admin Standard-Mail-Text laden.", "Text wird geladen; Bearbeiter haben keinen Standardtextzugriff."),
            ("Direktversand", "Testmail direkt versenden.", "Versand funktioniert oder Fehler steht in Log/Mailhistorie."),
            ("Nextcloud-Link", "Nextcloud-Datei als Link versenden.", "Echter oeffentlicher Downloadlink wird erzeugt, kein reiner Ordnerlink."),
            ("Mailhistorie", "Mailhistorie oeffnen.", "Nur eigene Versandvorgaenge sichtbar."),
        ],
    ),
    (
        "K. Admin, Datenbank, Server und Update",
        [
            ("Backup", "Admin > Datenbank sichern.", "Backup wird erstellt oder Fehler klar angezeigt."),
            ("Migrationen", "Datenbankmigrationen pruefen.", "Offene/erledigte Migrationen werden angezeigt."),
            ("Reset Schutz", "Datenbank zuruecksetzen im Produktivbetrieb testen.", "Reset ist blockiert."),
            ("Reset Testbetrieb", "Im Testbetrieb Sicherheitswort eingeben.", "Button wird nur bei korrektem Text aktiv."),
            ("Routes Deployment", "Server-routes sichern/hochladen Dialog oeffnen.", "Backups werden angezeigt, Upload nur kontrolliert."),
            ("Backups bereinigen", "Nur alte routes-Backups bereinigen.", "Letzte Backups bleiben erhalten."),
            ("Wartungsmodus", "Wartungsmodus setzen/beenden.", "Status wird via API sichtbar."),
            ("Updatefreigabe", "ODV-Updatefreigabe Dialog oeffnen.", "Paket/Hash/Pfad koennen verwaltet werden."),
        ],
    ),
    (
        "L. Negativtests und Robustheit",
        [
            ("API getrennt", "API kurz nicht erreichbar machen oder falsche URL nutzen.", "ODV zeigt klare Meldung, kein Absturz."),
            ("Nextcloud offline", "Lokalen Nextcloud-Ordner nicht verfuegbar machen.", "ODV warnt und blockiert riskante Aktionen."),
            ("Fehlende Rechte", "Bearbeiter versucht Admin-Aktion.", "Aktion ist nicht sichtbar oder wird verweigert."),
            ("Datei geloescht", "Angezeigte Datei extern entfernen.", "ODV meldet Datei nicht gefunden, kein Traceback."),
            ("Datei umbenannt extern", "Datei extern umbenennen und Baum aktualisieren.", "Anzeige aktualisiert; Metadatenzuordnung bleibt nachvollziehbar oder wird klar als fehlend markiert."),
            ("Ungueltige Eingaben", "Leere/ungueltige Pflichtfelder testen.", "Formular blockiert mit klarer Meldung."),
            ("Sehr grosse PDF", "Grosse PDF auswaehlen.", "Hinweis/!!/Optimierungsempfehlung entsprechend Schwellwerten."),
            ("Logs pruefen", "Nach Testdurchlauf app.log/error.log ansehen.", "Keine unerwarteten Tracebacks; Fehler sind fachlich erklaert."),
        ],
    ),
]


def build() -> None:
    pdf = PdfTableBuilder()
    counter = 1
    for section_title, rows in SECTIONS:
        pdf.section(section_title)
        for area, step, expected in rows:
            pdf.row([f"{counter:03d}", area, step, expected, ""], shade=(counter % 2 == 0))
            counter += 1
    pdf.paragraph("Hinweis: Nach jedem Fehler bitte Screenshot, Uhrzeit, angemeldete Rolle, betroffene Datei und relevante Logzeilen notieren.")
    pdf.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
