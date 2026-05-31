# ODV Version v86

## OpenAI-Vorprüfung per Ampel

- Im Upload-Reiter gibt es nun eine lokale OpenAI-Ampel für die ausgewählte Datei.
- Grün bedeutet: Text ist lokal lesbar und wirkt für eine OpenAI-Metadatenprüfung geeignet.
- Gelb bedeutet: OpenAI-Prüfung ist möglich, aber nur eingeschränkt oder mit unklarem Archivbezug; vor dem API-Aufruf fragt ODV nach.
- Rot bedeutet: Datei soll nicht an OpenAI gesendet werden; der Button „OpenAI prüfen“ wird gesperrt.
- Die Ampel arbeitet lokal und löst keinen OpenAI-Aufruf aus.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/main.py`
