# ODV Version v88

## OCR-Fallback ohne Ghostscript

- `PDF OCR erstellen` nutzt weiterhin OCRmyPDF, falls es installiert ist.
- Wenn OCRmyPDF fehlt, nutzt ODV nun PyMuPDF plus Tesseract als lokalen Fallback.
- Tesseract wird auch gefunden, wenn es nicht im aktuellen Windows-PATH steht.
- Deutsche Tesseract-Sprachdaten liegen lokal unter `app/tessdata/deu.traineddata`.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/main.py`
- `app/tessdata/deu.traineddata`
