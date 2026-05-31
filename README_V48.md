# ODV v48 – Beitrags- und Punkteverwaltung

Neue Funktionen:

- neue Metadatenfelder: Stichwörter, Transkription erstellt, Transkriptionsart, Transkriptionshinweis
- automatische Punkte für verwertbare Erschließungsarbeit, nicht für bloßes Hochladen
- Punkte gehen an den angemeldeten Bearbeiter der jeweiligen Leistung
- automatische Punkte bei Erstbefüllung wichtiger Felder: Beschreibung, Stichwörter, Quelle, Rechte, Archivsignatur, Datum, Ereignis, Transkription
- Personenpunkte bei Personenzuordnung
- Admin-Punkte für Übernahme sowie Umbenennen/Verschieben
- manuelle Sonderpunkte mit Begründung
- Punkteregeln je Kalenderjahr verwaltbar
- Beitragsauswertung mit CSV-Export

Server:

1. `sql/schema_v48_points.sql` in phpMyAdmin importieren.
2. `ortschronik-api/routes.php` sichern.
3. `server/routes_v48.php` als neue `ortschronik-api/routes.php` hochladen.

Wichtig: Bereits vergebene Punkte behalten den gespeicherten Wert. Änderungen an Punkteregeln gelten praktisch für zukünftige Punkteereignisse des jeweiligen Kalenderjahres.
