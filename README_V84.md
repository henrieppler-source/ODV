# ODV Version v84

Diese Version korrigiert die OpenAI-Logik im Upload-Reiter.

## Änderung

- Beim Auswählen einer Datei wird weiterhin kein OpenAI-API-Aufruf ausgelöst.
- Der Button **OpenAI prüfen** löst jetzt die Prüfung bewusst manuell aus.
- Die OpenAI-Prüfung erzeugt in einem API-Aufruf sowohl eine kurze Dokumentbewertung als auch Metadatenvorschläge.
- Der Button **Metadaten übernehmen** wird nach erfolgreicher OpenAI-Prüfung automatisch aktiviert, wenn übernehmbare Metadatenvorschläge vorhanden sind.
- Sind keine verwertbaren Vorschläge vorhanden, bleibt der Button deaktiviert und die Oberfläche zeigt einen klaren Hinweis.
- **Metadaten übernehmen** startet selbst keinen zusätzlichen OpenAI-API-Aufruf mehr.

## Geänderte Dateien

- `app/upload_tab.py`
- `app/openai_client.py`
- `app/main.py` (`APP_VERSION = "v84"`)
