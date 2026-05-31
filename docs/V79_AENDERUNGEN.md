# V79 Änderungen

## Menüstruktur

Die Menüstruktur wurde fachlich neu geordnet:

- **Admin** enthält Verwaltung und Betrieb.
- **Punkte** bündelt Punktefunktionen.
- **Mail** ersetzt das frühere Menü „Informationen“ und enthält Versandhistorie.
- **Übersichten** enthält Betriebs-/Auswertungsübersichten wie Dokumentzugriffe, Sitzungen/Geräte und Backup-Status.

## Manuelle Sonderpunkte

Für Tätigkeiten außerhalb einzelner Dokumente gibt es nun einen eigenen Bereich:

**Punkte → Manuelle Sonderpunkte vergeben...**

Erfasst werden:

- Ortschronist
- Tätigkeit / Regel
- Datum der Tätigkeit
- Zeitaufwand in Stunden
- Punkte
- Beschreibung / Begründung
- Bemerkung / Beleg
- vergebender Admin

Wenn ein Zeitaufwand angegeben wird, berechnet ODV mit dem hinterlegten Stundenfaktor automatisch einen Punktvorschlag. Der Vorschlag bleibt manuell änderbar.

## Punkte-Einstellungen

Superadmins können unter **Punkte → Punkte-Einstellungen...** den Faktor für manuelle Sonderpunkte festlegen. Standard ist:

```text
150 Punkte pro Stunde
```

## Übersicht manuelle Sonderpunkte

Admins und Superadmins können unter **Punkte → Übersicht manuelle Sonderpunkte...** nachvollziehen:

- welcher Admin
- welchem Ortschronisten
- für welche Tätigkeit
- mit welchem Zeitaufwand
- wie viele Punkte vergeben hat.

## Neue Datenbanktabelle

```sql
manual_special_points
```

Die automatischen Dokumentpunkte bleiben in `contribution_points`. Manuelle Sonderpunkte ohne Dokumentbezug werden getrennt gespeichert.
