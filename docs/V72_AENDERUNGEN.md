# Änderungen v72

## Konsolidierung

v72 ist der konsolidierte Produktivtest-Stand nach den v70/v71-Updater-Buildfixes.

## Komfort-Updater

- sichtbares Fortschrittsfenster „ODV wird aktualisiert“
- alte ODV-Instanz wird vor dem Kopieren gezielt beendet
- Einzelinstanz-Sperre verhindert doppelt gestartete ODV-Fenster
- neu gestartete ODV überspringt die Updateprüfung einmalig direkt nach dem Update
- Updatepaket wird vor der Installation auf Vollständigkeit geprüft

## Wartungsmodus

- Nach dem Aktivieren sieht auch der Superadmin sofort die eigentliche Warnmeldung.
- Die Warnung enthält Restzeit, Sperrzeitpunkt und den Hinweis, dass Superadmins zugriffsberechtigt bleiben.

## Technischer Updateordner

- `ODV_UPDATE` und alle Unterordner werden aus normalen Zielordner-/Ablage-/Dateibäumen ausgeblendet.
- Die Updateverwaltung kann den Ordner weiterhin intern verwenden.

## Mail-Historie

- Versandhistorie ist dokumentiert und bleibt über `Informationen > Versandhistorie...` erreichbar.
- Erfasst werden u. a. Zeitpunkt, Absender, Empfänger, Betreff, Versandart, Dokumente/Links und Fehlerstatus.

## Papierkorb / Gelöscht-Status

- Status `geloescht` ergänzt.
- Standard-Dokumentlisten blenden `geloescht` aus.
- Gelöschte Dokumente bleiben über Statusfilter nachvollziehbar und werden nicht hart entfernt.

## Server

- `server/routes_v72.php` als `ortschronik-api/routes.php` hochladen.
- App und API sollten beide v72 melden.
