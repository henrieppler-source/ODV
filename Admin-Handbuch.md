# ODV-Admin-Handbuch

Stand: v111

Dieses Handbuch beschreibt Administration, Betrieb und technische Abläufe der Ortschronisten-Datei-Verwaltung (ODV). Es richtet sich an Admins und Superadmins.

# Inhalt

- [1. Überblick](#1-uberblick)
- [2. Systemarchitektur](#2-systemarchitektur)
- [3. Rollen, Rechte und Benutzerverwaltung](#3-rollen-rechte-und-benutzerverwaltung)
- [4. Stammdatenverwaltung](#4-stammdatenverwaltung)
- [5. Datei- und Metadatenverwaltung](#5-datei-und-metadatenverwaltung)
- [6. Punkteverwaltung](#6-punkteverwaltung)
- [7. Mail, Verteiler und Versandhistorie](#7-mail-verteiler-und-versandhistorie)
- [8. Serverbetrieb](#8-serverbetrieb)
- [9. Datenbank, Backups und Migrationen](#9-datenbank-backups-und-migrationen)
- [10. Updates und Versionierung](#10-updates-und-versionierung)
- [11. Wartungsmodus und Systemstatus](#11-wartungsmodus-und-systemstatus)
- [12. Sicherheit, Sitzungen und Geräte](#12-sicherheit-sitzungen-und-gerate)
- [13. Regelmäßige Admin-Workflows](#13-regelmassige-admin-workflows)
- [14. Fehlerbehebung](#14-fehlerbehebung)
- [15. Versionshistorie und technische Fortschreibung](#15-versionshistorie-und-technische-fortschreibung)

# 1. Überblick

ODV besteht aus einer lokalen Desktop-App, einem zentralen API-Backend, einer MySQL/MariaDB-Datenbank, der Nextcloud-Dateiablage und optionalen Mail-/OpenAI-/OCR-Funktionen.

Admin-Aufgaben sind:

- Benutzer und Rollen verwalten.
- Ordnerrechte und Stammdaten pflegen.
- Dateien prüfen, korrigieren, übernehmen, verschieben oder umbenennen.
- Punkte und Sonderpunkte kontrollieren.
- Rundmail- und Verteilerfunktionen betreuen.
- Systemstatus, Datenbanksicherung, Migrationen und Updates überwachen.

Superadmins haben zusätzlich Zugriff auf Server-Deployment, Datenbankmigrationen, Backup-Rücksicherung und Update-Freigabe.

# 2. Systemarchitektur

| Komponente | Aufgabe |
| --- | --- |
| ODV Desktop-App | Lokale Bedienoberfläche für Upload, Anzeige, Admin-Bearbeitung, Punkte, Mail und Systemdialoge. |
| Nextcloud Desktop Client | Synchronisiert lokal abgelegte Dateien mit der Nextcloud. |
| Nextcloud-Struktur | Physischer Dateispeicher für Ortschronik, Ablage, Austausch, Informationen und Ortsordner. |
| API | Zentrale Anmeldung, Rechteprüfung, Dokumentverwaltung, Personen, Punkte, Mail, Backups und Migrationen. |
| MySQL/MariaDB | Führende Datenhaltung für Benutzer, Dokumente, Historie, Rechte, Punkte, Verteiler und Systemeinstellungen. |
| JSON-Sicherung | Lokale bzw. synchronisierte Sicherung der Metadaten, nicht mehr führend im API-Betrieb. |

Grunddatenfluss:

1. Benutzer meldet sich über die API an.
2. App erhält Token, Rolle, Ort und Rechte.
3. Datei wird lokal in die Nextcloud-Struktur kopiert oder dort gefunden.
4. Metadaten werden über die API gespeichert.
5. API schreibt Dokument, Historie, Personen und Punkte in MySQL.
6. JSON bleibt zusätzliche Sicherung.

# 3. Rollen, Rechte und Benutzerverwaltung

| Rolle | Zweck |
| --- | --- |
| Ortschronist/Bearbeiter | Dateien erfassen, anzeigen, eigene oder berechtigte Metadaten pflegen. |
| Admin | Dokumente prüfen, korrigieren, übernehmen, Rundmail und operative Pflege. |
| Superadmin | System-, Server-, Datenbank-, Update- und Benutzerverwaltung. |

Benutzerverwaltung erfolgt zentral über API/MySQL. Lokale Benutzerdateien sind nicht mehr führend.

Wichtige Admin-Regeln:

- Den eigenen Superadmin-Zugang nicht deaktivieren.
- Rollen sparsam vergeben.
- Ordnerrechte bewusst zwischen Lesen und Schreiben trennen.
- Neue Benutzer nach erstem Login und Geräteanzeige prüfen.

# 4. Stammdatenverwaltung

Stammdaten betreffen vor allem Ortsordner, Archiv-/Sammlungswerte und weitere Listen, die in Auswahlfeldern verwendet werden.

Ziele:

- Einheitliche Schreibweisen.
- Weniger Freitext-Varianten.
- Bessere Suche und Auswertung.
- Stabilere Punkte- und Metadatenlogik.

Superadmins pflegen Stammdaten über das Admin-Menü. Änderungen sollten knapp in README und, wenn nutzerrelevant, in den Handbüchern dokumentiert werden.

# 5. Datei- und Metadatenverwaltung

Admins bearbeiten Dokumente im Bereich `Dateien bearbeiten`. Typische Aufgaben sind:

- Status setzen.
- Metadaten fachlich korrigieren.
- Erfasst-von-Zuordnung korrigieren.
- Datei normiert umbenennen oder verschieben.
- Vorhandene Dateien in ODV erfassen.
- Lokale JSON-Sicherungen gegen API/MySQL prüfen.

Beim Umbenennen oder Verschieben werden Dateinamen normiert. Verknüpfte OCR-PDFs werden nach Möglichkeit mitgeführt.

Statuslogik:

| Status | Bedeutung |
| --- | --- |
| hochgeladen | Datei wurde neu hochgeladen. |
| erfasst | Vorhandene Datei wurde nachträglich in ODV aufgenommen. |
| in_pruefung | Dokument ist fachlich in Prüfung. |
| uebernommen | Dokument ist übernommen und zählt regulär in Auswertungen. |
| abgelehnt / archiviert / geloescht | Sonderstatus für fachliche oder organisatorische Fälle. |

# 6. Punkteverwaltung

Die Punkteverwaltung ist seit v111 feldbezogen strukturiert.

## Metadatenregeln

Metadatenregeln bestehen aus:

- Metadatenfeld
- Wertung: `manual` oder `openAI`
- automatisch gebildeter Regel, z. B. `copyright_author_manual`
- Beschreibung
- Prüftyp
- Mindestwert
- Punkte
- Aktiv

Prüftypen:

| Prüftyp | Bedeutung | Beispiel |
| --- | --- | --- |
| characters | Mindestanzahl Zeichen | Beschreibung mindestens 50 Zeichen |
| words | Mindestanzahl Wörter | Beschreibung mindestens 8 Wörter |
| count | Mindestanzahl Einträge | Stichwörter mindestens 3 Begriffe |
| none | Keine Mindestprüfung | Systemregel |

Grundregeln:

- Manuelle Metadatenbefüllung zählt standardmäßig 2 Punkte.
- OpenAI-Befüllung zählt standardmäßig 1 Punkt.
- Korrigiert ein Bearbeiter einen OpenAI-Wert, wird die OpenAI-Wertung durch manuelle Wertung ersetzt.
- Punkte erhält der tatsächliche Bearbeiter, also auch ein Admin, wenn er fachlich korrigiert.

## Sonderregeln

Sonderregeln sind systemseitig vorgegeben und nicht frei zu löschen. Dazu gehören:

- Bild mit Personenmarkierungen.
- Punkte je markierter Person.
- Dokument geprüft und übernommen.
- Datei umbenannt oder verschoben.
- Transkriptionsregeln.
- Besondere Sammlung / Archivordner.

Die Systemregel `transcription_document` bewertet Transkriptionen von Zeitung, Akte oder Urkunde mit 10 Punkten.

## Manuelle Zusatzpunkte

Manuelle Zusatzpunkte bleiben eigener Regeltyp. Sie können Tätigkeiten wie Archiv-Recherche, Erschließung, Veranstaltungen oder sonstige Arbeit abbilden.

# 7. Mail, Verteiler und Versandhistorie

ODV unterstützt Rundmails und Informationen mit:

- Benutzerempfängern.
- Verteilern.
- externen Mailadressen.
- Versand ohne Anlage.
- Versand mit Dokumentanhang.
- Versand mit Nextcloud-Downloadlink.
- Versandhistorie.

Empfänger werden nicht gegenseitig offengelegt. Fehlende Downloadlinks können beim Versand automatisch erzeugt werden.

Admin-Aufgabe ist die Pflege von Verteilern und die Kontrolle der Versandhistorie.

# 8. Serverbetrieb

Serverfunktionen liegen im Admin-Menü unter `Server` bzw. in den Superadmin-Einstellungen.

Wichtig:

- Produktive API-Datei ist `routes.php` im Serverpfad der API.
- ODV kann `server/routes.php` per FTP hochladen.
- Vor dem Upload wird die vorhandene Serverdatei mit Version und Zeitstempel gesichert.
- FTP-Passwort wird lokal per Windows-DPAPI verschlüsselt gespeichert.

Wenn App- und API-Version abweichen, erhalten Superadmins beim Start einen Hinweis.

# 9. Datenbank, Backups und Migrationen

Datenbankänderungen laufen über die Server-API, nicht direkt aus dem Client gegen MySQL.

Wichtige Funktionen:

- `Datenbankmigrationen prüfen/ausführen`
- `Datenbank sichern`
- `Datenbank zurücksetzen`
- `Backup zurücksichern`
- `Wartungsmodus / Datenbanksperre`

Unterschied:

| Funktion | Wirkung |
| --- | --- |
| Datenbank zurücksetzen | Löscht Bewegungs-/Testdaten nach Sicherheitsabfrage. |
| Datenbank sichern | Erstellt serverseitig ein SQL-GZ-Backup. |
| Backup zurücksichern | Spielt ein vorhandenes Serverbackup zurück. |
| Migrationen ausführen | Passt Tabellen/Regeln kontrolliert an. |

Bei Migrationen wird zuerst ein Backup erstellt. Bei Tabellenänderungen wird die betroffene Tabelle mit Versionssuffix gesichert, z. B. `point_rules_v110`.

# 10. Updates und Versionierung

Superadmins können freigegebene ODV-Versionen verwalten. Die App prüft beim Start und über `Hilfe > Nach ODV-Update suchen...` auf Updates.

Updatefreigabe:

- `Admin > Updates > ODV-Updatefreigabe verwalten...` öffnen.
- Mit `Updatepaket vorbereiten...` das fertige Updatepaket auswählen.
- ODV kopiert die Datei in den lokalen Nextcloud-Updateordner `02_AUSTAUSCH/ODV_UPDATE/Windows`.
- Dateiname, Relativpfad und SHA256-Prüfsumme werden automatisch eingetragen.
- Version, Pflichtupdate und Release-Hinweise prüfen und anschließend speichern.

Die Bearbeiter bekommen den Updatehinweis automatisch, sobald die gespeicherte Freigabe eine neuere Version als ihre lokale ODV-Version enthält.

Als Paketname wird künftig `ODV_vXXX.zip` empfohlen, z. B. `ODV_v112.zip`. Das ZIP soll den vollständigen Inhalt von `dist\ODV` enthalten, nicht nur die einzelne `ODV.exe`, damit auch der Updater und alle Programmdateien verteilt werden.

Versionierung:

- App-Version steht in `app/main.py`.
- API-Version steht in `server/routes.php`.
- README und Handbücher werden bei Änderungen fortgeschrieben.
- Bei neuer Version werden alle Versionsbezeichnungen angepasst.

# 11. Wartungsmodus und Systemstatus

Der ausführliche Systemstatus wird nicht mehr automatisch beim Start angezeigt. Er ist über `Hilfe > Systemstatus...` abrufbar.

Superadmins erhalten beim Start nur Hinweise, wenn Handlungsbedarf besteht:

- API-Version passt nicht zur App-Version.
- Datenbankmigrationen sind offen.
- Statusprüfung schlägt fehl.

Der Wartungsmodus sperrt normale Zugriffe kontrolliert, Superadmins bleiben zur Verwaltung zugriffsberechtigt.

# 12. Sicherheit, Sitzungen und Geräte

ODV protokolliert Sitzungen und Geräte. Neue Geräte können Superadmins auffallen und bei Bedarf sperren.

Sicherheitsregeln:

- Keine MySQL-Zugangsdaten im Client.
- API-Token lokal speichern, aber serverseitig prüfen.
- FTP-Passwort lokal verschlüsseln.
- Wartungsmodus vor kritischen Datenbankarbeiten nutzen.
- Backups vor Migrationen und Rücksicherungen prüfen.

# 13. Regelmäßige Admin-Workflows

## Neuer Benutzer

1. Benutzer anlegen.
2. Rolle festlegen.
3. Ort und E-Mail prüfen.
4. Ordnerrechte vergeben.
5. Ersten Login und Gerät kontrollieren.

## Dokument prüfen und übernehmen

1. Dokument in `Dateien bearbeiten` öffnen.
2. Datei und Vorschau prüfen.
3. Metadaten fachlich korrigieren.
4. Personenmarkierungen prüfen.
5. Status auf `uebernommen` setzen.
6. Falls nötig Datei normiert umbenennen oder verschieben.

## Server aktualisieren

1. Lokal prüfen, ob `server/routes.php` zur App-Version passt.
2. `Admin > Server > routes.php sichern/hochladen` verwenden.
3. Danach API-Status prüfen.
4. Offene Datenbankmigrationen ausführen.

## Migration ausführen

1. Wartungsmodus erwägen.
2. Backup-Status prüfen.
3. Migrationen anzeigen.
4. Offene Migrationen ausführen.
5. Ergebnis und Migrationsprotokoll prüfen.

# 14. Fehlerbehebung

| Problem | Mögliche Ursache | Maßnahme |
| --- | --- | --- |
| App/API-Version abweichend | Server-routes.php nicht aktuell | routes.php hochladen. |
| Migration offen | Datenbankstruktur noch alt | Migration über Admin-Menü ausführen. |
| Datei nicht auffindbar | Lokaler Nextcloud-Pfad anders | Sync-Ordner und Dateipfad prüfen. |
| Bearbeitung nicht möglich | Rechte, Status oder Sperre | Rechte/Status prüfen, ggf. Sperre abwarten. |
| Mailversand fehlschlägt | Verteiler, SMTP oder Linkproblem | Versandhistorie und API-Fehler prüfen. |
| Punkte fehlen | Regel inaktiv, Mindestwert nicht erfüllt oder Status nicht übernommen | Punkteregel, Metadaten und Dokumentstatus prüfen. |

# 15. Versionshistorie und technische Fortschreibung

## v83 bis v95

- OpenAI-Prüfung wird bewusst manuell ausgelöst.
- DOCX- und PDF-Inhalte werden besser ausgewertet.
- OCR-PDFs werden als verknüpfte Analysefassung geführt.
- OpenAI-Ampel, OCR-Fortschritt und Kosten-/Tokenanzeige ergänzt.
- Schutz gegen alte Metadatenreste beim Dateiwechsel.

## v104 bis v107

- Superadmin-Einstellungen in Reiter gegliedert.
- FTP-Deployment für `routes.php`.
- FTP-Passwort lokal per Windows-DPAPI verschlüsselt.
- Vor Upload wird Serverdatei gesichert.

## v106 bis v111

- Serverseitige Datenbankmigrationen über API.
- Migrationsprotokoll `odv_schema_migrations`.
- Automatisches Backup vor Migration.
- Backup-Rücksicherung aus ODV.
- Admin-Menü fachlich gegliedert.
- Systemstatus ins Hilfe-Menü verlagert.
- Neue Punkte-Regelbasis mit Feld, Wertung, Prüftyp und Mindestwert.
- Handbuch und Admin-Handbuch als Markdown ins Hilfe-Menü eingebunden.
- Updatefreigabe vereinfacht: fertiges Updatepaket auswählen, automatisch in den Nextcloud-Updateordner kopieren und SHA256-Prüfsumme übernehmen.
- Paketkonvention für Updates festgelegt: `ODV_vXXX.zip` aus dem vollständigen `dist\ODV`-Ordner.
- Technischer Strukturumbau begonnen: Hilfe-/Markdown-Anzeige liegt in `app/help_docs.py`, Updateprüfung und Updatefreigabe liegen in `app/update_manager.py`.
- Datenbank-/Serverbetrieb ausgelagert: Backup, Rücksicherung, Migrationen, Wartungsmodus und `routes.php`-Deployment liegen in `app/admin_operations.py`.
- Punkteverwaltung ausgelagert: Punkteregeln, Punkteübersichten und manuelle Sonderpunkte liegen in `app/points_manager.py`.
- Mailbereich ausgelagert: Rundmail, Verteilerverwaltung, Versandhistorie, Nextcloud-Mail-Links und Mailanhänge liegen in `app/mail_manager.py`.
- Benutzerverwaltung ausgelagert: Benutzer, Rechte sowie Sitzungen/Geräte liegen in `app/user_admin.py`.
- Stammdatenbereich ausgelagert: Ortsordner, Archiv/Sammlung, vorhandene Dateien einlesen und lokale Sicherungsdateien bereinigen liegen in `app/masterdata_manager.py`.
- Ordner-/Konfigurationslogik ausgelagert: Nextcloud-/Metadatenordner, Zielordnerauswahl, Ordnerbaum und Schreibordnerprüfung liegen in `app/config_folders.py`.
- Systemstatus-Dialog ausgelagert: Anzeige und Aktualisierung liegen in `app/system_status.py`.
- Metadaten-Helfer ausgelagert: Metadatenformular, Feldhilfen, Dokumenttyp-/Archiv-/Keyword-Vorschläge und EXIF/GPS-Auswertung liegen in `app/metadata_helpers.py`.
- EXIF/GPS-Verhalten angepasst: GPS-Koordinaten werden separat gespeichert und ersetzen nicht automatisch das fachliche Feld `Ort`.
- Startschutz ausgelagert: Single-Instance-Sperre und PyInstaller-Ressourcenpfad liegen in `app/single_instance.py`.
- GPS-Ort ergänzt: Bei Bildern mit EXIF-GPS-Daten wird zusätzlich ein deutscher Ortsname aus den Koordinaten ermittelt, als `GPS-Ort` in den JSON-Metadaten gespeichert und in der Oberfläche schreibgeschützt hinter den Koordinaten angezeigt; `Ort` bleibt als reiner Ortsname bearbeitbar. Dafür ist keine zusätzliche Tabellenspalte notwendig.
- Upload-Metadatenmaske angepasst: GPS-Koordinaten werden unter `Ort` als reine Anzeige dargestellt; Stichwortvorschläge aus Dateinamen filtern technische Kamera-/Bildtokens und Ziffernfolgen strenger.
- GPS-Anzeige weiter reduziert: Die GPS-Zeile erscheint nur bei vorhandenen Koordinaten und wird ohne Rahmen oder Hervorhebung dargestellt.

## Dokumentationsregel

Künftige Änderungen werden dokumentiert in:

- `README.md` unter Versionshistorie.
- `Handbuch.md`, wenn Bearbeiter betroffen sind.
- `Admin-Handbuch.md`, wenn Admins, Betrieb, Server, Datenbank oder Migrationen betroffen sind.
- Superadmins können die `README.md` direkt über `Hilfe > Versionshistorie` im Browser öffnen.
