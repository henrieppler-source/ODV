# v31 – JSON-Sicherungen und Produktivmodus

## Änderung

Im API-/Produktivmodus zeigt der Reiter **Dateien bearbeiten** nur noch Dokumente aus MySQL/API an.

Lokale JSON-Dateien im Ordner `.ortschronik_metadaten` bleiben als Sicherung erhalten, werden aber nicht mehr automatisch als aktive Admin-Bearbeitungsliste eingemischt.

## Neue Funktion

Unter:

`Admin > Lokale Sicherungsdateien prüfen/bereinigen...`

kann der Superadmin lokale JSON-Sicherungen gegen die MySQL/API-Dokumentliste prüfen.

Angezeigt werden:

- JSON-Datei ist in MySQL vorhanden
- JSON-Datei ist verwaist, also ohne passenden MySQL-Datensatz

Verwaiste Sicherungen können:

- in `_verwaiste_sicherungen` verschoben werden
- endgültig gelöscht werden

Empfehlung: Vor dem Löschen erst verschieben.

## Server

Keine neue SQL-Migration erforderlich, wenn v27, v29 und v30 bereits eingespielt sind.
