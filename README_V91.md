# ODV Version v91

## OCR-Fortschrittsanzeige

- Während `PDF OCR erstellen` läuft, zeigt ODV im Upload-Reiter einen laufenden Fortschrittsbalken an.
- Der Balken wird nach erfolgreicher OCR oder bei Fehlern automatisch ausgeblendet.
- Während OCR laufen die Buttons `PDF OCR erstellen` und `OpenAI prüfen` gesperrt.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/main.py`
