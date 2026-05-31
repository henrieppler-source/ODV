# v41 Änderungen

## Rundmail / Dokumente

- Dokumente werden jetzt über einen `+`-Button nacheinander zur Rundmail hinzugefügt.
- Mehrere Dokumente bleiben als Liste sichtbar.
- Einzelne Dokumente können wieder entfernt werden.
- Für die Versandart „Nextcloud-Downloadlink versenden“ werden für alle ausgewählten Dokumente Downloadlinks erzeugt.
- Der Mailtext nutzt standardmäßig den Platzhalter `{dokumente}`.
- Die Dokumentenliste erscheint im Mailtext z. B. so:

```text
DOKUMENTE:
Datei: Installation Nextcloud Client.docx
Downloadlink: https://.../download

Datei: Rechte Nextcloud Client.docx
Downloadlink: https://.../download
```

## Server

- Keine SQL-Migration erforderlich.
- Keine Serveränderung nötig, wenn v40 bereits läuft.
