# Ortschronisten-Datei-Verwaltung (ODV) v111

## Aktueller Projektstand

- Aktuelle App-Version laut `app/main.py`: `v111`
- Git-Repository ist initialisiert.
- Aktueller Hauptbranch: `main`
- Arbeitsweise: Vor Änderungen `git status --short` prüfen, relevante Dateien lesen, Änderungen gezielt umsetzen, danach sinnvoll testen.
- Dokumentationsregel: Alle künftigen Anpassungen in dieser `README.md` unter `Versionshistorie` dokumentieren.
- Bei neuer App-Version alle Versionsbezeichnungen passend anheben.
- Bei Korrekturen innerhalb einer bestehenden Version die Beschreibung direkt bei dieser Version ergänzen.
- Bearbeiterrelevante Änderungen zusätzlich in `Handbuch.md`, admin-/betriebsrelevante Änderungen zusätzlich in `Admin-Handbuch.md` fortschreiben.
- Commit-Regel: Wenn der Nutzer exakt `OK läuft` schreibt, wird der aktuelle sinnvolle Arbeitsstand geprüft und committed.
- Wichtig: Vorhandene Änderungen im Git-Workspace nicht zurücksetzen oder überschreiben.

## Wiederaufnahme-Text

Für die nächste Sitzung:

```text
Wir machen im ODV-Projekt weiter:
C:\ODV\Entwicklung

Bitte zuerst `git status --short` prüfen, dann die relevanten Dateien lesen.
Aktuelle App-Version laut README/Code: v111.
Alle künftigen Anpassungen bitte in README.md unter Versionshistorie dokumentieren.
Bearbeiterrelevante Änderungen bitte zusätzlich in Handbuch.md, Admin-/Betriebsthemen zusätzlich in Admin-Handbuch.md dokumentieren.
Bei neuer App-Version alle Versionsbezeichnungen anpassen; bei Korrekturen in einer bestehenden Version direkt dort ergänzen.
Wenn ich exakt `OK läuft` schreibe, bitte den aktuellen sinnvollen Stand committen.
Vorhandene Änderungen im Git-Workspace nicht zurücksetzen oder überschreiben.
```

## Build und Verteilung

Windows-Build:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Ergebnis:

```text
dist\ODV\ODV.exe
```

Für Verteilung und Updatepakete immer den gesamten Ordner `dist\ODV` verteilen oder als ZIP packen, nicht nur `ODV.exe`. Seit v70/v71 gehört auch `ODV_Updater.exe` zum Verteilordner.

Optionaler Onefile-Build aus älteren Paketen:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows_onefile.ps1
```

Onefile startet oft langsamer und wird von Virenscannern eher skeptisch bewertet. Für Tests und Verteilung ist der Ordner-Build robuster.

macOS-Build aus älteren Paketen:

```bash
chmod +x build_macos.sh
./build_macos.sh
```

Für Verteilung auf andere Macs sollte die App signiert/notarisiert werden.

## Server und Datenbank

- Produktive API-Datei grundsätzlich als `ortschronik-api/routes.php` hochladen.
- Für den aktuellen App-Stand sollte `server/routes.php` beziehungsweise die zur App passende `server/routes_vXX.php` verwendet werden.
- In der alten README stand zuletzt noch `server/routes_v81.php`; das ist historisch und muss vor einer echten Serveraktualisierung gegen den aktuellen Code geprüft werden.
- SQL-Migrationen nur bei Bedarf und passend zur Zielversion importieren.
- SQL-Ordnerstruktur: `sql/current`, `sql/migrations`, `sql/resets`, `sql/archive`.
- Vor MySQL-Tabellenaenderungen betroffene Tabellen mit vorheriger Versionsnummer kopieren, z. B. `documents_v104` vor einer Migration auf v105.
- Reset-Dateien löschen nur Bewegungs-/Testdaten, nicht Benutzer, Rollen/Rechte, Ortsordner, Punkteregeln, Verteiler, Systemeinstellungen oder Nextcloud-Dateien.

Wichtige SQL-/Reset-Hinweise aus den Versionsständen:

- `sql/migrations/schema_v48_points.sql`
- `sql/migrations/schema_v49_points_folder_scope.sql`
- `sql/migrations/schema_v51_point_rules_ui.sql`
- `sql/migrations/schema_v60_mail_history.sql`
- `sql/resets/reset_bewegungsdaten_v63.sql`
- `sql/resets/reset_bewegungsdaten_v64.sql`
- `sql/resets/reset_bewegungsdaten_v65.sql`
- `sql/migrations/schema_v68_maintenance_backup.sql`
- `sql/migrations/schema_v69_app_update.sql`
- `sql/migrations/schema_v74_sessions_devices_locks.sql`
- `sql/migrations/schema_v76_dragdrop_fileview.sql`
- `sql/migrations/schema_v77_fileview_status_search.sql`
- `sql/migrations/schema_v79_menu_manual_points.sql`
- `sql/migrations/schema_v80_ui_session_state.sql`
- `sql/migrations/schema_v81_ui_window_geometry_fix.sql`
- `sql/migrations/schema_v82_upload_form_layout.sql`

## Versionshistorie

### v111 - Punkteverwaltung optimiert

- Aktuelle App-Version laut `app/main.py`: `v111`.
- API-Version in `server/routes.php` auf `v111` angehoben.
- Punkteregeln-Dialog optimiert: Die Übersicht zeigt nur noch Regeln, die serverseitig wirklich ausgewertet werden; veraltete Regeln werden beim Speichern entfernt.
- Metadatenpunkte werden als Regel aus Metadatenfeld und Wertung gebildet, z. B. `copyright_author_manual` oder `copyright_author_openAI`.
- Metadatenregeln enthalten Prüftyp und Mindestwert: `characters`, `words`, `count` oder `none`.
- Metadatenpunkte vereinheitlicht: Manuell befüllte Metadatenfelder zählen standardmäßig 2 Punkte, durch OpenAI befüllte Metadatenfelder standardmäßig 1 Punkt; bei manueller Korrektur wird die OpenAI-Wertung für dieses Feld durch die manuelle Wertung ersetzt.
- Personenpunkte angepasst: Ein Bild mit Personenmarkierungen zählt 5 Punkte über `persons_image_marked`, zusätzlich zählt jede markierte Person 1 Punkt über `persons_per_person`.
- Sonderregeln und manuelle Zusatzpunkte werden in der Regelbasis mitgeführt; Sonderregeln bleiben systemseitig vorgegeben.
- Systemregel `transcription_document` ergänzt: Transkription von Zeitung, Akte oder Urkunde zählt 10 Punkte.
- Datenbankmigration `v111_point_rules_optimization` ergänzt; vor der Aktualisierung wird `point_rules` als `point_rules_v110` gesichert und die Tabelle um Regeltyp, Metadatenfeld, Wertung, Prüftyp, Mindestwert und Systemkennzeichen erweitert.
- Bearbeiter-Dokumentation als `Handbuch.md` und Admin-Dokumentation als `Admin-Handbuch.md` aus den bisherigen DOCX-Dokumenten übernommen und bis v111 fortgeschrieben.
- Beide Markdown-Handbücher haben ein verlinktes Inhaltsverzeichnis; die lokale Browser-Ansicht erzeugt passende Kapitelanker und klickbare interne Links.
- `Handbuch.md` und `Admin-Handbuch.md` fachlich neu und einheitlich strukturiert: Überblick, Arbeits-/Verwaltungsbereiche, Spezialthemen, Workflows, Checklisten/Fehlerbehebung und Fortschreibung.
- Hilfe-Menü ergänzt: `Handbuch` für alle Rollen, `Admin-Handbuch` nur für Admin/Superadmin; Markdown wird lokal als Browser-HTML geöffnet.
- Für Superadmins zeigt das Hilfe-Menü zusätzlich `Versionshistorie`; geöffnet wird die lokale `README.md` im Browser.
- Dokumentationsregel erweitert: Künftige fachliche Änderungen werden zusätzlich zur README auch in den passenden Handbuch-Dateien ergänzt.
- ODV-Updatefreigabe vereinfacht: Superadmins können ein fertiges Updatepaket auswählen; ODV kopiert es automatisch nach `02_AUSTAUSCH/ODV_UPDATE/Windows`, berechnet die SHA256-Prüfsumme und füllt Dateiname, Relativpfad und Hash im Freigabe-Dialog vor.
- Updatepakete sollen künftig einheitlich als `ODV_vXXX.zip` aus dem vollständigen `dist\ODV`-Ordner erstellt werden; eine spätere Automatisierung soll Build, ZIP-Erstellung, Kopie in den Updateordner, SHA256-Berechnung und Freigabevorbereitung bündeln.
- Geänderte Dateien: `app/main.py`, `app/config.py`, `server/routes.php`, `sql/migrations/schema_v111_point_rules_optimization.sql`, `README.md`, `Handbuch.md`, `Admin-Handbuch.md`, `scripts/docx_to_md.py`, `scripts/add_md_toc.py`

### v110 - Datenbankmenü und Backup-Rücksicherung

- Aktuelle App-Version laut `app/main.py`: `v110`.
- API-Version in `server/routes.php` auf `v110` angehoben.
- Untermenü `Admin > Datenbank` neu sortiert: Wartungsmodus/Datenbanksperre, Datenbankmigrationen, Datenbank zurücksetzen, danach getrennt Datenbank sichern und Backup zurücksichern.
- Klarstellung: `Datenbank zurücksetzen` löscht Bewegungs-/Testdaten und ist nicht identisch mit Backup-Rücksicherung.
- Neuer Menüpunkt `Backup zurücksichern...`.
- Neue API-Endpunkte `GET /api/admin/backups` und `POST /api/admin/restore-backup`.
- Vor einer Backup-Rücksicherung erstellt die API automatisch ein frisches Backup des aktuellen Stands.
- Rücksicherung akzeptiert nur serverseitige Backup-Dateien nach Muster `odv_db_backup_YYYY-MM-DD_HH-MM-SS.sql.gz` aus dem Backup-Ordner und verlangt den Bestätigungstext `BACKUP ZURUECKSICHERN`.
- Geänderte Dateien: `app/main.py`, `app/api_client.py`, `server/routes.php`, `README.md`

### v109 - Admin-Menü fachlich gegliedert

- Aktuelle App-Version laut `app/main.py`: `v109`.
- API-Version in `server/routes.php` auf `v109` angehoben.
- Superadmin-Menü `Admin` in fachliche Untermenüs gegliedert: Benutzerverwaltung, Stammdaten, Dateien, Datenbank, Server, Updates.
- Datenbankfunktionen sind nun gebündelt: sichern, Migrationen prüfen/ausführen, zurücksetzen, Wartungsmodus/Datenbanksperre.
- Serverfunktion `routes.php sichern/hochladen` liegt im Untermenü `Server`.
- Geänderte Dateien: `app/main.py`, `server/routes.php`, `README.md`

### v108 - Start-Hinweise und Systemstatus im Hilfe-Menü

- Aktuelle App-Version laut `app/main.py`: `v108`.
- API-Version in `server/routes.php` auf `v108` angehoben.
- Das bisherige automatische Systemstatus-Fenster beim Start wird nicht mehr angezeigt.
- Beim Start erscheint nur noch ein Hinweis, wenn Handlungsbedarf besteht: Server-`routes.php` nicht passend zur App-Version oder offene Datenbankmigrationen.
- Neuer Menüpunkt `Hilfe > Systemstatus...` zeigt den ausführlichen Betriebsstatus auf Wunsch.
- Der Systemstatus enthält zusätzlich die Anzahl offener Datenbankmigrationen.
- Geänderte Dateien: `app/main.py`, `server/routes.php`, `README.md`

### v107 - routes.php per FTP sichern und hochladen

- Aktuelle App-Version laut `app/main.py`: `v107`.
- API-Version in `server/routes.php` auf `v107` angehoben.
- Neuer Superadmin-Menüpunkt `Server-routes.php sichern/hochladen...`.
- ODV nutzt die in den Admin-Einstellungen gespeicherten FTP-Daten und das lokal per Windows-DPAPI verschluesselte FTP-Passwort.
- Vor dem Upload wird die vorhandene Server-Datei `routes.php` per FTP mit Zeitstempel und App-Version umbenannt, z. B. `routes_backup_v107_2026-05-31_15-30-00.php`.
- Danach wird die lokale Datei aus `ftp_local_routes_path`, standardmaessig `server/routes.php`, nach `ftp_remote_routes_path` hochgeladen.
- Datenbankanpassungen bleiben getrennt und laufen ueber `Admin > Datenbankmigrationen prüfen/ausführen...`.
- Geänderte Dateien: `app/main.py`, `app/config.py`, `server/routes.php`, `README.md`

### v106 - Serverseitige Datenbankmigrationen

- Aktuelle App-Version laut `app/main.py`: `v106`.
- API-Version in `server/routes.php` auf `v106` angehoben.
- Neuer Superadmin-Menüpunkt `Datenbankmigrationen prüfen/ausführen...`.
- Neuer API-Endpunkt `GET /api/admin/schema-migrations` zeigt offene serverseitige Migrationen, API-Version und letzte Datenbanksicherung.
- Neuer API-Endpunkt `POST /api/admin/schema-migrations/apply` erstellt zuerst automatisch eine vollständige Datenbanksicherung und führt danach bekannte Migrationen aus.
- Serverseitiges Migrationsprotokoll `odv_schema_migrations` ergänzt.
- SQL: `sql/migrations/schema_v106_schema_migrations.sql`
- Hilfsfunktion für künftige Tabellenänderungen ergänzt: Vor `ALTER TABLE` kann die betroffene Tabelle mit der vorherigen Versionsnummer kopiert werden, z. B. `documents_v105` vor einer Migration auf v106.
- Keine MySQL-Zugangsdaten im ODV-Client erforderlich; Migrationen laufen über die API mit vorhandener Server-Datenbankverbindung.
- Geänderte Dateien: `app/main.py`, `app/api_client.py`, `server/routes.php`, `sql/migrations/schema_v106_schema_migrations.sql`, `README.md`

### v105 - Admin-Einstellungen in Reitern

- Aktuelle App-Version laut `app/main.py`: `v105`.
- Superadmin-Dialog `Admin-Einstellungen` fachlich in Reiter gegliedert: Allgemein, API/OpenAI, FTP-Deployment, Links/Hinweise.
- Schließen des Dialogs fragt bei ungespeicherten Änderungen, ob gespeichert werden soll.
- Bewusste Entscheidung gegen automatisches Speichern beim Verlassen einzelner Felder, damit Admin-/Server-/FTP-/OpenAI-Werte erst nach ausdrücklicher Bestätigung übernommen werden.
- SQL-Ordner aufgeraeumt in `sql/current`, `sql/migrations`, `sql/resets`, `sql/archive`.
- Migrationsregel dokumentiert: Vor MySQL-Tabellenaenderungen wird die betroffene Tabelle mit der vorherigen Versionsnummer gesichert, z. B. `documents_v104` vor einer Migration auf v105.
- Geänderte Dateien: `app/main.py`, `README.md`, `sql/README.md`, `sql/*`

### v104 - FTP-Zugang und lokale Passwortverschlüsselung

- Aktuelle App-Version laut `app/main.py`: `v104`.
- In den Superadmin-Einstellungen gibt es FTP-Deployment-Felder fuer Server, Port, Benutzer, Zielpfad und Passwort.
- Das FTP-Passwort wird lokal per Windows-DPAPI verschluesselt in der ODV-Konfiguration gespeichert; es muss danach nicht erneut eingegeben werden.
- Ein vorhandenes gespeichertes FTP-Passwort bleibt erhalten, wenn das Passwortfeld beim Speichern leer bleibt.
- FTP-Verbindungstest aus den Admin-Einstellungen ergaenzt.
- Geplanter Server-Deploymentpfad fuer `routes.php`: FTP-Server `w0210fa6.kasserver.com`, Benutzer `f0185adc`, Port `21`, Zielpfad `/ortschronik.info/ortschronik-api/routes.php`, lokale Quelle `server/routes.php`.
- Verbindungstest am 31.05.2026: DNS loest auf `85.13.162.140` auf, TCP/FTP auf Port `21` ist erreichbar.
- Geänderte Dateien: `app/main.py`, `app/config.py`, `app/secure_store.py`, `README.md`

### v103

- Aktuelle App-Version laut `app/main.py`.
- Keine eigene alte README-Datei für v96-v103 im Projekt gefunden; Änderungen für diese Versionen müssen bei Bedarf aus Code, Git-Historie oder weiteren Notizen rekonstruiert werden.
- README-Arbeitsregel ergänzt: Künftige Anpassungen werden in der Versionshistorie dokumentiert; neue Versionen heben alle Versionsbezeichnungen an, Korrekturen werden bei der bestehenden Version beschrieben.
- Erster Verbindungstest am 31.05.2026: DNS loest auf `85.13.162.140` auf, TCP/SFTP auf Port `22` lief von dieser Umgebung in einen Timeout; spaeter als FTP/Port `21` korrigiert.

### v95 - Metadaten beim Dateiwechsel leeren

- Beim Auswählen eines neuen Dokuments werden fachliche Upload-Metadaten zurückgesetzt.
- Alte OpenAI-Vorschläge, Beschreibung, Bemerkung, Personenmarkierungen und OCR-Verknüpfung bleiben nicht am neuen Dokument hängen.
- Technische Felder wie Dateiname, Erfasser und Upload-Zeitpunkt werden danach wieder passend für die neue Datei gesetzt.
- Der Zielordner bleibt erhalten.
- Geänderte Dateien: `app/upload_tab.py`, `app/main.py`

### v94 - Rechteauswahl und OpenAI-Modellwahl

- Im Upload-Wizard ist `Rechte / Nutzung allgemein` wieder als feste Auswahl verfügbar.
- Die Auswahl enthält A/B/C/D-Rechtehinweise.
- In den Admin-Einstellungen wird das OpenAI-Modell per Auswahlfeld gewählt.
- Verfügbare Modelle: `gpt-4o-mini`, `gpt-4o`, `gpt-3.5-turbo`.
- Geänderte Dateien: `app/upload_wizard.py`, `app/main.py`

### v93 - OpenAI-Kosten, Ortsnamen und Formularfix

- OpenAI-Verbrauchsanzeige zeigt zusätzlich Kostenschätzung und freie Kontext-Tokens, soweit das Modell bekannt ist.
- Unterstützte Preisprofile: `gpt-3.5-turbo`, `gpt-4o-mini`, `gpt-4o`.
- Die lokale/OpenAI-Metadatenableitung achtet besonders auf Bedheim, Eicha, Gleicherwiesen, Gleichamberg, Hindfeld, Milz, Mendhausen, Roth, Haina, Römhild, Sülzdorf, Westenfeld, Zeilfeld, Mönchshof und Simmershausen.
- Erkannte Orte werden im Feld `Ort` ergänzt, ohne vorhandene Orte zu überschreiben.
- Überlappende Felder in Schritt 2 `Quelle / Rechte / Transkription` wurden korrigiert.
- Geänderte Dateien: `app/upload_tab.py`, `app/openai_client.py`, `app/upload_wizard.py`, `app/main.py`

### v92 - OCR-PDF automatisch neben Original speichern

- `PDF OCR erstellen` fragt nicht mehr nach einem Speicherort.
- OCR-PDF wird automatisch im gleichen Ordner wie das Original gespeichert.
- Dateiname: `Originalname_ocr.pdf`; bei Konflikten ergänzt ODV `_#1`, `_#2` usw.
- OCR-PDF wird danach direkt mit dem Original verknüpft.
- Geänderte Dateien: `app/upload_tab.py`, `app/main.py`

### v91 - OCR-Fortschrittsanzeige

- Während `PDF OCR erstellen` läuft, zeigt ODV im Upload-Reiter einen laufenden Fortschrittsbalken.
- Der Balken wird nach erfolgreicher OCR oder bei Fehlern automatisch ausgeblendet.
- Während OCR laufen, sind `PDF OCR erstellen` und `OpenAI prüfen` gesperrt.
- Geänderte Dateien: `app/upload_tab.py`, `app/main.py`

### v90 - OCR-Dateien im gleichen Ordner, aber ausgeblendet

- Verknüpfte OCR-PDFs bleiben im gleichen Ordner wie das Original.
- Beim automatischen Umbenennen/Verschieben wird die OCR-PDF parallel mitgeführt.
- OCR-Dateiname folgt dem Original mit Zusatz `_ocr.pdf`.
- In `Dateien anzeigen` und `Dateien bearbeiten` werden verknüpfte OCR-PDFs nicht als eigene Dokumente angezeigt.
- OCR-PDF bleibt über `OCR anzeigen` am Original erreichbar.
- Geänderte Datei: `app/main.py`

### v89 - OCR-PDF als verknüpfte Analysefassung

- `PDF OCR erstellen` ersetzt nicht mehr das Original und wählt nicht die OCR-Datei als Upload-Datei aus.
- Das Original bleibt Upload-/Archivdokument.
- OpenAI nutzt bei vorhandener OCR-Verknüpfung automatisch den Text der OCR-PDF.
- Beim Upload wird die OCR-PDF als verknüpfte Kopie neben dem Original gespeichert.
- OCR-Verknüpfung wird in den Metadaten gespeichert.
- Beim Umbenennen/Verschieben des Originals wird die OCR-PDF mitgeführt.
- In `Dateien anzeigen` gibt es `OCR anzeigen`, wenn eine OCR-PDF verknüpft ist.
- Geänderte Dateien: `app/upload_tab.py`, `app/main.py`, `app/models.py`, `requirements.txt`

### v88 - OCR-Fallback ohne Ghostscript

- `PDF OCR erstellen` nutzt OCRmyPDF, falls installiert.
- Wenn OCRmyPDF fehlt, nutzt ODV PyMuPDF plus Tesseract als lokalen Fallback.
- Tesseract wird auch gefunden, wenn es nicht im aktuellen Windows-PATH steht.
- Deutsche Tesseract-Sprachdaten liegen lokal unter `app/tessdata/deu.traineddata`.
- Geänderte Dateien: `app/upload_tab.py`, `app/main.py`, `app/tessdata/deu.traineddata`

### v87 - Bild-PDFs per OCR vorbereiten

- PDF-Dateien werden für die OpenAI-Vorprüfung lokal mit `pypdf` auf lesbaren Text geprüft.
- Bild-PDFs ohne auslesbaren Text erhalten eine gelbe OpenAI-Ampel mit OCR-Hinweis.
- Im Upload-Reiter gibt es `PDF OCR erstellen`.
- Wenn `ocrmypdf` mit Tesseract installiert ist, erzeugt ODV eine durchsuchbare PDF-Kopie.
- OpenAI-Aufruf erfolgt weiterhin erst nach Klick auf `OpenAI prüfen`.
- Geänderte Dateien: `app/upload_tab.py`, `app/main.py`

### v86 - OpenAI-Vorprüfung per Ampel

- Im Upload-Reiter gibt es eine lokale OpenAI-Ampel für die ausgewählte Datei.
- Grün: Text lokal lesbar und für Metadatenprüfung geeignet.
- Gelb: Prüfung möglich, aber eingeschränkt oder mit unklarem Archivbezug; vor dem API-Aufruf fragt ODV nach.
- Rot: Datei soll nicht an OpenAI gesendet werden; `OpenAI prüfen` wird gesperrt.
- Die Ampel arbeitet lokal und löst keinen OpenAI-Aufruf aus.
- Geänderte Dateien: `app/upload_tab.py`, `app/main.py`

### v85 - OpenAI-Metadaten aus DOCX

- DOCX-Dateien werden vor dem OpenAI-Check lokal als Textauszug gelesen.
- OpenAI erhält tatsächlichen Dokumentinhalt statt nur Dateiname/Dateiendung.
- Lokale Fallback-Ableitung für typische Niederschriften/Protokolle: Datum/Zeitraum, Ort, Ereignis, Stichwörter, Beschreibung, Quelle.
- `Metadaten übernehmen` wird aktiv, wenn OpenAI oder lokale Ableitung verwertbare Metadaten liefert.
- Datei auswählen löst weiterhin keinen API-Aufruf aus.
- Geänderte Dateien: `app/upload_tab.py`, `app/openai_client.py`, `app/main.py`

### v84 - OpenAI-Logik im Upload-Reiter

- Beim Auswählen einer Datei wird kein OpenAI-API-Aufruf ausgelöst.
- `OpenAI prüfen` löst die Prüfung bewusst manuell aus.
- Ein API-Aufruf erzeugt Dokumentbewertung und Metadatenvorschläge.
- `Metadaten übernehmen` wird nach erfolgreicher Prüfung automatisch aktiviert, wenn Vorschläge vorhanden sind.
- `Metadaten übernehmen` startet keinen zusätzlichen OpenAI-Aufruf.
- Geänderte Dateien: `app/upload_tab.py`, `app/openai_client.py`, `app/main.py`

### v82 - Uploadmaske und Layoutkorrekturen

- Upload-Metadatenmaske an `Dateien anzeigen` und `Dateien bearbeiten` angeglichen.
- Technische Felder sichtbar: Upload-ID, Dokumenttyp, Status, aktueller Dateiname, erfasst von, hochgeladen am.
- Felder, die erst beim Upload final entstehen, werden ausgegraut dargestellt.
- `Erfasst von` wird mit dem aktuell angemeldeten Benutzer vorbelegt und ist im Upload nicht änderbar.
- `Aktueller Dateiname` und `Hochgeladen am` werden bei Dateiauswahl bzw. Drag & Drop vorbelegt.
- Button `Baum...` in der Dateiansicht optisch vom Verzeichnis-Auswahlfeld abgesetzt.
- Server: `server/routes_v82.php`
- SQL: keine strukturelle Änderung; `sql/migrations/schema_v82_upload_form_layout.sql` enthält nur Hinweis.

### v81 - Fenstergeometrie-Fix

- Fenstergrößen und Fensterpositionen werden zuverlässig lokal gespeichert und beim nächsten Öffnen wiederhergestellt.
- Server: `server/routes_v81.php`
- SQL: keine Datenbankänderung; `sql/migrations/schema_v81_ui_window_geometry_fix.sql` enthält nur Hinweis.

### v80 - Fensterzustand und Sitzungsanzeige

- Lokales Speichern von Fenstergrößen und Fensterpositionen.
- Aktualisierung der ODV-Version in `Sitzungen und Geräte` nach Start/Login/API-Statusprüfung.
- Server: `server/routes_v80.php`
- SQL: `sql/migrations/schema_v80_ui_session_state.sql` enthält nur Hinweise; Tabellen stammen aus v74.

### v79 - Menüstruktur und manuelle Sonderpunkte

- Neues Hauptmenü `Punkte`: Mein Punktestand, Punkteübersicht, manuelle Sonderpunkte, Übersicht manueller Sonderpunkte, Punkteregeln, Nachberechnung, Einstellungen.
- Menü `Informationen` heißt `Mail`: Rundmail, Verteiler, Versandhistorie.
- Neues Menü `Übersichten`: Dokumentzugriffe, Sitzungen und Geräte, Backup-Status.
- Manuelle Sonderpunkte können ohne Dokumentbezug vergeben werden.
- Zeitaufwand in Stunden kann erfasst werden.
- Standardpunkte pro Stunde: 150, über Superadmin einstellbar.
- Eigene Tabelle `manual_special_points`.
- Server: `server/routes_v79.php`
- SQL: `sql/migrations/schema_v79_menu_manual_points.sql` oder `sql/migrations/schema_v78_ui_sources_search_mailrules.sql`
- Reset: `sql/resets/reset_bewegungsdaten_v79.sql`

### v77 - Dateiansicht, Suche, Dokumentstatus und Normierung

- Leserecht auf `00_ORTSCHRONIK` zeigt kompletten physischen Unterbaum rekursiv wie beim Superadmin.
- Dateinamenfilter mit normierter Suche; Trefferdateien und Ordner werden angezeigt.
- Systemdateien wie `desktop.ini`, `Thumbs.db`, `.DS_Store`, temporäre Dateien und `ODV_UPDATE` werden ausgeblendet.
- Dateinamen-Normierung reduziert Mehrfachsegmente wie `milz_milz`.
- `Neuer Status` heißt `Dokumentstatus`.
- Punktebereich in `Dateien bearbeiten` optisch abgesetzt.
- Status `archiviert`, `abgelehnt`, `geloescht` verschiebt Dateien in Archiv-/Papierkorb-Ordner.
- Reaktivierung über Status `erfasst` versucht, Datei an ursprünglichen Pfad zurückzuschieben.
- Server: `server/routes_v77.php`
- SQL: `sql/migrations/schema_v77_fileview_status_search.sql`
- Reset: `sql/resets/reset_bewegungsdaten_v77.sql`

### v76 - Dateiansicht, Metadatenrechte und Drag & Drop

- ODV-Hauptordner werden auch unter Sammelordnern wie `Ortschronisten_Gemeinsam` erkannt.
- Leserecht auf `00_ORTSCHRONIK` zeigt kompletten physischen Unterbaum rekursiv.
- `ODV_UPDATE` bleibt aus Zielordner- und Dateibäumen ausgeblendet.
- Metadatenrechte: Admin/Superadmin dürfen bearbeiten; Bearbeiter bei Ordnerschreibrecht oder eigener erfasster Datei; fehlt `Erfasst von`, reicht Ordnerschreibrecht.
- Drag & Drop einer Datei aus dem Explorer in den Upload-Reiter möglich; Upload erfolgt erst per Button.
- Server: `server/routes_v76.php`
- SQL: `sql/migrations/schema_v76_dragdrop_fileview.sql`
- Reset: `sql/resets/reset_bewegungsdaten_v76.sql`

### v75 - Dateiansicht und Metadatenrechte

- `00_ORTSCHRONIK` wird in `Dateien anzeigen` für Bearbeiter, Admins und Superadmins rekursiv angezeigt.
- Tiefe Ordner unter `00_ORTSCHRONIK` sollen für Bearbeiter/Ortschronisten aufklappbar sein.
- `ODV_UPDATE` bleibt in normalen Bäumen und Auswahllisten ausgeblendet.
- Metadaten in `Dateien anzeigen` sind bearbeitbar bei Ordnerschreibrecht, eigener erfasster Datei oder Admin/Superadmin.
- Wenn kein `Erfasst von` hinterlegt ist, dürfen nur Admin/Superadmin Metadaten bearbeiten.
- Server: `server/routes_v75.php`
- Keine neue SQL-Struktur.

### v74 - Sitzungen, Geräte und Bearbeitungssperren

- Geräte-ID je lokaler Installation.
- Geräteinformationen beim Login.
- Mail an Superadmins bei Login von neuem Gerät.
- Superadmin-Dialog `Sitzungen und Geräte...`.
- Sitzung beenden, Gerät sperren/freigeben, Hinweis bei Mehrfachlogin.
- Dokument-Bearbeitungssperre gegen parallele Metadatenänderungen.
- Neue Geräte werden nicht blockiert; Superadmins können auffällige Geräte sperren.
- Server: `server/routes_v74.php`
- SQL: `sql/migrations/schema_v74_sessions_devices_locks.sql`; API legt Tabellen defensiv selbst an, wenn möglich.

### v72 - Konsolidierter Produktivtest-Stand

- Konsolidiert funktionierende v70/v71-Updater-Fixes.
- Komfort-Updater mit sichtbarem Fortschrittsfenster, Einzelinstanz-Sperre und Schutz gegen Update-Endlosschleifen.
- Verbesserte Wartungsmodus-Warnung für Superadmins direkt nach Aktivierung.
- `ODV_UPDATE` wird in normalen Zielordner- und Dateibaum-Auswahlen ausgeblendet.
- Mail-Historie über `Informationen > Versandhistorie...`.
- Papierkorb-Logik: Status `geloescht` statt hartem Löschen; Standardlisten blenden gelöschte Dokumente aus.
- Dokumentation zur Updatefreigabe für Superadmins ergänzt.
- Server: `server/routes_v72.php`

### v71 - Komfort-Updater Buildfix 3

- Komfort-Updater beendet die alte ODV hart nach dem Start des Updaters, damit Dateien nicht gesperrt bleiben.
- Neu gestartete ODV bekommt einmalig `--odv-skip-update-check-once`, damit keine Update-Endlosschleife entsteht.
- Updater schreibt `last_update_result.json` unter `%LOCALAPPDATA%\ODV\updates`.
- Server: `server/routes_v71.php`

### v70 - Komfort-Updater über Nextcloud

- Neue mitzuliefernde `ODV_Updater.exe`.
- ODV erkennt freigegebene Updates über die API.
- Updatepaket wird aus lokalem Nextcloud-Updateordner kopiert und entpackt.
- ODV startet den Updater und beendet sich selbst.
- Updater ersetzt den Programmordner und startet `ODV.exe` neu.
- Laufende `ODV.exe` wird nicht von sich selbst überschrieben.
- Server: `server/routes_v70.php`

### v69 - Updateverwaltung über Nextcloud

- Superadmins können unter `Admin > ODV-Updatefreigabe verwalten...` freigegebene Versionen hinterlegen.
- Felder: Version, Dateiname, Nextcloud-Relativpfad, optionale SHA256-Prüfsumme, Pflichtupdate, Release-Hinweise.
- App prüft beim Start und über `Hilfe > Nach ODV-Update suchen...` auf neuere Versionen.
- Neue Version wird aus dem lokalen Nextcloud-Updateordner nach `%LOCALAPPDATA%\ODV\versions\vXX` kopiert und ZIP-Dateien werden entpackt.
- Komfort-Updater war noch späterer Ausbauschritt.
- Server: `server/routes_v69.php`
- SQL: `sql/migrations/schema_v69_app_update.sql`
- Reset: `sql/resets/reset_bewegungsdaten_v69.sql`
- Zusatzdoku: `docs/V69_AENDERUNGEN.md`

### v68 - Wartungsmodus, Datenbanksicherung und Systemprüfung

- Superadmin-Menü `Datenbank sichern...` erzeugt serverseitig komprimierte SQL-Sicherung.
- `Backup-Status anzeigen...` zeigt Zeitpunkt, Datei, Größe und Warnung bei Sicherungen älter als 48 Stunden.
- `Wartungsmodus / Datenbanksperre...` mit frei wählbarer Vorlaufzeit.
- Superadmins bleiben zugriffsberechtigt, erhalten aber Warn-/Statushinweise.
- Admins und Ortschronisten werden bei aktivem Wartungsmodus blockiert; neue Logins werden abgewiesen.
- `/api/status` liefert `api_version`, Zeit und Wartungsstatus.
- App prüft Startzustand: API, Version, Nextcloud-Stammverzeichnis, Token, Wartungsstatus.
- Statusleiste weist auf abweichende Server-/App-Versionen hin.
- Backups liegen standardmäßig serverseitig unter `odv_backup/backups` neben dem API-Verzeichnis und sollten geschützt werden.
- Rücksicherung bleibt manuell über KAS/phpMyAdmin.
- Server: `server/routes_v68.php`
- SQL: `sql/migrations/schema_v68_maintenance_backup.sql`
- Reset: `sql/resets/reset_bewegungsdaten_v68.sql`

### v67 - Stammdatenblatt, Zugriffsprotokoll und Download

- Störende Überlagerung im Metadatenbereich von `Dateien anzeigen` beseitigt.
- Rechtsklick auf Dateien in `Dateien anzeigen` und `Dateien bearbeiten`: öffnen, Download/Kopie speichern, bei Bildern mit Personen Stammdatenblatt als PDF.
- Download/Kopie speichert in frei wählbares Zielverzeichnis, standardmäßig Downloads.
- Öffnen und Download/Kopie von ODV-Dokumenten werden über API in `document_history` protokolliert.
- `Auswertungen > Dokumentzugriffe` zeigt Öffnen/Download mit Benutzer, Zeit, Datei und Details.
- Stammdatenblatt als A4-PDF: obere Hälfte Bild mit Nummern, untere Hälfte Personenliste und wichtigste Dateidaten.
- Server: `server/routes_v67.php`
- API: `POST /api/documents/{upload_id}/access-log`, `GET /api/document-access-log`
- Keine separate Schema-Aktualisierung erforderlich.

### v66 - Erfasst-von und Rundmail-Linkautomatik

- In `Dateien anzeigen` ist `Erfasst von` für Admins wie in `Dateien bearbeiten` als Auswahlliste änderbar.
- Änderungen an `Erfasst von` werden über API gespeichert.
- Automatische Punkte werden serverseitig auf neu zugeordneten Benutzer übertragen.
- Bei neu erfassten vorhandenen Dateien kann der erfassende/zugeordnete Benutzer direkt gesetzt werden.
- Beim Rundmail-Direktversand mit Versandart `Nextcloud-Downloadlink versenden` werden fehlende Downloadlinks automatisch erzeugt.
- `Downloadlinks erzeugen` bleibt als Vorschau-/Prüffunktion erhalten.
- Server: `server/routes_v66.php`

### v65 - Nachträglich erfasste Dateien, Rundmail ohne Anlage und UI

- Physisch vorhandene Dateien werden erst in ODV/MySQL übernommen, wenn Metadaten gespeichert werden.
- Anzeigen, Vorschau oder Öffnen erzeugt keinen Dokumentdatensatz.
- Nachträglich erfasste vorhandene Dateien erhalten Status `erfasst` statt `hochgeladen`.
- Historie: `Vorhandene Nextcloud-Datei in ODV erfasst`.
- Nachträglich erfasste vorhandene Dateien erscheinen in `Dateien bearbeiten` nur in ODV-Hauptbereichen.
- Bereits durch Admin erfasste Dateien werden nicht erneut als Admin-Bearbeitungsfall angezeigt.
- `Hochgeladen von` heißt an Metadatenstellen `Erfasst von`.
- Admins können `Erfasst von` per Auswahlliste ändern; automatische Punkte werden neu zugeordnet.
- Layout: Block `Rechte` steht auf gleicher Höhe wie `Zeit / Ort / Inhalt`.
- Rundmail: neue Standard-Versandart `Keine Anlage`.
- Rundmail verlangt nur bei Downloadlink oder Dokumentanlage eine ausgewählte Datei.
- Server/API akzeptiert neuen Status `erfasst`.
- Server: `server/routes_v65.php`
- Reset: `sql/resets/reset_bewegungsdaten_v65.sql`

### v64 - Physisch vorhandene Dateien rekursiv anzeigen

- `Dateien anzeigen` durchsucht den ausgewählten Ordner ohne künstliche Tiefenbegrenzung rekursiv.
- Dateien ohne ODV-Metadaten werden mit normalem Dateinamen angezeigt.
- Doppelklick öffnet auch solche Dateien mit dem Standardprogramm.
- Beim Speichern von Metadaten zu physisch vorhandener Datei wird diese als ODV-Dokument in MySQL angelegt, ohne erneut kopiert zu werden.
- Punkte nur für Dateien in `00_ORTSCHRONIK`, `01_ABLAGE_ORTSCHRONIK` oder `06_ARBEIT_DER_ORTSCHRONISTEN`.
- Sonderpunkte: `Kinder wie die Zeit vergeht` neu 100 Punkte, nachträglich 20; Jahresblätter neu 50, nachträglich 10.
- Server: `server/routes_v64.php`
- Reset: `sql/resets/reset_bewegungsdaten_v64.sql`
- Buildfix: `pyinstaller==6.11.1`, `pyinstaller-hooks-contrib==2024.10`, PyInstaller-Aufruf über `python -m PyInstaller`; bei Long-Path-Fehler Projektordner kurz halten oder Windows Long Path Support aktivieren.

### v63

- Server: `server/routes_v63.php`
- Optionaler Testreset: `sql/resets/reset_bewegungsdaten_v63.sql`

### v62 - Robuste Dateiauflösung / Dateiendungen

- Lokale Dateiauflösung in `Dateien bearbeiten` ist robuster.
- Datensätze mit fehlender oder ersetzter Dateiendung werden toleranter gefunden, z. B. `datei_jpg`, `datei_jpg.jpg`, `datei.jpg`.
- Wenn gespeicherter Pfad eines anderen Benutzers nicht passt, sucht ODV im eigenen Nextcloud-Stammverzeichnis nach Namensvarianten.
- Dateinamen-Normierung bereinigt Altfälle wie `_jpg` vor echter Endung.
- Keine SQL-Änderung.

### v61 - Punkte/Bearbeiter-Feinschliff

- Punkte bei Selbst-Löschung eigener punkteauslösender Eingaben werden entfernt.
- Admin-Korrekturen löschen Punkte des ursprünglichen Bearbeiters nicht.
- Korrektur-/Ergänzungspunkt ab mehr als 10 Zeichen Änderung.
- `Mein Punktestand` zeigt für Admins Auswahlfeld zur Einsicht fremder Punktekonten.
- Vorläufige Punkte für noch nicht übernommene Dokumente werden angezeigt.
- Doppelklick im Punktekonto öffnet Dokument in `Dateien bearbeiten`.
- Admin kann `Hochgeladen von` per Auswahlfeld ändern.
- Bei Änderung des Hochladers werden automatische Punkte des bisherigen Hochladers auf den neuen übertragen.
- Server: `server/routes_v61.php`
- Keine SQL-Migration, sofern v48/v49/v51/v55/v60 eingespielt sind.

### v60 - Reset, Mailhistorie und Upload-Layout

- Upload-Reiter kompakter zweispaltig angeordnet.
- Superadmin-Menü `Admin > Datenbank zurücksetzen...` löscht nur Bewegungs-/Testdaten und optional Mail-Historie.
- Nextcloud-Dateien werden nicht gelöscht.
- Beim Import vorhandener Dateien kann Superadmin auswählen, von wem Dateien sind.
- Mail-Versandhistorie: pro Empfänger wird gespeichert, welche Rundmail versendet wurde.
- Menü `Informationen > Versandhistorie...` für Admin/Superadmin.
- Server: `server/routes_v60.php`
- SQL optional/empfohlen: `sql/migrations/schema_v60_mail_history.sql`; Route legt Tabelle bei Bedarf automatisch an.

### v59 - Punkte-Schwellen für Beschreibung und Stichwörter

- Punkte für `Aussagekräftige Beschreibung` erst ab 50 Zeichen.
- Live-Zeichenzähler beim Feld `Beschreibung`.
- Punkte für `Stichwörter` erst ab mindestens 3 Stichwörtern.
- Stichwörter durch Komma oder Semikolon getrennt.
- Hinweise direkt unter passenden Feldern.
- Regeln gelten bei neuer Punktevergabe und Nachberechnung.
- Server: `server/routes_v59.php`
- Keine neue SQL-Migration.

### v58/v59 - Login-Startfix 2

- README-Datei `README_V58.md` trägt im Titel v59.
- Ohne gültige Anmeldung wird das Hauptfenster selbst als Loginfenster genutzt.
- Kein leeres Hauptfenster ohne sichtbaren Login-Dialog.
- Erst nach erfolgreicher Anmeldung wird die eigentliche Oberfläche aufgebaut.
- Wird Anmeldung beim Start abgebrochen, beendet sich die Anwendung sauber.
- Keine SQL-Änderung.

### v57 - Login-Startfix

- Beim Programmstart wird Loginfenster zwingend angezeigt, wenn kein gültiger API-Token/Benutzer geladen werden kann.
- Loginfenster wird unter Windows in den Vordergrund gehoben und kurzzeitig topmost gesetzt.
- Wird Login beim Programmstart abgebrochen, beendet sich die Anwendung sauber.
- Korrekturen aus v56 enthalten.
- Keine SQL-Änderung.

### v56 - Login- und Transkriptionslayout-Fix

- Benutzerwechsel ist abbruchsicher; bisheriger Benutzer bleibt angemeldet, wenn Dialog geschlossen oder abgebrochen wird.
- Alter API-Token wird erst nach erfolgreichem neuem Login abgemeldet.
- Transkriptionsfelder kompakter: `Transkription`, `Art`, `Transkriptionshinweis`.
- Layout in `Dateien hochladen` und `Dateien bearbeiten` umgesetzt.
- Kollisionen zwischen Transkriptionshinweis und Rechte-Bereich beseitigt.
- Server: `server/routes_v56.php` entspricht v55-Route mit Nachberechnungs-Fix.
- Keine neue SQL-Migration.

### v54 - Bearbeiter-Bearbeitung und UI-Aufräumung

- Normale Bearbeiter sehen `Dateien bearbeiten` und können eigene, noch nicht übernommene Dokumente ergänzen.
- Aktionsbereich heißt für normale Bearbeiter `Aktionen`; Admin-/Superadmin-Funktionen bleiben ausgeblendet.
- Bearbeiter dürfen Metadaten und Dateinamen eigener, noch nicht übernommener Dokumente ändern, aber nicht Status oder Zielordner.
- Sonderpunkte bleiben Admin/Superadmin vorbehalten.
- `Ausgewählte PDFs zusammenfassen...` oberhalb der Liste in Status-Zeile.
- `Punkte für Bearbeitungsliste nachtragen...` nur noch im Admin-Menü für Superadmins.
- Dokumenttyp in Upload und Bearbeitung als Auswahlfeld; neue erkannte Typen werden automatisch ergänzt.
- Server schützt zusätzlich gegen Bearbeitung übernommener Dokumente und Verschieben durch normale Bearbeiter.
- Server: `server/routes_v54.php`
- Keine zusätzliche SQL-Migration, wenn v48/v49/v51 eingespielt sind.

### v53 - UI-Korrektur Stichwörter-Hinweis

- Hinweis zur Eingabe von Stichwörtern wurde im Uploadformular direkt unter dem Feld `Stichwörter` positioniert.
- Keine SQL-Migration und keine Serveränderung.
- Alte README enthielt zusätzlich lose Testzeilen `j` und `jg`; diese wurden hier nicht als Projekthinweis übernommen.

### v51 - Metadaten- und Sonderpunkte-Feinschliff

- `Transkription erstellt` ist ein Kontrollkästchen.
- `Transkriptionsart` ist eine schmale Auswahlliste.
- `Rechte / Nutzung allgemein` ist eine schmale Auswahlliste mit A/B/C/D.
- Stichwörter sollen durch Komma oder Semikolon getrennt werden.
- Sonderpunkte können im Dialog aus verwaltbaren Punkteregeln gewählt werden; Punktzahl überschreibbar, Begründung Pflicht.
- SQL: `sql/migrations/schema_v51_point_rules_ui.sql`
- Server: `server/routes_v51.php` entspricht funktional v50.

### v50 - Punktestand, Ranking und direkte Sonderpunkte

- Angemeldete Benutzer sehen unter `Auswertungen > Mein Punktestand...` ihren eigenen Punktestand.
- Angezeigt werden Jahrespunkte, Rangposition, Teilnehmendenzahl und eigene Punkteereignisse.
- Admins/Superadmins behalten vollständige Beitragsauswertung.
- `Dateien bearbeiten` zeigt Punktesumme zum ausgewählten Dokument.
- Sonderpunkte direkt in `Dateien bearbeiten` erfassbar.
- API: `GET /api/points/me?year=YYYY`
- Server: `server/routes_v50.php`
- Keine zusätzliche SQL-Migration gegenüber v49.

### v49 - Punkte nur für zentrale Arbeitsordner

- Punkte nur für Dokumente, die ursprünglich in zentrale Arbeits-/Ablagebereiche hochgeladen wurden:
  - `01_ABLAGE_ORTSCHRONIK`
  - `06_UNSERE_ARBEITEN`
  - kompatibel: `06_ARBEIT_DER_ORTSCHRONISTEN`, `06_ARBEITEN_DER_ORTSCHRONISTEN`
- Uploads in eigene Ortsordner erhalten keine Punkte.
- `documents.points_eligible` wird beim Anlegen gespeichert, auch wenn Admin später verschiebt.
- Vorhandene Dokumente werden anhand `target_folder` und `current_path` nachklassifiziert.
- SQL: erst `sql/migrations/schema_v48_points.sql`, dann `sql/migrations/schema_v49_points_folder_scope.sql`
- Server: `server/routes_v49.php`

### v48 - Beitrags- und Punkteverwaltung

- Neue Metadatenfelder: Stichwörter, Transkription erstellt, Transkriptionsart, Transkriptionshinweis.
- Automatische Punkte für verwertbare Erschließungsarbeit, nicht für bloßes Hochladen.
- Punkte gehen an angemeldeten Bearbeiter der jeweiligen Leistung.
- Punkte bei Erstbefüllung wichtiger Felder: Beschreibung, Stichwörter, Quelle, Rechte, Archivsignatur, Datum, Ereignis, Transkription.
- Personenpunkte bei Personenzuordnung.
- Admin-Punkte für Übernahme sowie Umbenennen/Verschieben.
- Manuelle Sonderpunkte mit Begründung.
- Punkteregeln je Kalenderjahr verwaltbar.
- Beitragsauswertung mit CSV-Export.
- SQL: `sql/migrations/schema_v48_points.sql`
- Server: `server/routes_v48.php`
- Bereits vergebene Punkte behalten gespeicherten Wert; Regeländerungen gelten praktisch für zukünftige Punkteereignisse.

### v45/v43 - Umbenennung und Startbildschirm

- Startbildschirm mit Logo der Ortschronisten ergänzt.
- Anwendung in `Ortschronisten-Datei-Verwaltung (ODV)` umbenannt.
- Build-Ergebnis: `dist\ODV\ODV.exe`
- Einzel-EXE: `dist\ODV.exe`
- macOS-Ergebnis: `dist/ODV.app`

### v42 - Buildpaket

- Enthielt Skripte zur Erstellung einer Windows-EXE beziehungsweise macOS-App.
- Voraussetzungen Windows: Windows 10/11, Python 3.11 oder neuer, Python mit `Add Python to PATH`.
- Windows-Ordner-Build über `build_windows.ps1`.
- Historisches Ergebnis: `dist\OrtschronikUploader\OrtschronikUploader.exe`
- Optionaler Installer mit Inno Setup über `installer\windows\OrtschronikUploader.iss`.
- Server: API muss passend aktuell sein; für v42 keine neue Migration nötig, wenn v40/v41 bereits eingespielt.

### v22 - API-Datenfluss

- Server-API für Dashboard, Admin-Dateiliste, Metadatenänderungen, Statusänderungen und Personenzuordnungen.
- JSON-Dateien werden weiterhin als Sicherung erzeugt und aktualisiert.

### v21 - Schutz gegen Selbst-Deaktivierung

- Aktuell angemeldeter Benutzer kann sich nicht selbst über `Benutzer aktiv` deaktivieren.
- Button `Benutzer deaktivieren` ebenfalls gegen Selbst-Deaktivierung geschützt.

### v20 - Benutzerverwaltung über API/MySQL

- Benutzerverwaltung der Desktop-App vollständig an Server-API/MySQL angebunden.
- Benutzerliste über `GET /api/users`.
- Benutzeranlage über `POST /api/users`.
- Benutzeränderung/Deaktivierung über `PUT /api/users/{id}`.
- Lokale `users.json` wird für zentrale Benutzerverwaltung nicht mehr verwendet.

### v19 - API-Testbetrieb

- Benutzer melden sich über die Ortschronik-API an.
- Neue Upload-Metadaten werden zusätzlich zur lokalen JSON-Sicherungsdatei in MySQL/MariaDB gespeichert.
- Standard-API-URL: `https://ortschronik.info/api`
- Token wird lokal gespeichert und beim nächsten Start wiederverwendet.
- Upload kopiert Datei weiterhin lokal in den Nextcloud-Sync-Ordner.
- JSON-Begleitdatei weiterhin im zentralen Metadatenordner.
- Metadaten über `POST /api/documents`.
- Personenmarkierungen über `PUT /api/documents/{upload_id}/persons`.
- Benutzerverwaltung in der Oberfläche war damals noch alte lokale Verwaltung; API-Endpunkte existierten bereits.

### v9 - Lokaler Prototyp

Start:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

- Dateiansicht umgebaut: links Dateibaum, rechts Vorschau über Metadaten.
- Metadaten werden in der Dateiansicht aus JSON-Datei angezeigt.
- Metadaten nur bearbeitbar, wenn im Verzeichnis der Datei Schreibrecht besteht.
- Admin-Bearbeitung zeigt vollständige JSON-Daten inklusive Historie.
- Admin-Umbenennen/Verschieben normiert Dateinamen automatisch:
  - Datum/Zeitraum aus Metadaten als Präfix, sonst Hochladedatum
  - Kleinschreibung
  - Leerzeichen zu `_`
  - `ä/ö/ü/ß` zu `ae/oe/ue/ss`
  - unzulässige Sonderzeichen bereinigt
  - bei vorhandener Zieldatei automatisch `_#1`, `_#2` usw.
- In Admin-Einstellungen festgelegter Metadatenordnername wird konsequent verwendet.
- Superadmin-Testversion meldete automatisch an:
  - Name: Henri Eppler
  - Benutzername: `henri.eppler`
  - Rolle: Superadmin
  - Ort: Milz

## Projektordner

- Aktive Entwicklung: `C:\ODV\Entwicklung`
- Alte Projektstände und Buildpakete: `C:\ODV\Archiv`
- Die historischen `README*.md`-Dateien wurden in diese zentrale `README.md` übernommen und danach entfernt.
