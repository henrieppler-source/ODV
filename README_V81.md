# Ortschronisten-Datei-Verwaltung (ODV) v81

Buildfix/Fachversion v81 auf Basis von v80.

## Schwerpunkt

Fenstergrößen und Fensterpositionen werden zuverlässig lokal gespeichert und beim nächsten Öffnen wiederhergestellt.

## Server

`server/routes_v81.php` als `ortschronik-api/routes.php` hochladen.

## SQL

Keine Datenbankänderung erforderlich. `sql/schema_v81_ui_window_geometry_fix.sql` enthält nur den Hinweis.
