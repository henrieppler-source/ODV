# ODV-Stand und Arbeitsvereinbarungen

Stand: v121

Diese Datei sammelt die wichtigsten Vereinbarungen und den aktuellen Arbeitsstand für die Weiterentwicklung der ODV-Anwendung. Sie dient als kompakte Wiederaufnahmehilfe für spätere Sitzungen.

## Aktueller Stand

- Aktuelle App-Version: `v121`
- README-Version: `v121`
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
- Im Mailbereich werden echte öffentliche Nextcloud-Downloadlinks über einen technischen Nextcloud-Zugang erzeugt. Superadmins pflegen Basis-URL, Benutzer, App-Passwort und optionalen Remote-Basisordner unter `Admin-Einstellungen > Links / Hinweise`; das Passwort wird serverseitig verschlüsselt gespeichert und der Zugang kann per Testbutton geprüft werden. Passwortfelder zeigen bei gespeichertem verborgenem Passwort `***` als Platzhalter, einschließlich normaler Benutzerpasswörter.
- Der Mailbereich bekommt zusätzlich Standard-Mail-Texte, die im Superadmin-Menü gepflegt und in Rundmails geladen werden können.
- Standardtext-Auswahl im Rundmail-Dialog soll direkt über dem Textfeld stehen; beim Wechsel wird der Text ersetzt.
- Im Rundmail-Dialog kann optional eine `Antwort an`-Adresse gepflegt werden, während der Versand über `info@ortschronik.info` läuft.
- Für Mailtexte ist das leichte Markup `/bText/b` erlaubt und wird beim Direktversand als HTML-Fettschrift gerendert.
- Die Mail-UI zeigt `Versandart Anlagen`; Nextcloud-Dateien werden bei Link-Versand automatisch als Downloadlink erzeugt, andere Dateien werden normal angehängt.
- Mailrechte: Admin/Superadmin dürfen an alle senden und externe Empfänger nutzen; Bearbeiter nur an Benutzer und orts-/eigene Verteiler, ohne externe Empfänger.
- Verteiler speichern den Ersteller; normale Nutzer sehen nur eigene und ortsbezogene Verteiler, Admin/Superadmin nur von Admin/Superadmin angelegte Verteiler.
- Versandhistorie bleibt benutzerbezogen und zeigt jeweils nur die eigenen Sendungen.
- Im Reiter `Dateien bearbeiten` gibt es einen Ordnerfilter mit `alle` als Standard; die Admin-Arbeitsordner werden in den Einstellungen über Auswahl statt reinem Freitext gepflegt.
- Dokumentbezogene Sonderpunkte werden für Admin/Superadmin im Kontext `Dateien anzeigen` gepflegt; vorhandene manuelle Einträge sind editierbar und löschbar. Noch nicht aufgenommene Dateien werden beim Aufruf automatisch als ODV-Dokument angelegt.
- Der separate Reiter `Dateien nachbearbeiten` wurde wieder entfernt; Dateien ohne ODV-Eintrag sollen künftig direkt im zentralen Reiter `Dateien bearbeiten` erscheinen.
- In `Dateien bearbeiten` gibt es unter der Liste eine OpenAI-/OCR-Leiste: lesbare Textdokumente/PDFs können geprüft werden, nicht lesbare PDFs erhalten zuerst `PDF OCR erstellen`.
- OpenAI-Nachprüfungen in `Dateien bearbeiten` zeigen das zuletzt verwendete Modell, verhindern denselben Modellaufruf erneut und übernehmen Vorschläge nur nach feldweiser Auswahl: übernehmen, überschreiben oder anfügen; leere Felder sind mit übernehmen vorbelegt, keine Auswahl bedeutet ignorieren. Der Dokumenttyp wird dabei nicht geändert.
- `Orte prüfen` in `Dateien bearbeiten` sucht lokal nach Orten aus der Ortsverwaltung, sendet nur Fundstellen-Kontexte an OpenAI und erzeugt daraus eine ortsbezogene Zusammenfassung mit Stichwörtern. Vor dem OpenAI-Start wird das Modell gewählt; derselbe Ortsanalyse-Aufruf mit demselben Modell wird je Dokument gesperrt.
- Übernommene Werte aus `Orte prüfen` werden direkt am konkreten Dokument gespeichert, bleiben nach Dokumentwechsel erhalten und blenden die OpenAI-/Orte-Buttons nicht mehr aus.
- Bei Platzhalterdateien mit Anzeige `neu` legt die OpenAI-Übernahme automatisch einen echten ODV-Datensatz an; die technische Upload-ID wird nicht aus dem Anzeigeformular überschrieben.
- Fundstellen aus `Orte prüfen` werden vor Anzeige/Speicherung/OpenAI geglättet: Zeilenumbrüche, Silbentrennungen und typische OCR-Wortbrüche werden reduziert.
- Beschreibungen werden beim Speichern und bei OpenAI-Übernahmen immer mit `enthält u.a.` normalisiert; Ortsanalyse-Fundstellen werden als kompakte Metadatenkontexte gespeichert.
- In `Dateien anzeigen` werden Dateien ohne ODV-Eintrag schwarz angezeigt und mit `* ` vor dem Dateinamen markiert; die Sortierung bleibt am echten Dateinamen orientiert.
- Superadmins können unter `Admin > Normalisierung...` die Standard-Dateinamenvorlage und ordnerbezogene Sonderregeln mit Platzhaltern pflegen; Sonderregeln greifen nur bei gültiger Sicherheitsprüfung und passendem Ordner.
- Konkrete Ordnerfilter in `Dateien bearbeiten` zeigen vorhandene ODV-Dokumente und zusätzlich Dateien ohne ODV-Eintrag als Platzhalter (`neu`, Status `ohne`, Erfasser leer). `00_ORTSCHRONIK` zeigt weiterhin nur fehlende Einträge.
- Statusgrundlage: `ohne` = physisch vorhanden, noch kein ODV-Eintrag; `hochgeladen` = über ODV hochgeladen; `erfasst` = fachlich bearbeitet bzw. vorhandene Datei in die Ortschronik aufgenommen; `geaendert` = nach Erfassung/Prüfung erneut geändert und nachzusehen; danach folgen `rueckfrage`, `geprueft`, `archiviert`.
- `_ocr.pdf`-Dateien bleiben technische Begleitdateien zum Original, werden in `Dateien bearbeiten` nicht als eigener Bearbeitungsfall angezeigt, sollen beim Umbenennen/Verschieben mitgeführt werden und künftig über Datei-/Kontextaktionen am Original erreichbar bleiben.
- Upload-ID-Anzeigen in Metadatenformularen sind reine Textanzeigen auf grauem Hintergrund und keine Eingabefelder.
- Bestehende Metadatenformulare zeigen zusätzlich `Bearbeitet von` und `Bearbeitet am`; die Werte werden bei nachträglichen Änderungen automatisch gesetzt und gespeichert.
- Im `00_ORTSCHRONIK`-Sonderfilter zeigt `Dateien bearbeiten` nur den Ordner statt Erfasst-von/Datum; Listenüberschriften sind fett und sortieren per Klick.
- Der gemeinsame Reiter `Dateien anzeigen/bearbeiten` ist der aktive Dokument-Arbeitsbereich. Die alte Tabellenlogik wird nicht mehr aktiv aktualisiert und dient nur noch als interner Fallback, bis alle Altpfade vollständig entfernt werden können.
- Rechts in `Dateien anzeigen/bearbeiten` ist `Metadaten` der Hauptreiter; `Vorschau / Personen` wird nur bei Bilddateien eingeblendet.
- Die Bildvorschau kann per Mausrad gezoomt werden; beim Wechsel der Bildauswahl wird der Zoom zurückgesetzt.
- Im Personenmarkierungsdialog wird die angeklickte bzw. ausgewählte Markierung sofort im Bild hervorgehoben, um Verwechslungen bei vielen Personen zu vermeiden.
- PDF-Etappe 1 ist umgesetzt: Admin-Schwellwerte für Warnung/Optimierung/Blockade, `!! `-Markierung großer PDFs im Baum, Ersatzanzeige für PDF/A/OCR-Begleitdateien, Kontextmenüeinträge für vorhandene Begleitfassungen und die Übersicht `Übersichten > PDF-Dateien...` mit Ordner-/Größenfilter, Nextcloud-Pfad, lokaler Verfügbarkeit, Arbeitsdateigröße, Originalgröße, ODV-Optimierungsnachweis und lokalem `pdf_sizes.csv`-Log.
- Zielbild für ODV-Dateiansichten: Angezeigt werden soll grundsätzlich, was zentral in Nextcloud verfügbar ist. Lokale Verfügbarkeit steuert nur, ob lokale Aktionen wie Optimierung, PDF/A oder OCR direkt möglich sind; der Upload erfolgt anschließend über Nextcloud-Sync.
- Die PDF-Übersicht ist sortierbar und besitzt ein Rechtsklick-Menü für Öffnen, Kopie speichern, OCR/PDF-A anzeigen sowie `PDF optimieren...` und `PDF/A erzeugen...`.
- Aktionen aus der PDF-Übersicht führen Bestätigungs- und Ergebnisdialoge mit der PDF-Übersicht als Elternfenster; die Übersicht wird danach wieder in den Vordergrund geholt.
- Während `PDF optimieren...` und `PDF/A erzeugen...` läuft ein modaler Fortschrittsdialog mit `Datei wird verarbeitet`; die PDF-Verarbeitung läuft im Hintergrund, damit der Nutzer eine sichtbare Rückmeldung erhält.
- `Datei öffnen` öffnet bei PDFs bevorzugt eine vorhandene `_pdfa.pdf`-Archivfassung. Die Arbeits-PDF kann daher stärker für PC-Nutzung komprimiert werden.
- `PDF optimieren...` ist lokal aktiv; Superadmins können das Profil `verlustfrei`, `standard` oder `maximal` wählen. `standard` nutzt Ghostscript mit ca. 144 dpi, `maximal` ca. 120 dpi; ohne Ghostscript nutzt ODV PyMuPDF als Fallback. Die Arbeits-PDF wird nur ersetzt, wenn die optimierte Datei kleiner ist.
- Bei gesperrten PDFs versucht ODV das Ersetzen der Arbeitsdatei mehrfach kurz erneut und meldet danach verständlich, dass die Datei z. B. durch PDF-Reader, Explorer-Vorschau oder Nextcloud-Sync geschlossen/freigegeben werden muss.
- Ghostscript kann mit ODV ausgeliefert werden: ODV sucht unter `tools\ghostscript`, und der Windows-Build kopiert diesen Ordner in die Distribution.
- Falls Ghostscript beim Start fehlt, kann ODV einen mitgelieferten Installer aus `tools\ghostscript_installer` automatisch starten; verlangt Windows erhöhte Rechte, erscheint eine UAC-Bestätigung. Ohne mitgelieferte Dateien erfolgt kein Internetdownload.
- Ergibt der Optimierungsversuch keine kleinere Datei, wird dies als Versuch ohne Verkleinerung gespeichert und in der PDF-Übersicht bei `Optimiert durch ODV` mit `X` angezeigt.
- `PDF/A erzeugen...` ist Ghostscript-basiert und bricht mit Hinweis ab, wenn Ghostscript nicht verfügbar ist.
- Wiederholte PDF-Optimierung ist geregelt: Admin/Superadmin bekommen bei bereits durch ODV optimierten PDFs eine ausdrückliche Qualitätswarnung mit Bestätigung; Bearbeiter erhalten nur den Hinweis, dass keine weitere Optimierung möglich ist.
- Lokale PDF-Aktionen schreiben Metadaten zur Nachvollziehbarkeit: Optimierungszeitpunkt, Bearbeiter, Originalgröße, optimierte Größe, Werkzeug und Profil bzw. PDF/A-Pfad und Werkzeug.
- Die API-Endpunkte für Ordnerrechte und Ortsordner-Stammdaten müssen aktiv bleiben; fehlende Routen wurden wieder ergänzt.
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
- Der OpenAI-Schlüsseltest bewertet die Schlüsselprüfung getrennt von der Guthabenabfrage; wenn OpenAI die Guthabenabfrage blockiert, bleibt der Schlüsseltest trotzdem sichtbar erfolgreich.
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
