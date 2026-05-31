# ODV-Handbuch für Bearbeiter

Stand: v112

Dieses Handbuch beschreibt die Arbeit mit der Ortschronisten-Datei-Verwaltung (ODV) aus Sicht von Bearbeiterinnen und Bearbeitern. Es konzentriert sich auf die tägliche Erfassung, Pflege und Suche von Dateien und Metadaten.

# Inhalt

- [1. Überblick](#1-uberblick)
- [2. Rollen und Grundbegriffe](#2-rollen-und-grundbegriffe)
- [3. Erster Start und Anmeldung](#3-erster-start-und-anmeldung)
- [4. Beispiel-Workflow: neue Datei erfassen](#4-beispiel-workflow-neue-datei-erfassen)
- [5. Dateien hochladen](#5-dateien-hochladen)
- [6. Metadaten erfassen](#6-metadaten-erfassen)
- [7. OpenAI und OCR nutzen](#7-openai-und-ocr-nutzen)
- [8. Bilder und Personenmarkierung](#8-bilder-und-personenmarkierung)
- [9. Dateien anzeigen, suchen und öffnen](#9-dateien-anzeigen-suchen-und-offnen)
- [10. Eigene Dateien bearbeiten](#10-eigene-dateien-bearbeiten)
- [11. Punkte verstehen](#11-punkte-verstehen)
- [12. Mail und Informationen](#12-mail-und-informationen)
- [13. Häufige Fragen](#13-haufige-fragen)
- [14. Checklisten](#14-checklisten)
- [15. Wichtige Änderungen seit v82](#15-wichtige-anderungen-seit-v82)

# 1. Überblick

ODV hilft Ortschronisten, Dateien geordnet in der Nextcloud abzulegen, fachlich zu beschreiben und später wiederzufinden. Die App ist nicht nur eine Dateiablage, sondern eine gemeinsame Arbeitsoberfläche für Datei, Metadaten, Historie, Personenmarkierungen und Punkte.

Wichtig ist: ODV ersetzt nicht die fachliche Bewertung. OpenAI, OCR und automatische Vorschläge können helfen, aber die letzte Entscheidung trifft immer der Bearbeiter.

| Bereich | Bedeutung |
| --- | --- |
| Dateiablage | Die Datei liegt im lokalen Nextcloud-Sync-Ordner. |
| Metadaten | Fachliche Angaben wie Datum, Ort, Quelle, Rechte, Beschreibung und Stichwörter. |
| API/MySQL | Zentrale Speicherung von Dokumentdaten, Historie, Personen und Punkten. |
| JSON-Sicherung | Zusätzliche Sicherung der Metadaten im Metadatenordner. |
| Rechte | Sichtbarkeit und Bearbeitung hängen von Rolle und Ordnerrechten ab. |

# 2. Rollen und Grundbegriffe

Bearbeiter bzw. Ortschronisten können Dateien erfassen, beschreiben, anzeigen und je nach Berechtigung eigene oder freigegebene Metadaten bearbeiten.

Admins und Superadmins haben zusätzliche Verwaltungsfunktionen. Diese sind im Admin-Handbuch beschrieben.

| Begriff | Erklärung |
| --- | --- |
| Upload | Eine neue Datei wird über ODV in die Nextcloud-Struktur übernommen. |
| Erfassung | Eine vorhandene Datei wird fachlich mit Metadaten in ODV aufgenommen. |
| Metadaten | Beschreibung und Kontext einer Datei. |
| OCR | Texterkennung für gescannte oder bildhafte PDFs. |
| OpenAI-Prüfung | Unterstützende Analyse einer Datei zur Metadatenvorschlagserstellung. |
| Status | Bearbeitungszustand eines Dokuments, z. B. erfasst oder übernommen. |

# 3. Erster Start und Anmeldung

Beim Start meldet sich der Benutzer mit seinem ODV-Zugang an. Die App verbindet sich mit der zentralen API und lädt Rolle, Ort und Berechtigungen.

Vor der Arbeit sollte geprüft werden:

- Der lokale Nextcloud-Ordner ist eingerichtet.
- Der Nextcloud Desktop Client synchronisiert.
- ODV zeigt den korrekten Benutzer und die passende Rolle an.
- Die gewünschte Datei liegt lokal erreichbar vor.

Falls ein technischer Hinweis erscheint, betrifft er meist Admins oder Superadmins. Bearbeiter müssen keine Serverdateien hochladen, keine Datenbankmigrationen ausführen und keine Backups zurücksichern.

# 4. Beispiel-Workflow: neue Datei erfassen

1. ODV starten und anmelden.
2. Reiter `Dateien hochladen` öffnen.
3. Datei auswählen oder per Drag & Drop einfügen.
4. Zielordner prüfen.
5. Optional `OpenAI prüfen` ausführen.
6. Sinnvolle Vorschläge übernehmen und fachlich kontrollieren.
7. Metadaten vollständig und nachvollziehbar ausfüllen.
8. Bei Bildern Personen markieren, wenn sinnvoll und bekannt.
9. Datei speichern bzw. hochladen.
10. In `Dateien anzeigen` kontrollieren, ob Datei und Metadaten richtig erscheinen.

Dieser Ablauf ist der empfohlene Standardfall. Bei vorhandenen Dateien, die schon in der Nextcloud liegen, erfolgt die Erfassung über die Anzeige bzw. Admin-Funktionen.

# 5. Dateien hochladen

Beim Hochladen kopiert ODV die ausgewählte Datei in den lokalen Nextcloud-Sync-Ordner. Die Synchronisation in die Cloud erledigt anschließend der Nextcloud Desktop Client.

Gute Praxis:

- Nur fachlich passende Zielordner verwenden.
- Dateinamen nicht künstlich kompliziert machen; ODV normiert bei Admin-Aktionen Dateinamen.
- Keine temporären Dateien, Dubletten oder Systemdateien hochladen.
- Vor dem Speichern prüfen, ob Dokumenttyp, Datum, Ort und Quelle plausibel sind.

ODV erzeugt technische Angaben wie Upload-ID, Erfasst von und Hochgeladen am automatisch.

# 6. Metadaten erfassen

Metadaten machen Dateien später auffindbar und fachlich verwertbar. Eine Datei ohne Metadaten ist oft kaum besser als eine unsortierte Ablage.

Wichtige Felder:

| Feld | Empfehlung |
| --- | --- |
| Datum / Zeitraum | So genau wie bekannt eintragen. Ungefähre Angaben sind besser als leer. |
| Ort | Ortsteil oder Bezug eintragen, wenn erkennbar. Bei Bildern mit GPS-Daten wird hier der ermittelte Ortsname vorbelegt und kann bearbeitet werden. |
| GPS-Koordinaten | Werden bei Bildern aus EXIF-Daten übernommen und nur dann direkt unter dem Ort angezeigt, mit GPS-Ort in Klammern, z. B. `50.378094, 10.536086 (Milz)`. |
| GPS-Ort | Wird intern aus den GPS-Koordinaten ermittelt und mit den Metadaten gespeichert. |
| Ereignis / Thema | Anlass, Thema oder Zusammenhang nennen. |
| Quelle / Herkunft | Herkunft der Datei möglichst konkret angeben. |
| Beschreibung | Kurz, aber aussagekräftig beschreiben, was die Datei enthält. |
| Stichwörter | Suchbegriffe ergänzen, getrennt durch Komma oder Semikolon. ODV filtert technische Dateinamenreste wie Kamerakürzel und Nummern weitgehend heraus. |
| Rechte / Urheber | Bekannte Rechteinformationen eintragen. Unsicherheit im Hinweisfeld notieren. |

Für gute Beschreibungen hilft die Leitfrage: Was ist zu sehen oder enthalten, wo gehört es hin, wann ist es entstanden und warum ist es für die Ortschronik relevant?

# 7. OpenAI und OCR nutzen

OpenAI wird nicht automatisch beim Auswählen einer Datei aufgerufen. Die Prüfung erfolgt bewusst über `OpenAI prüfen`.

OpenAI kann helfen bei:

- Erkennen von Datum, Ort oder Thema.
- Vorschlägen für Beschreibung und Stichwörter.
- Auswertung lesbarer DOCX- und PDF-Inhalte.

OpenAI-Vorschläge müssen immer geprüft werden. Wenn ein OpenAI-Wert korrigiert wird, gilt die endgültige fachliche Leistung als manuelle Bearbeitung.

OCR hilft bei PDFs, die nur aus Bildern oder Scans bestehen. ODV kann eine durchsuchbare OCR-Fassung erzeugen. Das Original bleibt das Archivdokument; die OCR-Datei dient als verknüpfte Analysefassung.

# 8. Bilder und Personenmarkierung

Bei Bildern können Personen markiert und benannt werden. Die Markierung dient späterer Wiedererkennung und Dokumentation.

Empfehlungen:

- Nur tatsächlich erkennbare Personen markieren.
- Namen möglichst vollständig und einheitlich schreiben.
- Unsichere Zuordnungen vorsichtig formulieren oder im Hinweisfeld festhalten.
- Bei Gruppenbildern lieber sauber nummerieren als schnell ungenau erfassen.

Personenmarkierungen sind auch für Punkte relevant: Ein Bild mit Personenmarkierungen zählt als eigene Leistung, zusätzlich kann jede markierte Person gewertet werden.

# 9. Dateien anzeigen, suchen und öffnen

Im Bereich `Dateien anzeigen` können Dateien nach Berechtigung angezeigt und durchsucht werden. Die Suche ist normalisiert, sodass unterschiedliche Schreibweisen häufig trotzdem gefunden werden.

Möglichkeiten:

- Dateibaum durchsuchen.
- Dateien öffnen.
- Vorschau ansehen.
- Metadaten anzeigen.
- OCR-Fassung öffnen, falls vorhanden.
- Bei Bildern Personen anzeigen.

Die Anzeige ersetzt nicht die fachliche Pflege. Wenn Metadaten fehlen oder offensichtlich falsch sind, sollten sie korrigiert oder einem Admin gemeldet werden.

# 10. Eigene Dateien bearbeiten

Bearbeiter können je nach Rechtekonzept eigene bzw. berechtigte Dateien bearbeiten. Übernommene oder gesperrte Dokumente können eingeschränkt sein.

Typische Bearbeitungen:

- Beschreibung ergänzen.
- Stichwörter verbessern.
- Datum, Ort oder Thema korrigieren.
- Rechtehinweise ergänzen.
- Personenmarkierungen nachtragen.

Wenn ein anderer Benutzer ein Dokument gerade bearbeitet, kann eine Bearbeitungssperre greifen. Das verhindert parallele widersprüchliche Änderungen.

# 11. Punkte verstehen

Punkte sollen gute Erfassungsarbeit sichtbar machen. Sie sind kein Selbstzweck und ersetzen keine Qualitätsprüfung.

Grundlogik seit v112:

- Manuell befüllte Metadatenfelder zählen standardmäßig 2 Punkte.
- Von OpenAI übernommene Metadatenfelder zählen standardmäßig 1 Punkt.
- Wird ein OpenAI-Wert fachlich korrigiert, zählt die manuelle Bearbeitung.
- Mindestanforderungen können je Feld über Zeichen, Wörter, Anzahl oder keine Prüfung festgelegt sein.
- Eine Transkription von Zeitung, Akte oder Urkunde zählt als besondere Transkriptionsleistung mit 10 Punkten.
- Bild mit Personenmarkierung und einzelne Personenmarkierungen können eigene Punkte auslösen.
- `Mein Punktestand` aktualisiert sich beim Öffnen und beim Wechsel des Bearbeiters automatisch; ein manueller Aktualisieren-Button ist nicht mehr nötig.

Unterschied zwischen Prüftypen:

| Prüftyp | Bedeutung | Beispiel |
| --- | --- | --- |
| characters | Mindestanzahl Zeichen | Beschreibung mindestens 50 Zeichen |
| words | Mindestanzahl Wörter | Beschreibung mindestens 8 Wörter |
| count | Mindestanzahl Einträge | Stichwörter mindestens 3 Begriffe |
| none | Keine Mindestprüfung | System- oder Sonderregel |

# 12. Mail und Informationen

ODV kann für Informationen und Rundmails genutzt werden. Je nach Berechtigung können Dokumente als Anhang, als Nextcloud-Link oder ohne Anlage versendet werden.

Für Bearbeiter ist wichtig:

- Versandinformationen sorgfältig prüfen.
- Empfänger nicht versehentlich falsch wählen.
- Bei Dokumentlinks sicherstellen, dass das richtige Dokument ausgewählt ist.
- Bei normaler Information kann die Versandart ohne Anlage genutzt werden.

# 13. Häufige Fragen

## Wird OpenAI automatisch genutzt?

Nein. OpenAI wird erst über `OpenAI prüfen` gestartet.

## Muss ich OCR immer ausführen?

Nein. OCR ist sinnvoll bei gescannten oder bildhaften PDFs, wenn der Text sonst nicht lesbar ist.

## Warum sehe ich nicht alle Ordner?

Die Anzeige hängt von Rolle und Ordnerrechten ab.

## Warum kann ich manche Dateien nicht bearbeiten?

Mögliche Gründe sind fehlendes Schreibrecht, ein übernommener Status oder eine aktive Bearbeitungssperre.

## Was passiert, wenn ich OpenAI-Vorschläge korrigiere?

Dann zählt die endgültige Korrektur als manuelle fachliche Bearbeitung.

# 14. Checklisten

## Checkliste: neue Datei

- Datei fachlich passend ausgewählt.
- Zielordner geprüft.
- Dokumenttyp plausibel.
- Datum/Zeitraum eingetragen, soweit bekannt.
- Ort und Thema eingetragen, soweit bekannt.
- Quelle/Herkunft angegeben.
- Rechte/Urheber geprüft.
- Beschreibung verständlich.
- Stichwörter sinnvoll und getrennt.
- Bei Bilddateien Personen geprüft.

## Checkliste: gute Beschreibung

- Beschreibt den Inhalt, nicht nur den Dateinamen.
- Nennt wichtige Personen, Orte oder Ereignisse.
- Ist lang genug, um später verständlich zu sein.
- Enthält keine reinen Vermutungen ohne Hinweis.

## Checkliste: Stichwörter

- Mehrere Begriffe verwenden.
- Komma oder Semikolon als Trennung nutzen.
- Ort, Thema, Ereignis und besondere Namen berücksichtigen.
- Keine unnötigen Dopplungen.

# 15. Wichtige Änderungen seit v82

Seit v82 wurden vor allem folgende bearbeiterrelevante Themen verbessert:

- OpenAI wird bewusst manuell ausgelöst.
- DOCX- und PDF-Inhalte werden besser für Vorschläge genutzt.
- OCR-PDFs werden als verknüpfte Analysefassung geführt.
- Dateiansicht, Suche und Vorschau wurden robuster.
- Fenstergrößen und UI-Zustand werden zuverlässiger gespeichert.
- Punkte wurden in v112 feldbezogen und nachvollziehbarer strukturiert.
- Das Handbuch ist direkt über `Hilfe > Handbuch` erreichbar.
