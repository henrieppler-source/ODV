# ODV Realtest-Checkliste

Projektstand vor dem Realtest: `v121`

Datum:

Tester:

Konten:
- [ ] Bearbeiter
- [ ] Admin
- [ ] Superadmin

## 1. Start und Anmeldung
- [ ] Programm startet ohne Traceback
- [ ] Login als Bearbeiter funktioniert
- [ ] Login als Admin funktioniert
- [ ] Login als Superadmin funktioniert
- [ ] Benutzername und Rolle werden korrekt angezeigt
- [ ] Fenstergroesse und Fensterposition wirken nach Neustart plausibel

## 2. Grundstatus und Systemdialoge
- [ ] `Hilfe > Systemstatus` laesst sich oeffnen
- [ ] `Hilfe > Logdateien oeffnen` laesst sich oeffnen
- [ ] API-Status ist nachvollziehbar
- [ ] Keine unerwarteten Fehlermeldungen beim Start

## 3. Stammdaten und Einstellungen
- [ ] Stammdaten lassen sich oeffnen
- [ ] Nextcloud-Basisordner wird korrekt angezeigt
- [ ] `Admin-Einstellungen` lassen sich oeffnen
- [ ] Passwortfelder werden maskiert angezeigt
- [ ] FTP-Test funktioniert oder meldet klaren Fehler
- [ ] OpenAI-Schluesseltest funktioniert oder meldet klaren Fehler
- [ ] Technischer Nextcloud-Zugangstest funktioniert oder meldet klaren Fehler
- [ ] PDF-Schwellwerte lassen sich speichern und nach erneutem Oeffnen wiedersehen

## 4. Rechte und Sichtbarkeit
- [ ] Als Bearbeiter sind Admin-Funktionen ausgeblendet oder gesperrt
- [ ] Als Admin sind Admin-Funktionen sichtbar
- [ ] Als Superadmin sind Superadmin-Funktionen sichtbar
- [ ] Nicht berechtigte Dateien koennen nicht bearbeitet werden

## 5. Upload
- [ ] Textdatei laesst sich im Upload-Reiter auswaehlen
- [ ] PDF laesst sich im Upload-Reiter auswaehlen
- [ ] Bilddatei laesst sich im Upload-Reiter auswaehlen
- [ ] Zielname wird vorbefuellt
- [ ] Metadaten werden sinnvoll vorbefuellt
- [ ] Drag & Drop mit einer Datei funktioniert
- [ ] Mehrfach-Drag & Drop wird korrekt behandelt
- [ ] Upload ohne Pflichtangaben wird blockiert oder klar gemeldet
- [ ] Upload schreibt lokale Metadaten korrekt
- [ ] Upload erzeugt API-Datensatz oder meldet API-Fehler klar

## 6. Dateien anzeigen / bearbeiten
- [ ] Reiter `Dateien anzeigen/bearbeiten` laesst sich oeffnen
- [ ] Baumansicht laedt korrekt
- [ ] Ordnerfilter `alle` funktioniert
- [ ] Konkreter Ordnerfilter funktioniert
- [ ] Statusfilter `ohne` funktioniert
- [ ] Groesse-Markierung `!!` erscheint bei grossen PDFs
- [ ] PDF/A-Begleitdateien erscheinen korrekt
- [ ] OCR-Ersatzdateien erscheinen korrekt
- [ ] Metadaten rechts werden korrekt angezeigt
- [ ] Upload-ID erscheint nur als nicht editierbarer Text
- [ ] Aenderungen an Metadaten werden gespeichert
- [ ] `Bearbeitet von` und `Bearbeitet am` werden gesetzt
- [ ] Rechtsklick-Menue zeigt passende Aktionen
- [ ] Bildvorschau erscheint nur bei Bildern
- [ ] Bildzoom funktioniert
- [ ] Personenmarkierungen koennen angelegt werden
- [ ] Personenmarkierungen koennen verschoben werden
- [ ] Personenmarkierungen koennen geloescht werden
- [ ] Personenmarkierungen werden gespeichert

## 7. Umbenennen und Verschieben
- [ ] Datei umbenennen funktioniert
- [ ] Datei verschieben funktioniert
- [ ] OCR-Begleitdatei wird mitgezogen
- [ ] PDF/A-Begleitdatei wird mitgezogen
- [ ] Namensnormalisierung funktioniert
- [ ] Ungueltige Umbenennung wird sauber blockiert
- [ ] Extern geloeschte Datei erzeugt klare Meldung
- [ ] Extern umbenannte Datei wird nachvollziehbar behandelt

## 8. OpenAI-Pruefung
- [ ] Lesbares Dokument kann mit `OpenAI prüfen` gestartet werden
- [ ] Modelldialog erscheint
- [ ] Gleiches Modell wird nicht doppelt gestartet oder Cache greift
- [ ] Anderes Modell kann ausgewaehlt werden
- [ ] Metadatenvorschlaege werden angezeigt
- [ ] Leere Felder sind mit `uebernehmen` vorbelegt
- [ ] `uebernehmen` funktioniert pro Feld
- [ ] `ueberschreiben` funktioniert pro Feld
- [ ] `anfügen` funktioniert pro Feld
- [ ] Ohne Auswahl bleibt ein Feld unveraendert
- [ ] Dokumenttyp wird nicht durch OpenAI veraendert
- [ ] Gespeicherte OpenAI-Werte bleiben nach Wechsel erhalten

## 9. Orte pruefen
- [ ] `Orte pruefen` startet bei einem Dokument mit Ortsnamen
- [ ] Gefundene Orte werden lokal angezeigt
- [ ] Fundstellen werden lesbar gruppiert
- [ ] Fallback auf Textprobe funktioniert bei fehlenden Ortsnamen
- [ ] Modellwahl vor dem Lauf erscheint
- [ ] Gleiches Modell wird nicht doppelt gestartet oder Cache greift
- [ ] Ergebnisdialog zeigt Zusammenfassung
- [ ] Ergebnisdialog zeigt Stichwoerter
- [ ] Felduebernahme fuer Datum funktioniert
- [ ] Felduebernahme fuer Ereignis funktioniert
- [ ] Felduebernahme fuer Primärquelle funktioniert
- [ ] Felduebernahme fuer Beschreibung funktioniert
- [ ] Felduebernahme fuer Stichwoerter funktioniert
- [ ] Felduebernahme fuer Ort funktioniert
- [ ] Beschreibung wird mit `enthaelt u.a.` normalisiert
- [ ] Fundstellen koennen erneut angezeigt werden

## 10. OCR
- [ ] Bild-PDF ohne Text bietet OCR an
- [ ] OCR-Erzeugung laeuft durch
- [ ] OCR-Datei wird als verknuepfte Analysefassung genutzt
- [ ] OCR-Datei laesst sich oeffnen
- [ ] OCR-Begleitdatei bleibt verknuepft

## 11. PDF-Verwaltung
- [ ] `Uebersichten > PDF-Dateien...` laesst sich oeffnen
- [ ] Tabelle zeigt Arbeitsdatei, Pfad, Groessen und Begleitfassungen
- [ ] Ordnerfilter in der PDF-Uebersicht funktioniert
- [ ] Groessenfilter in der PDF-Uebersicht funktioniert
- [ ] Sortierung per Spaltenkopf funktioniert
- [ ] Rechtsklick auf PDF-Zeile zeigt passende Aktionen
- [ ] Arbeits-PDF oeffnen funktioniert
- [ ] OCR-Fassung oeffnen funktioniert
- [ ] PDF/A-Fassung oeffnen funktioniert
- [ ] Kopie speichern funktioniert
- [ ] `PDF optimieren...` startet
- [ ] Fortschrittsdialog erscheint
- [ ] Optimierung ersetzt Datei nur bei kleinerer Ausgabe
- [ ] Optimierung ohne Gewinn laesst Datei unveraendert
- [ ] Gesperrte PDF wird verstaendlich gemeldet
- [ ] `PDF/A erzeugen...` startet
- [ ] PDF/A wird bei vorhandenem Ghostscript erzeugt
- [ ] Fehlendes Ghostscript wird klar gemeldet
- [ ] `pdf_sizes.csv` wird geschrieben oder aktualisiert

## 12. Punkte und Sonderpunkte
- [ ] Punktestand laesst sich oeffnen
- [ ] Dokumentbezogene Punkte werden angezeigt
- [ ] Automatische Punkte wirken plausibel
- [ ] OpenAI-Punkte wirken plausibel
- [ ] Manuelle Korrektur aendert die Wertung korrekt
- [ ] Sonderpunkte koennen angelegt werden
- [ ] Sonderpunkte koennen bearbeitet werden
- [ ] Sonderpunkte koennen geloescht werden

## 13. Mail
- [ ] Mailbereich laesst sich oeffnen
- [ ] Rundmail laesst sich oeffnen
- [ ] Antwort-an ist vorbefuellt
- [ ] Empfaengerlisten und Verteiler werden korrekt geladen
- [ ] Bearbeiter sieht nur erlaubte Verteiler
- [ ] Admin/Superadmin sieht Admin-Verteiler
- [ ] Standard-Mail-Texte lassen sich laden
- [ ] Standard-Mail-Texte lassen sich speichern
- [ ] Versandart `Anlagen` funktioniert
- [ ] Nextcloud-Datei als Link-Versand funktioniert
- [ ] Normale Datei als Anhang funktioniert
- [ ] Echte Downloadlinks werden erzeugt
- [ ] Mailhistorie zeigt nur eigene Versandvorgaenge

## 14. Server, Update und Wartung
- [ ] Benutzerverwaltung laesst sich oeffnen
- [ ] Benutzer koennen angelegt und gespeichert werden
- [ ] Passwoerter bleiben maskiert
- [ ] Server-Backups koennen angezeigt werden
- [ ] Server-Backups koennen bereinigt werden
- [ ] Update-Dialog laesst sich oeffnen
- [ ] Datenbank-Reset ist im Produktivmodus gesperrt
- [ ] Test-Reset verlangt Sicherheitswort
- [ ] Wartungsmodus laesst sich setzen und beenden

## 15. Negativtests
- [ ] API kurz ungueltig oder nicht erreichbar machen
- [ ] Nextcloud-Ordner kurz nicht verfuegbar machen
- [ ] Nicht berechtigte Aktion als Bearbeiter versuchen
- [ ] Leere Pflichtfelder pruefen
- [ ] Sehr grosse PDF pruefen
- [ ] Datei extern loeschen oder umbenennen
- [ ] Fehlende OCR-/PDFA-Datei pruefen
- [ ] Ungueltigen OpenAI-Schluessel pruefen
- [ ] Gesperrte PDF optimieren versuchen

## 16. Abschluss
- [ ] Keine neuen Tracebacks in `app.log` oder `error.log`
- [ ] Keine stillen Datenverluste bemerkt
- [ ] Wichtige Realfaelle ohne Blocker durchgelaufen
- [ ] Offene Probleme dokumentiert

