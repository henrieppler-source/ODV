# Smoke-Test – Upload & Duplikatprüfung (v121)

## 1) Schnelle Vorab-Prüfung (automatisch)

- `python scripts/check_project_health.py`
  - Erwartung: keine Fehler, nur Hinweise auf refactor-empfohlene große Module.
- `python scripts/smoke_upload_tab.py`
  - Erwartung: `OK: upload_tab Smoke erfolgreich`

## 2) Manuelle Kernprüfung Upload-Fluss

- Anwendung starten: `python launcher.py -q`
1. Login mit gültigem Nutzer.
2. Reiter `Dateien hochladen` öffnen.
3. Neue Testdatei auswählen (Datei ohne _ocr, z. B. `.pdf` oder `.txt`).
4. Prüfen:
   - Dateiname wird im Dateifeld übernommen.
   - Felder für Metadaten bleiben bedienbar.
   - bei „Datei bereits vorhanden“-Prüfung wird ggf. Warnung gezeigt (falls Hash bereits in ODV).
5. Upload starten.
6. Erwartung:
   - Nach erfolgreicher Ausführung keine Anwendungshänger.
   - Datei erscheint in Dashboard/Dateiliste.
   - Bei Konflikt (gleicher SHA-256) wird Upload-Dialog angezeigt und nicht stillschweigend doppelt hochgeladen.

## 3) OpenAI-Precheck/PDF-Blocker (kurz)

1. Mit PDF ohne `_ocr.pdf` wählen.
2. In Upload-Tab den OpenAI-Status/Prüfbereich beobachten.
3. Erwartung:
   - Meldung erscheint und entspricht der Konfiguration im Admin-Panel.
4. Bei Blocker-Triggerung:
   - Klarer Statustext (`rot/gelb` je Konfiguration).
   - Hinweis auf manuellen Abschluss der Metadaten.
5. Bei bereits vorhandener OCR-Datei (gleicher Stammname + `_ocr.pdf`) wird kein unnötiger Blocker-Flow erzwungen.

## 4) Zielordner-Regeln

- Nicht-Admin: Zielordner darf nur die freigegebenen Upload-Ziele enthalten (nach letzter Berechtigungslogik).
- Admin/Superadmin: zusätzliche Ordner nur nach Berechtigung sichtbar.

## 5) Ergebnisprotokoll

- [ ] check_project_health lief grün (nur Refactor-Hinweise erlaubt)
- [ ] smoke_upload_tab lief grün
- [ ] Upload mit neuer Datei funktioniert
- [ ] Duplikatprüfung greift bei gleichem SHA-256
- [ ] OpenAI-Precheck zeigt erwarteten Status
- [ ] Kein dauerhaftes UI-Hängen beim Klick auf Datei auswählen/Upload
- [ ] Dashboard zeigt den hochgeladenen Datensatz mit korrekten Grunddaten
