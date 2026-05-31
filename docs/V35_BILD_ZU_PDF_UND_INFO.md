# v35 – Bilddateien in PDF umwandeln und Information/Rundmail vorbereiten

## Bilddateien in PDF umwandeln

### Dateien anzeigen

- Rechtsklick auf eine Bilddatei im Dateibaum.
- Menüpunkt **Als PDF speichern...** wählen.
- Speicherort/Dateiname auswählen.
- Die PDF erhält eine eigene Upload-ID, eine JSON-Sicherung und wird über die API als neuer Datensatz in MySQL gespeichert.
- Nach der Umwandlung fragt die Anwendung, ob die ursprüngliche Bilddatei gelöscht werden soll.

### Dateien bearbeiten

- Rechtsklick auf einen Admin-Datensatz mit Bilddatei.
- Menüpunkt **Bild in PDF umwandeln** wählen.
- Die PDF wird im selben Ordner erzeugt, Metadaten werden vom Bild übernommen.
- Neuer MySQL-Datensatz und JSON-Sicherung werden erzeugt.
- Danach fragt die Anwendung, ob die ursprüngliche Bilddatei gelöscht werden soll.

## Information / Rundmail vorbereiten

Unter **Admin > Information / Rundmail vorbereiten...** gibt es einen ersten einfachen Dialog.

Der Dialog kann aktuell:

- Empfänger manuell aufnehmen,
- Betreff erfassen,
- Dokument/Link auswählen,
- Standardtext erzeugen,
- E-Mail-Text in die Zwischenablage kopieren.

Noch nicht enthalten:

- E-Mail-Adressen in der zentralen Benutzerverwaltung,
- automatischer Versand,
- serverseitige Rundmail-Funktion,
- Nextcloud-Freigabelinks automatisch erzeugen.

Für eine spätere Produktivversion sollten E-Mail-Adressen in der Tabelle `users` ergänzt und der Versand serverseitig über die API abgewickelt werden.
