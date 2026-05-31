# ODV Version v95

## Metadaten beim Dateiwechsel leeren

- Beim Auswählen eines neuen Dokuments werden fachliche Upload-Metadaten zurückgesetzt.
- Alte OpenAI-Vorschläge, Beschreibung, Bemerkung, Personenmarkierungen und OCR-Verknüpfung bleiben nicht am neuen Dokument hängen.
- Technische Felder wie Dateiname, Erfasser und Upload-Zeitpunkt werden danach wieder passend für die neue Datei gesetzt.
- Der Zielordner bleibt erhalten.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/main.py`
