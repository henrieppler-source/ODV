# ODV v69 – Updateverwaltung über Nextcloud

Version v69 erweitert v68 um eine zentrale Updateprüfung und Updatebereitstellung über den lokalen Nextcloud-Syncordner.

## Enthalten

- `APP_VERSION = "v69"`
- `server/routes_v69.php`
- `server/routes.php` entspricht v69
- `sql/schema_v69_app_update.sql`
- `sql/reset_bewegungsdaten_v69.sql`
- `docs/V69_AENDERUNGEN.md`

## Updateverwaltung

Superadmins können unter **Admin → ODV-Updatefreigabe verwalten...** eine neue freigegebene Version hinterlegen:

- Version, z. B. `v70`
- Dateiname, z. B. `odv-v70-buildpaket.zip` oder `ODV.exe`
- Nextcloud-Relativpfad, Standard: `02_AUSTAUSCH/ODV_UPDATE/Windows`
- optionale SHA256-Prüfsumme
- optionales Pflichtupdate
- Release-Hinweise

Die App prüft beim Start und über **Hilfe → Nach ODV-Update suchen...**, ob eine neuere Version freigegeben ist. Die laufende EXE wird nicht überschrieben. Die neue Version wird aus dem lokalen Nextcloud-Updateordner nach `%LOCALAPPDATA%\ODV\versions\vXX` kopiert und ZIP-Dateien werden dort entpackt.

## Server

`server/routes_v69.php` muss als `ortschronik-api/routes.php` hochgeladen werden.

## Hinweis

Der Komfort-Updater, der die laufende Installation automatisch ersetzt, bleibt ein späterer Ausbauschritt. v69 stellt die neue Version sicher bereit und kann eine entpackte neue EXE starten.
