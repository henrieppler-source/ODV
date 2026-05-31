# ODV v74 – Sitzungen, Geräte und Dokument-Bearbeitungssperren

Dieses Paket konsolidiert v73 und ergänzt Sicherheitsfunktionen für den Produktivtest.

## Installation / Build Windows

PowerShell im Projektordner öffnen:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Die Anwendung liegt danach unter:

```text
dist\ODV\ODV.exe
```

Für Updatepakete immer den kompletten Inhalt von `dist\ODV` zippen, nicht nur die EXE.

## Server

`server/routes_v74.php` nach `ortschronik-api/routes.php` hochladen.

SQL-Migration bei Bedarf in phpMyAdmin ausführen:

```text
sql/schema_v74_sessions_devices_locks.sql
```

Die API legt die neuen Tabellen zusätzlich defensiv selbst an, sofern der Datenbankbenutzer dazu berechtigt ist.

## Neue Funktionen

- Geräte-ID je lokaler Installation
- Geräteinformationen beim Login
- Mail an Superadmins bei Login von neuem Gerät
- Superadmin-Dialog „Sitzungen und Geräte...“
- Sitzung beenden
- Gerät sperren/freigeben
- Hinweis bei Mehrfachlogin
- Dokument-Bearbeitungssperre gegen parallele Metadatenänderungen

## Hinweis

Neue Geräte werden bewusst nicht blockiert. Der Login bleibt benutzerfreundlich möglich; Superadmins werden informiert und können auffällige Geräte sperren.
