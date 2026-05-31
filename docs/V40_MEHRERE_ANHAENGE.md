# v40 - Mehrere Anhänge im Rundmailversand

## Änderungen

- In `Informationen > Rundmail erstellen...` können nun mehrere Dateien ausgewählt werden.
- Bei Versandart `Dokument anhängen` werden alle ausgewählten Dateien als Anlagen übertragen.
- Bei Versandart `Nextcloud-Downloadlink versenden` wird weiterhin die erste ausgewählte Datei für den Downloadlink genutzt.
- Das Textfeld `{datei}` enthält bei mehreren ausgewählten Dateien eine kommagetrennte Dateiliste.
- Der direkte Versand nutzt serverseitig multipart/mixed mit mehreren Anlagen.

## Größenbegrenzung

- Einzelanlage: maximal 8 MB
- Gesamtumfang aller Anlagen: maximal 12 MB

Für größere Dateien sollte der Nextcloud-Downloadlink verwendet werden.
