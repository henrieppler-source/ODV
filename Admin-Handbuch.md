# ODV-Admin-Handbuch

Stand: v121

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

Superadmins haben zusätzlich Zugriff auf Server-Deployment, Datenbankmigrationen, Backup-Rücksicherung, Update-Freigabe und den Betriebsmodus.

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
- Über dem Dokumentenbereich kann per Ordnerfilter zwischen `alle` und den konfigurierten Admin-Arbeitsordnern umgeschaltet werden.

Die Liste der Admin-Arbeitsordner wird in den Admin-Einstellungen nicht mehr nur als Freitext gepflegt, sondern über eine Auswahl erweitert oder bereinigt. Dadurch lassen sich weitere Ordner bequemer hinzufügen.

Der zuvor geplante Reiter `Dateien nachbearbeiten` wurde wieder entfernt. Dateien ohne ODV-Eintrag sollen künftig direkt im zentralen Bereich `Dateien bearbeiten` bearbeitet werden.

Unter der Liste in `Dateien bearbeiten` erscheint bei lokal lesbaren Textdokumenten und PDFs `OpenAI prüfen`. Bei nicht lesbaren PDFs wird stattdessen `PDF OCR erstellen` angeboten; die erzeugte OCR-Fassung wird anschließend für die OpenAI-Prüfung verwendet.

Vor einer OpenAI-Nachprüfung wird das bereits gespeicherte OpenAI-Modell angezeigt. Ein erneuter Aufruf mit demselben Modell ist gesperrt, um doppelte Kosten zu vermeiden. Nach der Prüfung erscheint ein Feldvergleich mit aktuellem Wert und OpenAI-Vorschlag; je Feld kann `übernehmen`, `überschreiben` oder `anfügen` gewählt werden. Leere Felder sind mit `übernehmen` vorbelegt, ohne Auswahl wird der Vorschlag ignoriert. Der Dokumenttyp bleibt von der OpenAI-Nachübernahme ausgenommen.

`Orte prüfen` nutzt die Orte aus der Ortsverwaltung als Suchliste. ODV scannt lokal den gesamten lesbaren Text umlauttolerant nach diesen Orten, sendet aber nur die Fundstellen-Kontexte an OpenAI und zeigt eine ortsbezogene Inhaltszusammenfassung mit Stichwörtern an. Wird kein Ort gefunden, wird eine begrenzte Textprobe gemäß den OpenAI-Seiten-/Textumfang-Einstellungen geprüft. Vor dem OpenAI-Start wird das Modell ausgewählt; derselbe Ortsanalyse-Aufruf mit demselben Modell ist je Dokument gesperrt. Die Vorschläge können feldweise mit `übernehmen`, `überschreiben` oder `anhängen` in Datum, Ereignis, Primärquelle, Beschreibung, Stichwörter und Ort übernommen werden.

Übernommene Ortsanalyse-Metadaten werden sofort am Dokument gespeichert. Wenn MySQL nicht aktualisiert werden kann, zeigt ODV dies in der Statuszeile an.

Das Metadatenfeld `Beschreibung` wird beim Speichern und bei OpenAI-Übernahmen immer mit `enthält u.a.` begonnen, auch bei manueller Eingabe. Die bei `Orte prüfen` verwendeten lokalen Fundstellen werden als kompakte Textausschnitte in den Metadaten gespeichert, nicht als kompletter Dokumenttext.

Wenn gespeicherte Ortsanalyse-Fundstellen vorhanden sind, zeigt `Fundstellen anzeigen` diese lesbar nach Ort gruppiert an, inklusive verwendetem Modell und Aktualisierungszeitpunkt.

Unter `Admin-Einstellungen > API / OpenAI` können für `Orte prüfen` der Kontext vor/nach dem gefundenen Ort und die maximale Anzahl der Fundstellen eingestellt werden.

Der OpenAI-Aufruf startet bei `Orte prüfen` erst nach einer lokalen Vorprüfung. ODV zeigt die gefundenen Orte und Fundstellenanzahl an; erst nach Bestätigung und Modellwahl werden die Fundstellen-Kontexte an OpenAI gesendet.

In `Dateien anzeigen` sind Dateien ohne ODV-Eintrag im Baum mit `* ` vor dem Dateinamen markiert. Die Schrift bleibt schwarz; sortiert wird nach dem echten Dateinamen ohne Stern.

Admins und Superadmins können im Reiter `Dateien anzeigen` unter dem Dateibaum die aktuell ausgewählte Datei gezielt umbenennen oder in einen anderen Ordner verschieben. Wenn zur Datei bereits ein ODV-Datensatz existiert, werden Pfad, Zielordner und Dateiname in den Metadaten aktualisiert.

Konkrete Ordnerfilter in `Dateien bearbeiten` zeigen vorhandene ODV-Dokumente und zusätzlich physisch vorhandene Dateien ohne ODV-Eintrag. Diese Platzhalter werden mit Upload-ID `neu`, Statusanzeige `ohne` und leerem Erfasser angezeigt. `00_ORTSCHRONIK` bleibt ein Sonderfall und zeigt nur Dateien ohne ODV-Eintrag.

In diesem Sonderfilter wird statt `Erfasst von` die Spalte `Ordner` angezeigt; die Datumsspalte bleibt leer. Die Spaltenüberschriften der Bearbeitungsliste sind fett, klickbar und sortieren die aktuelle Liste.

Beim Umbenennen oder Verschieben werden Dateinamen normiert. Verknüpfte OCR-PDFs werden nach Möglichkeit mitgeführt.

Superadmins pflegen unter `Admin > Normalisierung...` die Dateinamenregeln. Die Standardvorlage bleibt auf `{datum}_{ort}_{dateiname}` voreingestellt. Ordnerbezogene Sonderregeln können Platzhalter wie `{ordner3}_{ordner4}_{dateiname_mmdd}` nutzen, z. B. für Zeitungen/Zeitschriften. ODV prüft Vorlagen gegen eine Sicherheitsregel und zeigt vor dem Speichern eine Vorschau.

Der gemeinsame Reiter `Dateien anzeigen/bearbeiten` ist der aktive Arbeitsbereich für Baumansicht, Metadaten, OpenAI, Orteprüfung, Sonderpunkte und Dateiaktionen. Die frühere Tabellenansicht wird intern nur noch als Fallback gehalten und nicht mehr als führender Datenpfad aktualisiert.

Im rechten Bereich ist `Metadaten` der Hauptreiter. `Vorschau / Personen` wird nur bei Bilddateien eingeblendet, damit Dokumente und PDFs mehr Platz für die Metadatenbearbeitung haben.

Die Bildvorschau lässt sich per Mausrad zoomen; der Zoom ist auf die aktuelle Bildauswahl begrenzt und wird beim Wechsel zurückgesetzt.

Die Upload-ID ist ein technisches, nicht änderbares Kennzeichen. Sie wird in Metadatenformularen nur als Text auf grauem Hintergrund angezeigt, nicht als Eingabefeld.

Unter `Erfasst von` und `Hochgeladen am` zeigen bestehende Metadaten zusätzlich `Bearbeitet von` und `Bearbeitet am`. Diese Felder sind technische Anzeigen und werden bei nachträglichen Änderungen automatisch gesetzt.

OCR-Dokumente:

- `_ocr.pdf`-Dateien sind technische Begleitdateien zum Originaldokument und erhalten keinen eigenen ODV-Datensatz.
- OpenAI nutzt die OCR-Fassung als lesbare Analysequelle, schreibt Metadaten aber ins Originaldokument.
- Beim Umbenennen oder Verschieben soll die verknüpfte OCR-Datei mitgeführt werden und bis auf den Zusatz `_ocr` denselben Dateinamen behalten.
- Die OCR-Fassung bleibt dem Original zugeordnet und soll künftig über Datei-/Kontextaktionen geöffnet werden können.

PDF-Verwaltung:

- Superadmins pflegen unter `Admin-Einstellungen > Allgemein` die Schwellwerte `Warnung ab MB`, `Optimierung empfehlen ab MB` und `Upload blockieren ab MB`.
- Große PDFs werden im Dateibaum mit `!! ` vor dem Dateinamen markiert. Die Sortierung bleibt am echten Dateinamen orientiert.
- PDF/A-Begleitdateien mit `_pdfa.pdf` werden normalerweise nicht als Arbeitsdatei angezeigt. Fehlt die Arbeits-PDF, kann die PDF/A-Fassung als Ersatz hellgrün erscheinen; OCR-Ersatzdateien erscheinen hellgelb.
- Das PDF-Kontextmenü öffnet vorhandene OCR- und PDF/A-Begleitfassungen direkt. Die Aktionen `PDF optimieren...` und `PDF/A erzeugen...` sind Admin-Aktionen.
- `Übersichten > PDF-Dateien...` zeigt aktuell lokal verfügbare Nextcloud-PDFs mit Nextcloud-Pfad, lokaler Verfügbarkeit, Größe der Arbeitsfassung, Originalgröße, ODV-Optimierungsnachweis, PDF/A-Fassung und OCR-Fassung. Die Ansicht kann auf einen Hauptordner und eine Mindestgröße, z. B. größer als `250 MB`, gefiltert werden. Beim Öffnen bzw. Aktualisieren wird zusätzlich lokal `pdf_sizes.csv` im ODV-Logordner geschrieben.
- Grundsatz: ODV soll künftig die zentral in Nextcloud verfügbaren Dateien als gemeinsame Sicht anzeigen. Lokale PDF-Aktionen bleiben möglich, wenn die Datei lokal verfügbar ist; erzeugte oder geänderte Dateien werden über den Nextcloud-Sync hochgeladen.
- Die Spaltenüberschriften der PDF-Übersicht sortieren die Tabelle. Per Rechtsklick auf eine PDF-Zeile können Admin/Superadmin die Datei öffnen, eine Kopie speichern, vorhandene OCR-/PDF-A-Fassungen öffnen oder die PDF-Aktionen starten.
- Wird eine Aktion aus der PDF-Übersicht gestartet, bleibt der Übersichts-Dialog im Vordergrund bzw. wird nach Bestätigungs- und Ergebnismeldungen wieder aktiviert.
- Während `PDF optimieren...` oder `PDF/A erzeugen...` läuft, erscheint ein Fortschrittsdialog mit laufendem Balken und der Meldung `Datei wird verarbeitet`. Die Verarbeitung läuft im Hintergrund; Ergebnis- oder Fehlermeldungen erscheinen danach wieder im ODV-Fenster.
- `Datei öffnen` öffnet bei PDFs bevorzugt die vorhandene `_pdfa.pdf`-Archivfassung, wenn sie existiert. Die Arbeits-PDF kann dadurch stärker für Bildschirmnutzung komprimiert werden.
- `PDF optimieren...` optimiert die Arbeitsdatei lokal. Superadmins wählen unter `Admin-Einstellungen > Allgemein` das Optimierungsprofil `verlustfrei`, `standard` oder `maximal`. `standard` nutzt Ghostscript mit ca. 144 dpi, `maximal` ca. 120 dpi; ohne Ghostscript nutzt ODV PyMuPDF als Fallback. ODV erstellt zuerst eine temporäre Datei und ersetzt die Arbeits-PDF nur, wenn die neue Datei kleiner ist.
- Wenn Windows die Arbeits-PDF beim Ersetzen sperrt, z. B. durch Adobe Reader, Explorer-Vorschau oder Nextcloud-Sync, versucht ODV den Austausch mehrfach kurz erneut. Bleibt die Sperre bestehen, erscheint ein klarer Hinweis; die Datei muss dann geschlossen bzw. der Sync abgewartet und die Optimierung erneut gestartet werden.
- Ghostscript kann mit ODV ausgeliefert werden. Dafür liegt eine portable Ghostscript-Installation im Projekt unter `tools\ghostscript`; der Windows-Build kopiert diesen Ordner nach `dist\ODV\tools\ghostscript`, und der Installer übernimmt ihn automatisch.
- Ist Ghostscript beim Programmstart nicht vorhanden, sucht ODV zusätzlich unter `tools\ghostscript_installer` nach einem mitgelieferten MSI-/EXE-Installer und startet diesen automatisch. Wenn Windows erhöhte Rechte verlangt, erscheint eine UAC-Bestätigung. ODV lädt Ghostscript nicht eigenständig aus dem Internet herunter; die Quelle bleibt dadurch kontrollierbar.
- Wenn keine kleinere Datei entsteht, bleibt die Arbeitsdatei unverändert. Der Versuch wird trotzdem protokolliert und in der PDF-Übersicht bei `Optimiert durch ODV` mit `X` angezeigt.
- `PDF/A erzeugen...` nutzt Ghostscript und erzeugt eine separate `_pdfa.pdf`-Archivfassung. Ohne Ghostscript wird die Aktion mit Hinweis abgebrochen, damit keine nicht-konforme PDF/A-Datei entsteht.
- Eine ODV-Optimierung soll technisch nachvollziehbar in den Metadaten gespeichert werden (`pdf_optimized_at`, `pdf_optimized_by`, Originalgröße, optimierte Größe, Werkzeug und Profil). Bereits durch ODV optimierte PDFs werden nicht unbemerkt erneut optimiert: Admin/Superadmin erhalten die Warnung `Dieses PDF wurde bereits am ... durch ... optimiert. Erneute Optimierung kann Qualität verschlechtern. Trotzdem erneut optimieren?`; Bearbeiter erhalten `Dieses PDF wurde bereits am ... durch ... optimiert. Keine weitere Optimierung möglich.`

Statuslogik:

| Status | Bedeutung |
| --- | --- |
| ohne | Physische Datei liegt in einem ODV-Arbeitsordner, hat aber noch keinen ODV-Eintrag. |
| hochgeladen | Datei wurde neu über ODV hochgeladen. |
| erfasst | Datei wurde fachlich bearbeitet bzw. als vorhandene Datei in die Ortschronik aufgenommen. |
| rueckfrage | Es liegt eine Rückfrage oder Korrektur vor. |
| geprueft | Rückfrage wurde vom Bearbeiter erledigt. |
| geaendert | Dokument wurde nach einer Erfassung oder Prüfung erneut geändert und muss fachlich nachgesehen werden. |
| archiviert | Dokument wurde fachlich oder organisatorisch abgelegt. |

# 6. Punkteverwaltung

Die Punkteverwaltung ist seit v116 feldbezogen strukturiert.

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
- `Mein Punktestand` lädt beim Öffnen und beim Wechsel des ausgewählten Bearbeiters automatisch neu.
- Dokumentbezogene Sonderpunkte können Admins/Superadmins im Reiter `Dateien anzeigen` über `Punkte > Sonderpunkte zum ausgewählten Dokument...` oder per Rechtsklick auf die Datei pflegen; vorhandene Einträge sind editierbar und löschbar. Noch nicht in ODV aufgenommene Dateien werden beim Aufruf automatisch als ODV-Dokument angelegt.

## Sonderregeln

Sonderregeln sind systemseitig vorgegeben und nicht frei zu löschen. Dazu gehören:

- Bild mit Personenmarkierungen.
- Punkte je markierter Person.
- Dokument fachlich erfasst.
- Datei umbenannt oder verschoben.
- Transkriptionsregeln.
- Besondere Sammlung / Archivordner.

Die Systemregel `transcription_document` bewertet Transkriptionen von Zeitung, Akte oder Urkunde mit 10 Punkten.

## Manuelle Zusatzpunkte

Manuelle Zusatzpunkte bleiben eigener Regeltyp. Sie können Tätigkeiten wie Archiv-Recherche, Erschließung, Veranstaltungen oder sonstige Arbeit abbilden.

## Jahresabschluss und Prämienbudget

Die Beitragsauswertung kann pro Kalenderjahr mit einem Prämienbudget arbeiten. Der Superadmin kann:

- einen Prämienbetrag je Jahr hinterlegen,
- den daraus errechneten Wert je Punkt einsehen,
- ein Punktejahr abschließen,
- ein Punktejahr nach Bedarf wieder öffnen.

Ein abgeschlossenes Punktejahr ist gesperrt für:

- Punkteregeln,
- automatische Punktvergabe,
- manuelle Punkte,
- Nachberechnungen.

# 7. Mail, Verteiler und Versandhistorie

ODV unterstützt Rundmails und Informationen mit:

- Benutzerempfängern.
- Verteilern.
- externen Mailadressen.
- Versand ohne Anlage.
- Versand mit Dokumentanhang.
- Versand mit Nextcloud-Downloadlink.
- Das Verfallsdatum für Nextcloud-Links wird im Rundmail-Dialog vorbefüllt und kann per Kalender gewählt werden.
- Standard-Mail-Texte können im Superadmin-Menü unter `Admin > Mail > Standard-Mail-Texte...` gepflegt und in der Rundmail geladen werden.
- Der Standardtext wird direkt über dem eigentlichen Textfeld ausgewählt; beim Wechsel wird der Textinhalt ersetzt.
- Im Rundmail-Dialog kann optional eine `Antwort an`-Adresse gesetzt werden. Der Versand erfolgt weiterhin über `info@ortschronik.info`, die Antwort kann aber an die gewählte Adresse gehen.
- Die Anzeige heißt jetzt `Versandart Anlagen`. Bei Nextcloud-Dateien wird im Link-Versand automatisch ein Downloadlink erzeugt, Dateien außerhalb der Nextcloud werden unabhängig davon normal angehängt.
- Echte Nextcloud-Downloadlinks werden über einen technischen Nextcloud-Zugang erzeugt. Superadmins pflegen Basis-URL, technischen Benutzer, App-Passwort und optionalen Remote-Basisordner unter `Admin-Einstellungen > Links / Hinweise`.
- Das technische Nextcloud-App-Passwort wird serverseitig verschlüsselt gespeichert und nicht wieder angezeigt; `***` zeigt ein vorhandenes Passwort an. Nur bei Passwortänderung wird ein neues Passwort eingegeben.
- Passwortfelder mit gespeichertem, aber verborgenem Passwort zeigen `***` als Platzhalter. Dieser Platzhalter wird beim Speichern nicht als neues Passwort übernommen; das gilt auch für normale Benutzerpasswörter in der Benutzerverwaltung.
- Über `Nextcloud-Zugang prüfen` kann der technische Zugang direkt gegen die Server-API getestet werden.
- Im Rundmail-Text und in Vorlagen ist das leichte Markup `/bText/b` erlaubt; beim Direktversand wird es als HTML-Fettschrift gerendert.
- In der Benutzerverwaltung können optional weiterhin Nextcloud-Benutzername und -Passwort je Nutzer erfasst werden. Für Rundmail-Downloadlinks ist vorrangig der technische Nextcloud-Zugang vorgesehen.
- Versandhistorie.

Empfänger werden nicht gegenseitig offengelegt. Fehlende Downloadlinks können beim Versand automatisch erzeugt werden.

## Rechte und Sichtbarkeit im Mailbereich

| Rolle | Empfänger | Externe Empfänger | Sichtbare Verteiler | Standardtexte | Versandhistorie |
| --- | --- | --- | --- | --- | --- |
| Bearbeiter | Nur Benutzer und eigene/ortsbezogene Verteiler | Nein | Eigene Verteiler und Verteiler aus dem gleichen Ort | Nein | Nur eigene Sendungen |
| Admin | Alle Benutzer | Ja | Nur Verteiler, die von Admin/Superadmin angelegt wurden | Ja | Nur eigene Sendungen |
| Superadmin | Alle Benutzer | Ja | Nur Verteiler, die von Admin/Superadmin angelegt wurden | Ja | Nur eigene Sendungen |

Verteiler speichern den Ersteller mit. Normale Nutzer sehen damit nur die von ihnen selbst oder im gleichen Ort angelegten Verteiler. Bearbeiter dürfen in ihren Verteilern auch Benutzer aus anderen Orten als Empfänger aufnehmen. Admin/Superadmin sehen ausschließlich Verteiler, die von Admin/Superadmin angelegt wurden.

Admin-Aufgabe ist die Pflege von Verteilern, Standardtexten und die Kontrolle der Versandhistorie.

# 8. Serverbetrieb

Serverfunktionen liegen im Admin-Menü unter `Server` bzw. in den Superadmin-Einstellungen.

Wichtig:

- Produktive API-Datei ist `routes.php` im Serverpfad der API.
- ODV kann `server/routes.php` per FTP hochladen.
- Vor dem Upload wird die vorhandene Serverdatei mit Version und Zeitstempel gesichert.
- Vorhandene `routes.php`-Backups können im Deployment-Dialog angezeigt und gezielt gelöscht werden; beim Upload bleiben automatisch nur die letzten drei Sicherungen erhalten.
- FTP-Passwort wird lokal per Windows-DPAPI verschlüsselt gespeichert.
- API-Token und OpenAI-API-Schlüssel werden lokal ebenfalls per Windows-DPAPI verschlüsselt gespeichert.
- `OpenAI-Schlüssel prüfen` prüft den Schlüssel gegen die OpenAI-API. Eine Guthabenanzeige kann je nach OpenAI-Zugang nicht per API abrufbar sein und ist dann nur als Hinweis zu verstehen.
- Die Server-API wird schrittweise modularisiert; Admin-/Backup-/Wartungsendpunkte liegen bereits in `server/routes_admin_endpoints.php`.
- FTP-Deployment nimmt lokale `routes*.php`-Dateien automatisch mit und rotiert Backups je Datei.

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
| Datenbank zurücksetzen | Löscht Bewegungs-/Testdaten nach Sicherheitsabfrage, inklusive Dokumente, Historie, Personenmarkierungen, Punkte und manuelle Sonderpunkte; nur im Testbetrieb möglich. |
| Datenbank sichern | Erstellt serverseitig ein SQL-GZ-Backup. |
| Backup zurücksichern | Spielt ein vorhandenes Serverbackup zurück. |
| Migrationen ausführen | Passt Tabellen/Regeln kontrolliert an. |

Bei Migrationen wird zuerst ein Backup erstellt. Bei Tabellenänderungen wird die betroffene Tabelle mit Versionssuffix gesichert, z. B. `point_rules_v110`.
Nach einem Bewegungsdaten-Reset löscht ODV verwaiste lokale JSON-Metadatensicherungen automatisch. Originaldateien in der Nextcloud werden nicht gelöscht.

# 10. Updates und Versionierung

Superadmins können freigegebene ODV-Versionen verwalten. Die App prüft beim Start und über `Hilfe > Nach ODV-Update suchen...` auf Updates.

Updatefreigabe:

- `Admin > Updates > ODV-Updatefreigabe verwalten...` öffnen.
- Mit `Updatepaket vorbereiten...` das fertige Updatepaket auswählen.
- ODV kopiert die Datei in den lokalen Nextcloud-Updateordner `02_AUSTAUSCH/ODV_UPDATE/Windows`.
- Dateiname, Relativpfad und SHA256-Prüfsumme werden automatisch eingetragen.
- Version, Pflichtupdate und Release-Hinweise prüfen und anschließend speichern.

Die Bearbeiter bekommen den Updatehinweis automatisch, sobald die gespeicherte Freigabe eine neuere Version als ihre lokale ODV-Version enthält.

Als Paketname wird künftig `ODV_vXXX.zip` empfohlen, z. B. `ODV_v115.zip`. Das ZIP soll den vollständigen Inhalt von `dist\ODV` enthalten, nicht nur die einzelne `ODV.exe`, damit auch der Updater und alle Programmdateien verteilt werden.

Versionierung:

- App-Version steht in `app/app_constants.py`.
- API-Version steht in `server/routes.php`.
- README und Handbücher werden bei Änderungen fortgeschrieben.
- Bei neuer Version werden alle Versionsbezeichnungen angepasst.

# 11. Wartungsmodus und Systemstatus

 Der ausführliche Systemstatus wird nicht mehr automatisch beim Start angezeigt. Er ist über `Hilfe > Systemstatus...` abrufbar; dort können Admins die Logdateien direkt öffnen. Zusätzlich gibt es `Hilfe > Logdateien öffnen...` im Explorer. Beim Leeren der Admin-Auswahl werden Bool-Felder jetzt korrekt mit `False` zurückgesetzt. Die Reset-Logik für Datei-, Upload- und Admin-Auswahl liegt jetzt in kleinen Helfern bzw. Mixins.

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
5. Bei Rückfragen Status auf `rueckfrage` setzen und den Hinweis direkt erfassen.
6. Wenn die Rückfrage erledigt wurde, den Status auf `geprueft` setzen.
7. Danach Status auf `erfasst` setzen.
8. Falls nötig Datei normiert umbenennen oder verschieben.

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
| Punkte fehlen | Regel inaktiv, Mindestwert nicht erfüllt oder Dokument noch nicht im gewerteten Status | Punkteregel, Metadaten und Dokumentstatus prüfen. |

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
- API-Token und OpenAI-API-Schlüssel lokal per Windows-DPAPI verschlüsselt.
- Server-Deployment berücksichtigt bereits `routes*.php`-Module.
- Vor Upload wird Serverdatei gesichert.

## v106 bis v115

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
- Punkteverwaltung aufgeteilt: Jahresauswertung, Sonderpunkte sowie Punkteregeln und `Mein Punktestand` liegen in `app/points_year_manager.py`, `app/points_special_manager.py` und `app/points_rules_manager.py`.
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
- Historie ausgelagert: Historie-Tab, Aktualisierung, Detailanzeige und `Historie gesehen` liegen in `app/history_manager.py`.
- UI-Zustand ausgelagert: Mausradbindung, Styles, Tabwechsel, Fenstergeometrie, Pane-Positionen und Spaltenbreiten liegen in `app/ui_state.py`.
- Punktejahre steuerbar gemacht: Jahresbudget, Jahresabschluss und Wiederöffnung liegen in `app/points_year_manager.py`; abgeschlossene Jahre sperren Punkte-Regeln, manuelle Punkte und Nachberechnungen.
- Sonderpunkte ausgelagert: Sonderpunkte-Dialoge, Sonderpunkte-Einstellungen und die Sonderpunkte-Übersicht liegen in `app/points_special_manager.py`.
- Punkteregeln und `Mein Punktestand` ausgelagert: Die Regelverwaltung und die persönliche Punkteansicht liegen jetzt in `app/points_rules_manager.py`.
- Der frühere Kompatibilitätsrest `app/points_manager.py` wurde entfernt; die Punktefunktionen sind jetzt vollständig auf eigene kleine Module verteilt.
- Der Dokumentstatus ist auf die fachlichen Werte `hochgeladen`, `erfasst`, `geaendert`, `rueckfrage`, `geprueft` und `archiviert` reduziert; ältere Statuswerte werden beim Speichern nur noch intern normalisiert.
- Im Upload-Bereich wird der geplante Nextcloud-Dateiname als eigenes, editierbares Feld geführt und zusätzlich im Wizard angezeigt.
- Die Personenmarkierung nutzt jetzt eine größere, fachlichere Eingabemaske mit `Nachweis`, größerer Bemerkung und stabiler Nummernvergabe.
- In `Dateien anzeigen` beginnt der Metadatenbereich bei jeder neuen Auswahl wieder oben; die Hinweistexte wurden gestrafft.
- Rückfragen verwenden ein eigenes `status_note` und überschreiben nicht mehr die allgemeine Bemerkung.
- Die Statuslogik selbst liegt in einem eigenen Admin-Status-Modul; `main.py` enthält dort keine Schattenmethoden mehr.
- Dateiöffnen, OCR-Verknüpfung, Download und Zugriffsprotokollierung sind technisch in ein eigenes Datei-Zugriffsmodul ausgelagert.
- Der Dialog `Dokumentzugriffe` gehört ebenfalls zum Datei-Zugriffsmodul.
- Die Startprüfung mit Ortsordner-Check und Superadmin-Warnungen steckt im Systemstatus-Modul.
- Die Metadaten-Textdarstellung und große Bildvorschau wurden in ein eigenes Darstellungsmodul ausgelagert.
- Das Laden, Speichern und die `uploaded_by`-Auswahl der Dateiansicht laufen jetzt über ein eigenes Metadatenformular-Modul.
- Upload- und API-Metadatenlogik liegen in einem eigenen Upload-Modul.
- Der Admin-Reiter und die Admin-Einstellungen liegen in einem eigenen Admin-UI-Modul.
- Die Admin-Listenansicht mit Filter, Zielordnern und Auswahl liegt in einem eigenen Admin-Listen-Modul.
- Der Dateibaum mit Filter und Datei-Auswahl liegt in einem eigenen Dateibaum-Modul.
- Admin-Berechtigungen, Sichtbarkeit und Metadatenordner liegen in einem eigenen Admin-Policy-Modul.
- Die komplette Dateiansicht mit Vorschau und Metadaten liegt im File-View-Modul.
- Anmeldung, Benutzerkontext und Masterdata-Dialog liegen in einem eigenen Session-Modul.
- Ordner-, Dateinamen- und Leseregeln liegen in einem eigenen Path-Policy-Modul.
- Lokale Pfade und Dateivarianten werden in einem eigenen Path-Resolution-Modul behandelt.

## v116 bis v120

- Die App-Version liegt jetzt zentral in `app/app_constants.py`; `app/main.py` ist nur noch der Launcher.
- Die App-Klasse ist in `app/uploader.py` gebündelt.
- Bootstrap, Startdialoge und Fensteraufbau liegen in `app/bootstrap_mixin.py` und `app/main_window_mixin.py`.
- Diese technische Aufteilung ändert die Bedienung nicht, macht Start und Wartung aber klarer.
- Betriebsmodus ergänzt: Im Produktivbetrieb ist der Bewegungsdaten-Reset gesperrt, im Testbetrieb bleibt er für Superadmins verfügbar.
- Reset-Bereinigung ergänzt: Verwaiste lokale JSON-Metadatensicherungen werden nach dem Reset automatisch gelöscht.
- Server-Deployment erweitert: Server-Backups können angezeigt und gezielt gelöscht werden; beim Upload bleiben automatisch nur die letzten drei Sicherungen erhalten.
- Beitragsauswertung erweitert: Geldbeträge werden mit `EUR` und zwei Nachkommastellen dargestellt; je Nutzer wird der berechnete Wert angezeigt.
- Rundmail-Dialog markiert Benutzer farblich, wenn sie über einen ausgewählten Verteiler enthalten sind.
- Mailbereich erweitert: Antwortadresse wird vorbelegt, Mailrechte sind rollenbasiert, Standardtexte sind auf Admin/Superadmin begrenzt und `Versandart Anlagen` unterscheidet Nextcloud-Links von normalen Anhängen.
- Technischer Nextcloud-Zugang ergänzt: Superadmins pflegen den zentralen `oc_app`-Zugang im Admin-Dialog; das App-Passwort wird serverseitig verschlüsselt gespeichert und für echte öffentliche Downloadlinks genutzt.
- OpenAI-Schlüsselprüfung korrigiert: Der Schlüsseltest wird nicht mehr durch die blockierte Guthabenabfrage überdeckt.
- Testbutton für den technischen Nextcloud-Zugang ergänzt.
- Dokumentbezogene Sonderpunkte sind in `Dateien anzeigen` per Punkte-Menü und Rechtsklick erreichbar; bestehende manuelle Einträge können bearbeitet oder gelöscht werden.
- Der separate Reiter `Dateien nachbearbeiten` wurde wieder entfernt; die Nachbearbeitung wird in `Dateien bearbeiten` integriert.
- `Dateien bearbeiten` bietet eine eigene OpenAI-/OCR-Leiste unter der Dokumentliste.
- PDF-Verwaltung erweitert: Schwellwerte in den Admin-Einstellungen, Baum-Markierung großer PDFs, Kontextmenü für OCR/PDF-A-Begleitfassungen, neue Übersicht `PDF-Dateien`, verlustfreie PyMuPDF-Optimierung und Ghostscript-basierte PDF/A-Erzeugung.

## v121 - Interne Strukturbereinigung

- `mail_manager` wurde in Utility-Module geteilt; Kernlogik für Nutzerkontext, Verteiler-Sichtbarkeit sowie Empfänger- und Anlagen-Helfer liegt jetzt in kleineren Hilfskomponenten zur besseren Wartbarkeit.
- Der Refactor wurde als Slice durchgeführt; Fachlogik und Verhalten von Rundmail-Dialogen und Verteilerfilterung sind unverändert.
- Für den Slice wurden `scripts/check_project_health.py` sowie gezielte Smoke-Pfade (`scripts/smoke_mail_dialog.py`, `scripts/smoke_core_paths.py`) erfolgreich ausgeführt.

## Dokumentationsregel

Künftige Änderungen werden dokumentiert in:

- `README.md` unter Versionshistorie.
- `Handbuch.md`, wenn Bearbeiter betroffen sind.
- `Admin-Handbuch.md`, wenn Admins, Betrieb, Server, Datenbank oder Migrationen betroffen sind.
- Superadmins können die `README.md` direkt über `Hilfe > Versionshistorie` im Browser öffnen.
