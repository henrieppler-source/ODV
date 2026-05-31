# ODV Version v90

## OCR-Dateien im gleichen Ordner, aber ausgeblendet

- Verknüpfte OCR-PDFs bleiben im gleichen Ordner wie das Original.
- Beim automatischen Umbenennen/Verschieben wird die OCR-PDF parallel mitgeführt.
- Der OCR-Dateiname folgt dem Original mit Zusatz `_ocr.pdf`.
- In `Dateien anzeigen` werden verknüpfte OCR-PDFs im Baum ausgeblendet.
- In `Dateien bearbeiten` werden OCR-PDFs nicht als eigene Dokumente angezeigt.
- Die OCR-PDF bleibt über den Button `OCR anzeigen` am Original erreichbar.

Geänderte Dateien:

- `app/main.py`
