# ODV v77 – Dateiansicht, Suche, Dokumentstatus und Normierung

## Inhalt

- `APP_VERSION = "v77"`
- `server/routes_v77.php`
- `server/routes.php` meldet `api_version = v77`
- `sql/schema_v77_fileview_status_search.sql`
- `sql/reset_bewegungsdaten_v77.sql`

## Änderungen

- **Dateien anzeigen**: Baumlogik für Bearbeiter/Admins nochmals vereinheitlicht. Bei Leserecht auf `00_ORTSCHRONIK` wird der komplette physische Unterbaum rekursiv wie beim Superadmin angezeigt.
- **Suche/Filter in Dateien anzeigen**: Dateinamenfilter mit normierter Suche; Groß-/Kleinschreibung und Umlaute/Sonderzeichen werden für die Suche vereinfacht. Der Baum zeigt Trefferdateien und deren Ordner.
- **Systemdateien ausgeblendet**: `desktop.ini`, `Thumbs.db`, `.DS_Store`, temporäre Dateien und `ODV_UPDATE` werden in normalen Bäumen ausgeblendet.
- **Dateinamen-Normierung**: Der Ort wird nicht mehrfach in den Dateinamen geschrieben; vorhandene Mehrfachsegmente wie `milz_milz` werden reduziert.
- **Dateien bearbeiten**: `Neuer Status` heißt jetzt `Dokumentstatus`.
- **Punktebereich** in „Dateien bearbeiten“ ist optisch als eigener Block abgesetzt.
- **Archiv-/Papierkorb-Ordner**: Status `archiviert`, `abgelehnt` und `geloescht` verschieben Dateien nach `01_ABLAGE_ORTSCHRONIK/_ARCHIV/ARCHIVIERT`, `.../ABGELEHNT` bzw. `.../GELOESCHT`.
- **Archivieren** ist nur erlaubt, wenn die Datei aus `01_ABLAGE_ORTSCHRONIK` stammt.
- Reaktivierung über Status `erfasst` versucht, die Datei an den ursprünglichen Pfad zurückzuschieben.

## Server

`server/routes_v77.php` wie üblich als `ortschronik-api/routes.php` hochladen.

## Build

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```
