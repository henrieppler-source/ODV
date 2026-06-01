# ODV-Stand und Arbeitsvereinbarungen

Stand: v119

Diese Datei sammelt die wichtigsten Vereinbarungen und den aktuellen Arbeitsstand für die Weiterentwicklung der ODV-Anwendung. Sie dient als kompakte Wiederaufnahmehilfe für spätere Sitzungen.

## Aktueller Stand

- Aktuelle App-Version: `v119`
- README-Version: `v119`
- Bearbeiter-Handbuch: `Handbuch.md`
- Admin-Handbuch: `Admin-Handbuch.md`
- Zentrale App-Konstanten: `app/app_constants.py`
- Haupt-Launcher: `app/main.py`
- Versionshistorie: `README.md`

## Grundregeln für die Weiterentwicklung

- Alle fachlichen, technischen und sichtbaren Änderungen werden in der `README.md` unter `Versionshistorie` dokumentiert.
- Bei einer neuen Version werden alle Versionsbezeichnungen im Projekt passend angehoben.
- Korrekturen innerhalb einer bestehenden Version werden direkt bei dieser Version in der `README.md` ergänzt.
- Bearbeiterrelevante Änderungen werden zusätzlich in `Handbuch.md` dokumentiert.
- Admin-, Betriebs-, Server-, Datenbank- und Update-Themen werden zusätzlich in `Admin-Handbuch.md` dokumentiert.
- Die Handbücher und die README werden bei Änderungen immer zusammen gedacht, damit die Dokumentation nicht auseinanderläuft.
- Die aktuelle Versionshistorie in der `README.md` muss immer zum Code- und Handbuchstand passen.

## Wiederaufnahme bei Fortsetzung

- Bei einer neuen Sitzung zuerst den tatsächlichen Arbeitsstand prüfen.
- Relevante Dateien lesen, bevor Änderungen umgesetzt werden.
- Wenn nötig den technischen und fachlichen Stand aus `README.md`, `Handbuch.md` und `Admin-Handbuch.md` ableiten.
- Vor Änderungen auf vorhandene Git-Änderungen achten und fremde Änderungen nicht zurücksetzen.
- Bei unklaren Versionen oder widersprüchlichen Ständen zuerst den echten Code-Stand prüfen.

## Wichtige Projektregeln

- Vor Änderungen `git status --short` prüfen.
- Änderungen gezielt und nachvollziehbar umsetzen.
- Danach sinnvoll testen, soweit es die Änderung betrifft.
- Keine vorhandenen Änderungen im Workspace überschreiben oder unbedacht zurücksetzen.
- Wenn ein Commit gewünscht ist und der Nutzer sinngemäß oder exakt `OK läuft` schreibt, den aktuellen sinnvollen Arbeitsstand prüfen und committen.

## Dokumentation und Pflege

- Die `README.md` ist die zentrale Quelle für Versionsstand und Historie.
- `Handbuch.md` beschreibt die Arbeit aus Sicht von Bearbeiterinnen und Bearbeitern.
- `Admin-Handbuch.md` beschreibt Betrieb, Administration und technische Abläufe.
- Neue Funktionen sollen nicht nur implementiert, sondern auch in der passenden Dokumentation beschrieben werden.
- Die Dokumentation soll sprachlich und fachlich konsistent bleiben.

## Hinweise für künftige Versionen

- Bei jeder neuen App-Version müssen mindestens folgende Stellen geprüft werden:
  - `app/app_constants.py`
  - `server/routes.php`
  - `README.md`
  - `Handbuch.md`
  - `Admin-Handbuch.md`
- Wenn sich nur ein kleiner Teil ändert, trotzdem die betroffene Versionsbeschreibung aktualisieren.
- Wenn sich die Struktur von Modulen ändert, den neuen Zuschnitt kurz dokumentieren.
- Wenn sichtbare Bedienung, Statuslogik, Punkte, Updateabläufe, Serverbetrieb oder Admin-Menüs betroffen sind, die Änderung in den Handbüchern mitführen.
- Der Datenbank-Reset ist ein Bewegungsdaten-Reset: Dokumente, Historie, Personenmarkierungen, Punkte und manuelle Sonderpunkte werden geleert; Stammdaten wie Benutzer, Rechte, Orte, Punkteregeln, Verteiler und Systemeinstellungen bleiben erhalten.
- Bewegungsdaten-Reset darf nur im Testbetrieb möglich sein; der Produktivbetrieb muss serverseitig gegen Reset geschützt bleiben.
- Server-Backups sollen aufräumbar bleiben; Standardregel ist, pro Serverdatei nur die letzten drei Sicherungskopien aufzubewahren.
- API-Token und OpenAI-API-Schlüssel werden lokal verschlüsselt gespeichert und nicht mehr im Klartext in der Konfiguration abgelegt.
- `server/routes.php` wird schrittweise modularisiert; der Admin-/Backup-/Wartungsblock liegt jetzt bereits in `server/routes_admin_endpoints.php`.
- Die Mail-Verteiler-Routen liegen jetzt in `server/routes_mail_groups.php`.
- Das FTP-Deployment nimmt `routes*.php`-Dateien im Serverordner jetzt automatisch mit.

## Kurzform für die nächste Sitzung

Wir machen im ODV-Projekt weiter:

- Arbeitsordner: `C:\ODV\Entwicklung`
- Erst `git status --short` prüfen
- Dann relevante Dateien lesen
- Änderungen gezielt umsetzen
- README, Handbuch und Admin-Handbuch passend mitpflegen
- Versionsstand und Entwicklung in der `README.md` sauber dokumentieren
- Vorhandene Änderungen nicht zurücksetzen oder überschreiben
