# v27 – Ordnerrechte und Ortsordner-Stammdaten

## Neu

- Standard-Zielordner beim Start: `01_ABLAGE_ORTSCHRONIK`, sofern Schreibrecht vorhanden.
- Eigene Rechteverwaltung nach Ordnergruppen:
  - `00_ORTSCHRONIK`
  - `01_ABLAGE_ORTSCHRONIK`
  - `02_AUSTAUSCH`
  - `05_ORGA_CHRONISTEN`
  - `06_UNSERE_ARBEITEN`
  - eigener Ortsordner
  - andere Ortsordner
- Je Bereich werden Lesen und Schreiben gepflegt.
- Benutzerverwaltung enthält nun den Abschnitt „Rechte / Hinweise“.
- Ortsordner-Stammdaten unter `Admin > Ortsordner-Stammdaten...`, z. B. `Milz -> 45_Milz`, `Römhild -> 50_Roemhild`.
- Dateiansicht nutzt Leserechte, Upload-/Zielordnerauswahl nutzt Schreibrechte.

## Server

Vor Nutzung auf dem Server ausführen/importieren:

- `sql/schema_v27_permissions.sql`

Dann `server/routes_v27.php` als `ortschronik-api/routes.php` hochladen.
