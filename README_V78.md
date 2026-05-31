# Ortschronisten-Datei-Verwaltung (ODV) v79

Build:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Nach dem Build den gesamten Ordner `dist\ODV` verteilen oder als Update-ZIP packen.

Server:

`server/routes_v79.php` als `ortschronik-api/routes.php` hochladen.

SQL bei Bedarf importieren:

`sql/schema_v79_ui_sources_search_mailrules.sql`

Reset-Datei:

`sql/reset_bewegungsdaten_v79.sql`
