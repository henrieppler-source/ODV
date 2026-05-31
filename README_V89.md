# ODV Version v89

## OCR-PDF als verknüpfte Analysefassung

- `PDF OCR erstellen` ersetzt nicht mehr das Original und wählt auch nicht die OCR-Datei als Upload-Datei aus.
- Das Original bleibt das Upload-/Archivdokument.
- OpenAI nutzt bei vorhandener OCR-Verknüpfung automatisch den Text der OCR-PDF.
- Beim Upload wird die OCR-PDF als verknüpfte Kopie neben dem hochgeladenen Original gespeichert.
- Die OCR-Verknüpfung wird in den Metadaten gespeichert.
- Beim Umbenennen/Verschieben des Originals wird die verknüpfte OCR-PDF mit umbenannt/verschoben.
- Im Reiter `Dateien anzeigen` gibt es den Button `OCR anzeigen`, wenn eine OCR-PDF verknüpft ist.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/main.py`
- `app/models.py`
- `requirements.txt`
