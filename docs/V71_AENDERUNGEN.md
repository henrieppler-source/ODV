# Änderungen v71

Test-Updateversion auf Basis v70 Buildfix 1.

Zweck dieser Version:

- Prüfung des Komfort-Updaters mit einer tatsächlich neueren App-Version.
- `APP_VERSION` wurde von `v70` auf `v71` angehoben.
- `server/routes_v71.php` und `server/routes.php` melden `api_version = v71`.
- Komfort-Updater-Fix aus v70 Buildfix 1 bleibt enthalten.

Hinweis für den Test:

1. Diese Version klassisch bauen.
2. Den kompletten Inhalt von `dist\ODV` als ZIP bereitstellen, nicht nur `ODV.exe`.
3. In der Updatefreigabe `v71` und den ZIP-Dateinamen eintragen.
4. SHA256 nach dem ZIP-Erstellen neu berechnen.
