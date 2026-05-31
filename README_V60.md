# ODV v60 – Reset / Mailhistorie / Upload-Layout

## Änderungen

- Upload-Reiter kompakter zweispaltig angeordnet, ähnlich wie „Dateien bearbeiten“.
- Superadmin-Menüpunkt `Admin > Datenbank zurücksetzen...` ergänzt.
  - Löscht nur Bewegungs-/Testdaten: Dokumente, Personenmarkierungen, Dokumenthistorie, Punkte/Sonderpunkte und optional Mail-Historie.
  - Löscht nicht: Benutzer, Rollen, Rechte, Ortsordner, Punkteregeln, Verteiler und Systemeinstellungen.
  - Nextcloud-Dateien werden nicht gelöscht.
- Beim Import vorhandener Dateien kann der Superadmin auswählen, von wem die Dateien sind.
- Mail-Versandhistorie ergänzt:
  - Pro Empfänger wird gespeichert, welche Rundmail versendet wurde.
  - Menü `Informationen > Versandhistorie...` für Admin/Superadmin.

## Server

1. Optional/empfohlen: `sql/schema_v60_mail_history.sql` importieren.
2. `server/routes_v60.php` als `ortschronik-api/routes.php` hochladen.

Die Tabelle `mail_history` wird durch die Route bei Bedarf auch automatisch angelegt.
