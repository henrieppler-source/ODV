# Änderungen v75

## Dateiansicht

Die Dateiansicht wurde für Bearbeiter/Ortschronisten und Admins korrigiert. Leserecht auf `00_ORTSCHRONIK` gilt in „Dateien anzeigen“ jetzt konsequent für alle darunterliegenden Unterordner. Physisch vorhandene Dateien und tiefe Ordnerstrukturen werden rekursiv angezeigt.

## Metadatenrechte

In „Dateien anzeigen“ können Metadaten nur geändert werden, wenn fachlich eine Berechtigung besteht:

1. Schreibrecht auf den Ordner,
2. eigene bereits erfasste Datei,
3. Admin/Superadmin.

Fehlt bei einem bereits erfassten Dokument der Erfasser („Erfasst von“), ist die Bearbeitung nur durch Admin/Superadmin möglich.

## Technische Systemordner

`ODV_UPDATE` bleibt weiterhin aus normalen Dateibäumen und Zielordnerauswahlen ausgeblendet.
