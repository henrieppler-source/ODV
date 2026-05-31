# ODV v79 – Menüstruktur und manuelle Sonderpunkte

## Schwerpunkt
v79 ordnet die Menüs neu und führt manuelle Sonderpunkte für Ortschronisten ein.

## Wesentliche Änderungen

- Neues Hauptmenü **Punkte**:
  - Mein Punktestand
  - Punkteübersicht
  - Manuelle Sonderpunkte vergeben
  - Übersicht manuelle Sonderpunkte
  - Punkteregeln verwalten
  - Punkte für vorhandene Dokumente neu berechnen
  - Punkte-Einstellungen
- Menü **Informationen** heißt jetzt **Mail**:
  - Rundmail erstellen
  - Verteiler verwalten
  - Versandhistorie
- Neues Menü **Übersichten**:
  - Dokumentzugriffe
  - Sitzungen und Geräte
  - Backup-Status
- Manuelle Sonderpunkte können ohne Dokumentbezug vergeben werden.
- Zeitaufwand in Stunden kann erfasst werden.
- Standardpunkte pro Stunde: 150, über Superadmin einstellbar.
- Wenn Zeitaufwand erfasst ist, wird ein Punktvorschlag automatisch berechnet.
- Punkte bleiben vor dem Speichern manuell änderbar.
- Eigene Tabelle `manual_special_points` für nachvollziehbare Sonderpunkte.

## Server
`server/routes_v79.php` als `ortschronik-api/routes.php` hochladen.

## SQL
Bei Bedarf importieren:

```sql
sql/schema_v79_menu_manual_points.sql
```

## Build

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Für Updatepakete immer den Inhalt von `dist\ODV` zippen, nicht nur `ODV.exe`.
