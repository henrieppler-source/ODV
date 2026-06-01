# Checkliste Testbetrieb

## Server

- HTTPS aktiv.
- `.env` nicht öffentlich abrufbar.
- `api/create-superadmin.php` gelöscht.
- `ortschronik-api/create_superadmin.php` gelöscht oder sicher entfernt.
- `/api/status` funktioniert.
- `/api/db-test` funktioniert nur noch mit Superadmin-Token.
- `ortschronik-api/logs` existiert.
- Keine Passwörter oder Tokens in Logdateien.

## Benutzer

Mindestens drei Testbenutzer anlegen:

1. Superadmin
   - Benutzerverwaltung
   - Admin-Einstellungen
   - Dateien bearbeiten

2. Admin
   - Dateien bearbeiten
   - keine Benutzerverwaltung

3. Ortschronist
   - Dateien hochladen
   - Dateien anzeigen
   - keine Dateien-bearbeiten-Ansicht
   - keine Benutzerverwaltung

## Nextcloud

- Nextcloud-Stammverzeichnis lokal eingebunden.
- Zentraler Metadatenordner vorhanden: `.ortschronik_metadaten`.
- Admin-Bearbeitungsordner vorhanden, z. B.:
  - `01_ABLAGE_ORTSCHRONIK`
  - `06_ARBEIT_DER_ORTSCHRONISTEN`
- Schreibrechte je Rolle praktisch testen.

## Datenbank

- Testdaten vor Start bereinigen oder klar als Testdaten belassen.
- Statuswerte vereinheitlichen:
  - `hochgeladen`
  - `rueckfrage`
  - `geprueft`
  - `uebernommen`
  - `archiviert`
- Alte Tokens regelmäßig löschen, siehe `server/sql/token_cleanup.sql`.
