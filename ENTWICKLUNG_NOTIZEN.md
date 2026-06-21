# Entwicklungsnotizen ODV

Dokumentation von Arbeitsschritten, Bugs, Fixes und Wiederaufnahmepunkten für Rechner-übergreifendes Arbeiten.

## Git-Workflow (festgelegt)

### Bei Fertigstellung eines Arbeitstags
```powershell
git add .
git status   # optional zur Kontrolle vor Commit
git commit -m "Beschreibung"
git push    # erst dann ist der Stand auf allen Rechnern verfügbar
git status --short --branch
```

### Bei Wiederaufnahme der Arbeit am anderen Rechner
```powershell
git pull
git status
```

### Abkürzung für den Chat: „fertig für heute“
Wenn du mir jetzt „fertig für heute“ schreibst, führe ich als Nächstes aus:
1. `git status` (prüfen, was lokal geändert wurde)
2. `git add .`
3. `git commit -m "<kurze tägliche Zusammenfassung>"`
4. `git push`
5. `git status --short --branch` (warten bis `main` nicht mehr voraus ist: `[ahead 0]`)
6. Ergebnis vermerken, wenn `git push` nicht erfolgreich war (z. B. wegen Netzwerk/Authentifizierung), damit wir es im nächsten Schritt zuerst nachholen.

Danach solltest du auf dem anderen Rechner `weiter gehts heute` sagen, damit wir mit einem synchronen Stand weitermachen.

## 2026-06-10

### Morgen-Check (Schnellstart nach Rechnerwechsel)
- Remote prüfen: `git remote -v`, `git pull`, `git status`.
- Erwarteter Zielstand: Branch `main` trackt `origin/main`; lokale Änderungen prüfen und gezielt fortfahren.

### Was heute auf diesem Rechner umgesetzt wurde
- Remote und Branch-Sync repariert: `git remote add origin https://github.com/henrieppler-source/ODV.git`, `git fetch origin`, `git branch --set-upstream-to=origin/main main`, `git pull --rebase origin main` (wegen divergierender Historie).
- Vor dem Abschluss wurden ausgeführt: `python scripts/check_project_health.py` (OK), `python scripts/smoke_upload_tab.py` (OK).
- UI/Workflow-Fehlerquelle behoben: OpenAI-Blocker-Text und Precheck-Flow auf Reiter „Dateien hochladen“, letzter standender Commit `e786721`.
- Bestehende Folgefehler dokumentiert und lokal adressiert: VS Code Interpreter Pfadfehler sowie Freeze beim Nextcloud-Basisordner-Scan in großen Verzeichnissen.

### Gefixte Einträge
- Python-Interpreter: `settings`-Pfad auf `${workspaceFolder}` konnte nicht aufgelöst werden; `.venv` neu aufgebaut; absoluter Interpreter-Pfad gesetzt auf `c:\\ODV\\Entwicklung\\.venv\\Scripts\\python.exe`; Begleitänderung dokumentiert in `ad969a9`.
- Nextcloud-Scan UI-Blockade: Ursache war synchroner Scan in `find_writable_folders()`, nun asynchron bei allen relevanten Aufrufen. Geänderte Dateien: `app/config_folders.py`, `app/masterdata_manager.py`, `app/session_manager.py`.

### Offene Punkte aus 06-10 (bei der nächsten Sitzung zuerst prüfen)
- Endgültige Klärung der offenen UI-Performance im Upload-/Metadaten-Flow nach dem letzten Rollback.
- Weitere Refactor-Slices in großen Modulen noch offen: `mail_manager.py`, `upload_tab.py`.
- Tests nach jedem Refactor-Slice ausführen: `python scripts/check_project_health.py` und relevante Smoke-Pfade für betroffene Bereiche.

### 06-10 Schlussstatus
- Lokale Notizen aktuell: `ENTWICKLUNG_NOTIZEN.md` erweitert und als Leitfaden bereit
- Erwarteter nächster Wiederaufnahmepunkt: auf funktionale Stabilität in `upload` und Admin-Workflows fokussieren

### Vor dem Test: fertig / offen

#### Fertig
- Remote und Branch-Sync repariert.
- Python-Interpreter-Pfad bereinigt und `.venv` wieder lauffähig.
- OpenAI-Blocker-Text und Precheck-Flow im Reiter `Dateien hochladen` behoben.
- Nextcloud-Basisordner-Scan auf asynchron umgestellt, damit die UI nicht mehr blockiert.
- Upload-/Metadaten-Flow im Reiter `Dateien hochladen` mit Cache für OCR-Pfad und Textauszüge entlastet.
- Erste Mail-Manager-Zerlegung begonnen: Historien-Datenaufbereitung in Hilfsmodul ausgelagert.
- Versanddialog als eigener Helper ausgelagert und per Smoke getestet.
- Erste Postprocess-Zerlegung begonnen: die gemeinsame OpenAI-Dialogschicht liegt jetzt in `app/postprocess_dialog_utils.py`.
- OpenAI-Dokument-Slice als nächster Schritt ausgelagert: Modellwahl, feldweise Übernahme und Speicherlogik liegen jetzt in `app/postprocess_openai_document_utils.py`.
- OpenAI-Form- und Persistenzblock ausgelagert: Feldwerte, Speichern, Tabellenzeilen und Aktionslogik liegen jetzt in `app/postprocess_openai_form_utils.py`.
- Ortsanalyse-Slice direkt danach ausgelagert: Fundstellensuche, Fundstellen-Dialog und Ergebnisdialog liegen jetzt in `app/postprocess_place_scan_utils.py`.
- OCR-Slice ebenfalls ausgelagert: die beiden OCR-Einstiege liegen jetzt in `app/postprocess_ocr_utils.py`.
- OpenAI-/OCR-/Ortsanalyse-Statuslogik ausgelagert: `update_admin_openai_controls()` liegt jetzt in `app/postprocess_control_utils.py`.
- Upload-Dateiauswahl- und Lade-Workflow ausgelagert: die Datei-Initialisierung liegt jetzt in `app/upload_file_selection_utils.py`.
- Upload-OCR-Block ausgelagert: OCR-Start, Fortschritt und Backend-Auswahl liegen jetzt in `app/upload_ocr_utils.py`.
- Upload-Textauszug- und Metadatenblock ausgelagert: Textprobe, lokale Ableitung und Metadatenhilfen liegen jetzt in `app/upload_text_utils.py`.
- OpenAI-Precheck-, Modellwahl- und Übernahmedialog ausgelagert: die UI- und Laufsteuerung liegt jetzt in `app/upload_openai_utils.py`.
- OpenAI-Cache- und Übernahmeblock ausgelagert: Cache-Pfad, Laden/Speichern und Wiederverwendung liegen jetzt in `app/upload_openai_cache_utils.py`.
- Statusanzeige-, Bildvorschau- und Personenmarkierungsblock ausgelagert: die letzten Upload-Hilfen liegen jetzt in `app/upload_status_utils.py`.
- PDF-Verwaltung intern zerlegt: `pdf_management_manager.py` ist jetzt in Dialog/UI, PDF-Optimierung, PDF/A-Erzeugung sowie Metadaten-/Verknüpfungsreste aufgeteilt.
- `python scripts/check_project_health.py` lief bereits erfolgreich durch.
- `python scripts/smoke_upload_tab.py` lief bereits erfolgreich durch.

#### Offen
- Die übrigen Refactor-Slices in `mail_manager.py` und `upload_tab.py` sind noch nicht abgearbeitet.
- Nach jedem weiteren Slice erneut `python scripts/check_project_health.py` und den passenden Smoke-Test ausführen.

---

## Regelwerk für den Rechnerwechsel

### Zielzustand sichern
- Commit immer mit klarer Message
- Danach sofort pushen
- Am nächsten Rechner immer per `git pull` starten

### Standard-Befehle
- `git add .`
- `git commit -m "kurze Beschreibung"`
- `git push`
- `git pull`
- `git status`

### Arbeitslogik
- Bei Fehlern oder unklaren Rückgängen immer auf letzten bekannten Stand verweisen
- Bei UI- oder Importfehlern erst reproduzieren, dann Slice-weise fixen
- Nach größeren Slices mindestens einmal: Projekt-Health prüfen und betroffenen Funktions-Smoke ausführen.

