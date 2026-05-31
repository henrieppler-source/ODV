# ODV v64

Schwerpunkt dieser Version: „Dateien anzeigen“ zeigt physisch vorhandene Dateien rekursiv an, auch wenn sie noch nicht in ODV/MySQL/JSON erfasst sind.

## Wichtig für den Server

Bitte serverseitig `server/routes_v64.php` als produktive `ortschronik-api/routes.php` hochladen.

Die beiliegende `server/routes.php` entspricht ebenfalls v64.

## Geändert in v64

- „Dateien anzeigen“ durchsucht den ausgewählten Ordner ohne künstliche Tiefenbegrenzung rekursiv.
- Dateien ohne ODV-Metadaten werden im Baum mit normalem Dateinamen angezeigt; der Hinweis steht im Bereich Metadaten/Historie.
- Doppelklick öffnet auch solche Dateien weiterhin mit dem Standardprogramm.
- Im Metadaten-/Historie-Bereich bleibt bei fehlenden Metadaten der Hinweis: „Keine JSON-Metadaten vorhanden. Beim Speichern werden neue Metadaten angelegt.“
- Beim Speichern von Metadaten zu einer physisch vorhandenen Datei wird diese als ODV-Dokument in MySQL angelegt, ohne die Datei erneut zu kopieren.
- Punkte werden nur für Dateien in `00_ORTSCHRONIK`, `01_ABLAGE_ORTSCHRONIK` oder `06_ARBEIT_DER_ORTSCHRONISTEN` vergeben.
- Sonderpunkte:
  - „Kinder wie die Zeit vergeht“: neu über ODV 100 Punkte, nachträglich erfasste vorhandene Datei 20 Punkte.
  - Jahresblätter: neu über ODV 50 Punkte, nachträglich erfasste vorhandene Datei 10 Punkte.

## Reset-SQL

Optional vorhanden:

```text
sql/reset_bewegungsdaten_v64.sql
```

Der Reset löscht nur Bewegungsdaten, nicht Benutzer, Rollen/Rechte, Ortsordner, Punkteregeln, Verteiler, Systemeinstellungen oder Nextcloud-Dateien.

## Build-Hinweis / Buildfix

Falls Windows beim Installieren von `pyinstaller-hooks-contrib` mit einem Long-Path-Fehler abbricht,
wurde das Buildpaket angepasst:

- `pyinstaller` ist auf `6.11.1` gepinnt.
- `pyinstaller-hooks-contrib` ist auf `2024.10` gepinnt.
- Der Build ruft PyInstaller ueber `python -m PyInstaller` auf.

Wenn trotzdem ein Long-Path-Fehler erscheint, Projektordner kurz halten, z. B. `C:\ODV64`,
oder Windows Long Path Support aktivieren.
