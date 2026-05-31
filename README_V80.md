# Ortschronisten-Datei-Verwaltung (ODV) v80

Buildpaket mit zwei gezielten Verbesserungen:

1. Lokales Speichern von Fenstergrößen und Fensterpositionen.
2. Aktualisierung der ODV-Version in „Sitzungen und Geräte“ nach Start/Login/API-Statusprüfung.

## Build Windows

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Die gebaute Anwendung liegt anschließend unter:

```text
dist\ODV\ODV.exe
```

Für die Verteilung immer den gesamten Ordner `dist\ODV` verwenden.

## Server

`server/routes_v80.php` als `ortschronik-api/routes.php` auf den Server hochladen.

## SQL

`sql/schema_v80_ui_session_state.sql` enthält nur Hinweise; die benötigten Sitzungs-/Gerätetabellen stammen aus v74.
