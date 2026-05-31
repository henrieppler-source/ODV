# ODV v50 – Punktestand, Ranking und direkte Sonderpunkte

## Neu

- Alle angemeldeten Benutzer können unter `Auswertungen > Mein Punktestand...` ihren eigenen Punktestand sehen.
- Angezeigt werden Jahrespunkte, Rangposition, Anzahl der Teilnehmenden und die eigenen Punkteereignisse.
- Admins/Superadmins behalten die vollständige Beitragsauswertung.
- Im Reiter `Dateien bearbeiten` wird zum ausgewählten Dokument die Punktesumme angezeigt.
- Sonderpunkte können direkt im Reiter `Dateien bearbeiten` über `Sonderpunkte erfassen...` vergeben werden.
- Neuer API-Endpunkt: `GET /api/points/me?year=YYYY` für den eigenen Punktestand.

## Server

`server/routes_v50.php` als neue `ortschronik-api/routes.php` hochladen.

Eine zusätzliche SQL-Migration ist gegenüber v49 nicht erforderlich.
