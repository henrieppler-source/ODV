# Ortschronisten-Datei-Verwaltung (ODV) v80

Build:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Nach dem Build den gesamten Ordner `dist\ODV` verteilen oder als Update-ZIP packen.

Server:

`server/routes_v81.php` als `ortschronik-api/routes.php` hochladen.

SQL bei Bedarf importieren:

`sql/schema_v80_ui_sources_search_mailrules.sql`

Reset-Datei:

`sql/reset_bewegungsdaten_v81.sql`

## v82

- Upload-Metadatenmaske an Dateien anzeigen/bearbeiten angeglichen.
- Technische Upload-Felder sichtbar und passend ausgegraut.
- Layout der Verzeichnis-/Baum-Zeile verbessert.
