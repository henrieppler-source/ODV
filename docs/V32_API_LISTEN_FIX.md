# v32 API-Listen-Fix

Behebt HTTP 500 beim Laden der MySQL/API-Dokumentliste, insbesondere im Dialog zur Prüfung lokaler JSON-Sicherungsdateien.

Ursachenabsicherung:
- Rollen werden serverseitig case-insensitive geprüft.
- `str_contains` wurde durch `strpos` ersetzt.
- `GET /api/documents` ist robuster gegen Serverfehler und schreibt Details in `ortschronik-api/logs/api.log`.

Keine SQL-Migration erforderlich.
