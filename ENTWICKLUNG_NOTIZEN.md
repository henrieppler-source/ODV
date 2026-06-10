# Entwicklungsnotizen ODV

Dokumentation von Arbeitsschritten, Bugs, Fixes und Wiederaufnahmepunkten für Rechner-übergreifendes Arbeiten.

## Git-Workflow (festgelegt)

### Bei Fertigstellung eines Arbeitstags
```powershell
git add .
git status   # optional zur Kontrolle vor Commit
git commit -m "Beschreibung"
git push
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
5. `git status` (zur finalen Kontrolle)

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
- Weitere Refactor-Slices in großen Modulen noch offen: `mail_manager.py`, `postprocess_manager.py`, `upload_tab.py`, `pdf_management_manager.py`.
- Tests nach jedem Refactor-Slice ausführen: `python scripts/check_project_health.py` und relevante Smoke-Pfade für betroffene Bereiche.

### 06-10 Schlussstatus
- Lokale Notizen aktuell: `ENTWICKLUNG_NOTIZEN.md` erweitert und als Leitfaden bereit
- Erwarteter nächster Wiederaufnahmepunkt: auf funktionale Stabilität in `upload` und Admin-Workflows fokussieren

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

