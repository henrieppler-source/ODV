# ODV v72 – konsolidierter Produktivtest-Stand

Diese Version konsolidiert die funktionierenden v70/v71-Updater-Fixes und ergänzt die offenen Bedien- und Betriebsfunktionen für den Produktivtest.

## Enthalten

- `APP_VERSION = "v72"`
- `server/routes_v72.php` und `server/routes.php` melden `api_version = v72`
- Komfort-Updater mit sichtbarem Fortschrittsfenster, Einzelinstanz-Sperre und Schutz gegen Update-Endlosschleifen
- verbesserte Wartungsmodus-Warnung für Superadmins direkt nach Aktivierung
- `ODV_UPDATE` wird in normalen Zielordner- und Dateibaum-Auswahlen ausgeblendet
- Mail-Historie bleibt über **Informationen > Versandhistorie...** auswertbar
- Papierkorb-Logik: Status `geloescht` statt hartem Löschen; Standardlisten blenden gelöschte Dokumente aus
- Dokumentation zur Updatefreigabe für Superadmins ergänzt

## Server

`server/routes_v72.php` wie gewohnt als `ortschronik-api/routes.php` hochladen.

## Build

Unter Windows:

```powershell
.\build_windows.ps1
```

Für Verteilung und Updatepakete immer den gesamten Ordner `dist\ODV` verwenden bzw. als ZIP bereitstellen, nicht nur `ODV.exe`.
