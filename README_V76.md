# ODV v76 – Dateiansicht, Metadatenrechte und Drag & Drop

## Inhalt

- `APP_VERSION = "v76"`
- `server/routes_v76.php`
- `server/routes.php` meldet `api_version = v76`
- `sql/schema_v76_dragdrop_fileview.sql`
- `sql/reset_bewegungsdaten_v76.sql`

## Änderungen

- Dateien anzeigen: Baumaufbau für Bearbeiter/Admins nochmals vereinheitlicht. ODV-Hauptordner werden auch erkannt, wenn sie unter einem Sammelordner wie `Ortschronisten_Gemeinsam` liegen.
- Leserecht auf `00_ORTSCHRONIK` zeigt den kompletten physischen Unterbaum rekursiv, wie beim Superadmin.
- Tiefe Ordner wie `00_ORTSCHRONIK/90_Archive_und_Quellen/90-10_Zeitungen/Freies_Wort/...` sollen auch für Bearbeiter/Admins sichtbar und aufklappbar sein.
- `ODV_UPDATE` bleibt aus normalen Zielordner- und Dateibäumen ausgeblendet.
- Metadatenrechte in Dateien anzeigen: Admin/Superadmin dürfen bearbeiten; Bearbeiter dürfen bearbeiten bei Ordnerschreibrecht oder eigener erfasster Datei. Fehlt „Erfasst von“, reicht Ordnerschreibrecht.
- Dateien hochladen: Drag & Drop einer Datei aus dem Explorer in den Upload-Reiter möglich. Drag & Drop wählt nur die Datei aus; der Upload erfolgt erst nach Klick auf „Datei hochladen“.

## Server

`server/routes_v76.php` wie üblich als `ortschronik-api/routes.php` hochladen.

## Build

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```
