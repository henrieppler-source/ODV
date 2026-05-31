# Ortschronik-Uploader MVP v9

Lokaler Prototyp für Windows und macOS.

## Start

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Änderungen in v9

- Dateiansicht umgebaut: links Dateibaum, rechts Vorschau über den Metadaten.
- Metadaten werden in der Dateiansicht aus der JSON-Datei angezeigt.
- Metadaten sind nur bearbeitbar, wenn im Verzeichnis der Datei Schreibrecht besteht.
- Admin-Bearbeitung zeigt zusätzlich die vollständigen JSON-Daten inklusive Historie an.
- Beim Admin-Umbenennen/Verschieben wird der Dateiname automatisch normiert:
  - Datum/Zeitraum aus den Metadaten als Präfix, sonst Hochladedatum
  - Kleinschreibung
  - Leerzeichen werden zu `_`
  - `ä/ö/ü/ß` werden zu `ae/oe/ue/ss`
  - unzulässige Sonderzeichen werden bereinigt
  - bei vorhandener Zieldatei wird automatisch `_#1`, `_#2` usw. ergänzt
- Der in den Admin-Einstellungen festgelegte Metadatenordnername wird jetzt konsequent verwendet.

## Testversion

Die Superadmin-Testversion meldet automatisch an:

- Name: Henri Eppler
- Benutzername: henri.eppler
- Rolle: Superadmin
- Ort: Milz

## Version v19 API-Testbetrieb

Diese Version meldet Benutzer über die Ortschronik-API an und speichert neue Upload-Metadaten zusätzlich zur lokalen JSON-Sicherungsdatei in MySQL/MariaDB.

Standard-API-URL: `https://ortschronik.info/api`

Beim Start:
1. Benutzername und Passwort eingeben.
2. Die API liefert Name, Rolle und Ort des Benutzers.
3. Das Token wird lokal in der Konfiguration gespeichert und beim nächsten Start wiederverwendet.

Beim Upload:
- Datei wird weiterhin lokal in den Nextcloud-Sync-Ordner kopiert.
- JSON-Begleitdatei wird weiterhin im zentralen Metadatenordner gespeichert.
- Metadaten werden zusätzlich per `POST /api/documents` in MySQL gespeichert.
- Personenmarkierungen werden zusätzlich per `PUT /api/documents/{upload_id}/persons` gespeichert.

Hinweis: Benutzerverwaltung in der Oberfläche ist in dieser Version noch die alte lokale Verwaltung. Die API-Endpunkte dafür existieren bereits; die Oberfläche wird in einem Folgeschritt daran angebunden.


## v20

- Benutzerverwaltung in der Desktop-App ist jetzt vollständig an die Server-API/MySQL angebunden.
- Benutzerliste wird über GET /api/users geladen.
- Benutzeranlage läuft über POST /api/users.
- Benutzeränderung/Deaktivierung läuft über PUT /api/users/{id}.
- Lokale users.json wird für die zentrale Benutzerverwaltung nicht mehr verwendet.

## v21

- Schutz in der Benutzerverwaltung ergänzt: Der aktuell angemeldete Benutzer kann sich nicht mehr selbst über das Feld „Benutzer aktiv“ deaktivieren.
- Der Button „Benutzer deaktivieren“ bleibt ebenfalls gegen Selbst-Deaktivierung geschützt.

## Version v22 API-Datenfluss

Diese Version nutzt die Server-API für Dashboard, Admin-Dateiliste, Metadatenänderungen, Statusänderungen und Personenzuordnungen. JSON-Dateien werden weiterhin als Sicherung erzeugt und aktualisiert.
