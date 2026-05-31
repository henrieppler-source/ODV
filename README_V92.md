# ODV Version v92

## OCR-PDF automatisch neben Original speichern

- `PDF OCR erstellen` fragt nicht mehr nach einem Speicherort.
- Die OCR-PDF wird automatisch im gleichen Ordner wie das Original gespeichert.
- Der Dateiname lautet `Originalname_ocr.pdf`; bei Namenskonflikten ergänzt ODV automatisch `_#1`, `_#2` usw.
- Die OCR-PDF wird danach direkt mit dem Original verknüpft.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/main.py`
