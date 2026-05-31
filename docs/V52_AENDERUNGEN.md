# ODV v52 – Punkte nachträglich für angezeigte Bearbeitungsliste ermitteln

## Neu

- In `Dateien bearbeiten` gibt es im Bereich `Admin-Aktionen` den Button:
  - `Punkte für angezeigte Liste nachtragen...`
- Die Funktion berechnet fehlende automatische Punkte für alle aktuell in der Admin-Liste angezeigten Dateien.
- Bereits vorhandene Punkte werden nicht doppelt gespeichert.
- Die serverseitige Berechnung berücksichtigt weiterhin die Ordnerregel:
  - Punkte nur für ursprünglich punkteberechtigte Dateien aus `01_ABLAGE_ORTSCHRONIK` oder `06_UNSERE_ARBEITEN` bzw. kompatiblen Varianten.
- Für nachträgliche Berechnung wird versucht, die Punkte dem ursprünglichen Bearbeiter zuzuordnen:
  - Wenn ein Feld laut Historie erstmals durch einen Admin/Bearbeiter gefüllt wurde, gehen die Punkte an diesen Bearbeiter.
  - Wenn keine Feld-Historie vorhanden ist, wird als Fallback der ursprüngliche Uploader verwendet.
- Doppelte Punkte je Dokument/Feld/Regel werden bei der Nachberechnung verhindert.

## Server

Neue Route:

- `POST /api/points/recalculate-bulk`

Die bestehende Einzelroute wurde ebenfalls auf die neue rückwirkende Berechnung umgestellt:

- `POST /api/documents/{upload_id}/points/recalculate`

## SQL

Keine zusätzliche SQL-Migration gegenüber v51 erforderlich, sofern die Tabellen aus v48/v49/v51 bereits eingespielt wurden.
