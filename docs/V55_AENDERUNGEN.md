# ODV v55 – Punkte-Nachberechnung robuster

## Änderungen

- Die API-Route `POST /api/points/recalculate-bulk` ist jetzt vollständig in Fehlerbehandlung gekapselt.
- Wenn SQL-Migrationen für die Punkteverwaltung fehlen, wird eine konkrete Meldung zurückgegeben.
- Fehler werden in `ortschronik-api/logs/api.log` protokolliert.
- Personenpunkte werden defensiv berechnet, auch wenn optionale Spalten in älteren Tabellenständen fehlen.
- Zusätzliches SQL-Sicherheitsupdate `sql/schema_v55_points_safety.sql` ergänzt fehlende Spalten und berechnet `points_eligible` robuster nach.

## Server

Bitte `server/routes_v55.php` als neue `ortschronik-api/routes.php` hochladen.

## SQL

Bitte bei bestehender Punkteverwaltung zusätzlich `sql/schema_v55_points_safety.sql` importieren.
