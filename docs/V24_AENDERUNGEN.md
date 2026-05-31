# v24 – Benutzerwechsel und Zielordner-Filter

Änderungen:

- Beim Benutzerwechsel wird der Ort im Upload-Formular sofort aus dem aktuell angemeldeten API-Benutzer übernommen.
- Die frühere lokale `users.json` überschreibt die API-Benutzerdaten nicht mehr.
- Die Zielordnerliste für Ortschronisten wird zusätzlich fachlich gefiltert.

Warum zusätzlicher Filter?

Der lokale Schreibtest ist bei Nextcloud Desktop Client nicht immer zuverlässig: Windows kann lokal einen Schreibtest erlauben, obwohl Nextcloud serverseitig später wegen fehlender Rechte ablehnt. Deshalb werden bei Ortschronisten nur noch Zielordner angezeigt, die fachlich plausibel sind:

- `01_ABLAGE_ORTSCHRONIK`
- `02_AUSTAUSCH`
- `06_UNSERE_ARBEITEN`
- `06_UNSERE ARBEITEN`
- `06_ARBEIT_DER_ORTSCHRONISTEN`
- Ortsordner passend zum Ort des Benutzers, z. B. `50_Roemhild` bei Ort `Römhild`/`Roemhild`

Admin und Superadmin sehen weiterhin alle lokal beschreibbaren Ordner.
