# ODV v67 – Stammdatenblatt, Zugriffsprotokoll und Download

Version v67 erweitert v66 um praktische Auswertungs- und Dateiaktionen.

## Änderungen

- `APP_VERSION = "v67"`.
- `server/routes_v67.php` und `server/routes.php` entsprechen v67.
- Störende Überlagerung im Metadatenbereich von „Dateien anzeigen“ beseitigt.
- Rechtsklick auf Dateien in „Dateien anzeigen“ und „Dateien bearbeiten“:
  - Datei öffnen
  - Download / Kopie speichern unter...
  - bei Bildern mit Personen: Stammdatenblatt als PDF speichern
- Download/Kopie speichert die Datei in ein frei wählbares Zielverzeichnis, standardmäßig Downloads.
- Öffnen und Download/Kopie von bereits in ODV erfassten Dokumenten werden über die API in `document_history` protokolliert.
- Auswertungen → Dokumentzugriffe zeigt Öffnen/Download mit Benutzer, Zeit, Datei und Details.
- Für Bilder mit Personenzuordnung kann ein A4-Stammdatenblatt als PDF erzeugt werden:
  - obere Hälfte: Bild mit Nummern
  - untere Hälfte: Personenliste und wichtigste Dateidaten

## Server

`server/routes_v67.php` muss als `ortschronik-api/routes.php` hochgeladen werden.

Neue API-Endpunkte:

- `POST /api/documents/{upload_id}/access-log`
- `GET /api/document-access-log`

Die Auswertung nutzt die bestehende Tabelle `document_history`; ein separates Schema-Update ist nicht erforderlich.
