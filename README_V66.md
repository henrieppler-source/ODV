# ODV v66 – Erfasst-von in Dateiansicht und Rundmail-Linkautomatik

Version v66 baut auf v65 auf.

## Änderungen

- In **Dateien anzeigen** ist das Feld **Erfasst von** für Admins wie in **Dateien bearbeiten** als Auswahlliste änderbar.
- Änderungen an **Erfasst von** werden über die API gespeichert.
- Automatische Punkte werden serverseitig auf den neu zugeordneten Benutzer übertragen.
- Bei neu erfassten vorhandenen Dateien kann der erfassende/zugeordnete Benutzer direkt beim Anlegen gesetzt werden.
- Beim Rundmail-Direktversand mit Versandart **Nextcloud-Downloadlink versenden** werden fehlende Downloadlinks automatisch erzeugt.
- Der Button **Downloadlinks erzeugen** bleibt als Vorschau-/Prüffunktion erhalten.

## Server

`server/routes_v66.php` nach `ortschronik-api/routes.php` hochladen.
