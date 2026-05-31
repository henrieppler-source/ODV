# ODV Version v87

## Bild-PDFs per OCR vorbereiten

- PDF-Dateien werden für die OpenAI-Vorprüfung nun lokal mit `pypdf` auf lesbaren Text geprüft.
- Bild-PDFs ohne auslesbaren Text erhalten eine gelbe OpenAI-Ampel mit OCR-Hinweis.
- Im Upload-Reiter gibt es den Button `PDF OCR erstellen`.
- Wenn `ocrmypdf` mit Tesseract installiert ist, erzeugt ODV daraus eine durchsuchbare PDF-Kopie und wählt diese direkt für den Upload aus.
- Der OpenAI-Aufruf passiert weiterhin erst nach Klick auf `OpenAI prüfen`.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/main.py`
