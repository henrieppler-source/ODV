# V68 Änderungen

## Wartungsmodus / Datenbanksperre

- Nur Superadmins können den Wartungsmodus steuern.
- Die Vorlaufzeit wird frei in Minuten eingegeben.
- Auch Superadmins sehen Warn- und Statushinweise.
- Superadmins bleiben trotz aktiver Sperre arbeitsfähig.
- Admins und Ortschronisten werden bei aktivem Wartungsmodus durch die API blockiert.
- Neue Logins von Admins und Ortschronisten werden während aktiver Wartung abgewiesen.

## Datenbanksicherung

- Neue Superadmin-Funktion **Datenbank sichern...**.
- Sicherung erfolgt serverseitig als komprimierte `.sql.gz`.
- Neue Funktion **Backup-Status anzeigen...**.
- Warnung, wenn die letzte bekannte Sicherung älter als 48 Stunden ist oder keine Sicherung gefunden wurde.

## Systemprüfung beim Start

- Start-/Infofenster bleibt länger sichtbar.
- Nach Anmeldung erscheint eine kurze Systemprüfung:
  - API erreichbar
  - API-/Server-Version passend
  - Nextcloud-Stammverzeichnis vorhanden
  - lokaler Pfad erreichbar
  - Benutzer/Token gültig
  - Wartungsmodus geplant oder aktiv
  - Backup-Status für Superadmins

## API

- `/api/status` liefert `api_version` und Wartungsstatus.
- Neue Endpunkte:
  - `GET /api/admin/maintenance`
  - `POST /api/admin/maintenance`
  - `POST /api/admin/backup`
  - `GET /api/admin/backup-status`

## Vorgemerkt für spätere Version

- ODV-Updateverwaltung über Nextcloud mit Updateordner, Versionseintrag in MySQL/API, Prüfsumme und optionalem Pflichtupdate.
- Komfortabler Updater mit separater `ODV_Updater.exe`.
