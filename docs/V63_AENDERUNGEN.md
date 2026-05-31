# ODV v63 – Verzeichnis-/Upload-Fix und Reset-SQL

## Behoben

- Die Zielordner- und Dateiansicht verwendet wieder konsequent das konfigurierte Nextcloud-Stammverzeichnis.
- Die App verhindert, dass der PyInstaller-/Programmordner (`_internal`, `PIL`, `pypdf`, `tk_data` usw.) als Nextcloud-Zielordner verwendet wird.
- Wenn kein gültiges Nextcloud-Stammverzeichnis gesetzt ist, erscheint eine klare Meldung statt einer falschen Ordnerliste.
- Der Upload-Fehler `pdo_code HY093` in `POST /api/documents` wurde behoben. Ursache war ein SQL-Platzhalter für `points_eligible`, der im INSERT nicht passend enthalten war.
- Upload meldet einen API-/MySQL-Fehler nun als Fehler, statt lokal kopierte Dateien als erfolgreich hochgeladen darzustellen.

## Mitgeliefert

- `server/routes_v63.php` als neue `ortschronik-api/routes.php`.
- `sql/reset_bewegungsdaten_v63.sql` zum Leeren der Dokument- und Punkte-Testdaten ohne Löschen von Stammdaten/Verwaltungsdaten.
