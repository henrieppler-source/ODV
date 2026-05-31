# ODV v68 – Wartungsmodus, Datenbanksicherung und Systemprüfung

Version v68 erweitert v67 um Betriebs- und Sicherheitsfunktionen für den API/MySQL-Betrieb.

## Enthalten

- `APP_VERSION = "v68"`
- `server/routes_v68.php`
- `server/routes.php` entspricht v68
- `sql/schema_v68_maintenance_backup.sql`
- `sql/reset_bewegungsdaten_v68.sql`

## Wesentliche Änderungen

- Superadmin-Menü **Datenbank sichern...** erzeugt serverseitig eine komprimierte SQL-Sicherung.
- Superadmin-Menü **Backup-Status anzeigen...** zeigt Zeitpunkt, Datei, Größe und Warnung bei Sicherungen älter als 48 Stunden.
- Superadmin-Menü **Wartungsmodus / Datenbanksperre...** mit frei wählbarer Vorlaufzeit in Minuten.
- Auch Superadmins erhalten Warn-/Statushinweise, bleiben aber zugriffsberechtigt.
- Admins und Ortschronisten werden bei aktivem Wartungsmodus blockiert; neue Logins werden dann abgewiesen.
- `/api/status` liefert `api_version`, Zeit und Wartungsstatus.
- Die App prüft beim Start API-Erreichbarkeit, API-Version, Nextcloud-Stammverzeichnis, Token und Wartungsstatus.
- Startfenster/Systemprüfung bleibt länger sichtbar.
- Statusleiste weist auf abweichende Server-/App-Versionen hin.

## Server

`server/routes_v68.php` muss als `ortschronik-api/routes.php` hochgeladen werden.

Die Datenbanksicherung wird standardmäßig serverseitig unter einem Ordner `odv_backup/backups` neben dem API-Verzeichnis abgelegt, sofern beschreibbar. Dieser Ordner sollte zusätzlich per Verzeichnisschutz beziehungsweise `.htaccess` abgesichert werden.

## Hinweis zur Rücksicherung

Die Rücksicherung bleibt vorerst bewusst manuell über KAS/phpMyAdmin dokumentiert. Ein Restore-Knopf in der App ist absichtlich noch nicht enthalten.
