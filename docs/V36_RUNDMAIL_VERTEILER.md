# v36 – Rundmail / E-Mail-Adressen / Verteiler

## Server
1. `sql/schema_v36_mail.sql` in phpMyAdmin importieren.
   Wenn die Spalte `users.email` bereits existiert, die `ALTER TABLE users ADD COLUMN email ...`-Zeile vorher entfernen/überspringen.
2. `ortschronik-api/routes.php` sichern.
3. `server/routes_v36.php` als neue `ortschronik-api/routes.php` hochladen.
4. `/api/status` testen.

## App
Neu:
- Benutzerverwaltung enthält Feld „E-Mail“.
- Menü `Informationen > Verteiler verwalten...`.
- Menü `Informationen > Rundmail erstellen...`.
- Empfänger können aus aktiven Benutzern mit E-Mail-Adresse, aus Verteilern und manuell ergänzt werden.
- Nachricht kann in die Zwischenablage kopiert oder im lokalen Mailprogramm geöffnet werden.

Hinweis: v36 verschickt noch nicht serverseitig per SMTP. Das folgt in einer späteren Version, sobald SMTP-Daten in der Server-.env stehen.
