# ODV Version v85

## Korrektur OpenAI-Metadaten aus DOCX

- DOCX-Dateien werden vor dem OpenAI-Check lokal als Textauszug gelesen.
- Der OpenAI-Check erhält nun tatsächlichen Dokumentinhalt statt nur Dateiname/Dateiendung.
- Für typische Niederschriften/Protokolle gibt es eine lokale Fallback-Ableitung für Datum/Zeitraum, Ort, Ereignis, Stichwörter, Beschreibung und Quelle.
- Der Button „Metadaten übernehmen“ wird aktiv, wenn entweder OpenAI oder die lokale Ableitung verwertbare Metadaten liefert.
- Datei auswählen löst weiterhin keinen API-Aufruf aus; erst „OpenAI prüfen“ verbraucht Tokens.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/openai_client.py`
- `app/main.py` (`APP_VERSION = "v85"`)
