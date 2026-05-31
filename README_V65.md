# ODV v65

Schwerpunkt: nachträglich erfasste vorhandene Dateien, Rundmail ohne Anlage und kleinere UI-Korrekturen.

Bitte serverseitig `server/routes_v65.php` als produktive `ortschronik-api/routes.php` hochladen.
Die beiliegende `server/routes.php` entspricht ebenfalls v65.

## Geändert in v65

- Bereits physisch vorhandene Dateien werden erst dann in ODV/MySQL übernommen, wenn wirklich Metadaten gespeichert werden.
- Nur Anzeigen, Vorschau oder Doppelklick/Öffnen erzeugt keinen Dokumentdatensatz.
- Vorhandene Dateien, die nachträglich erfasst werden, erhalten den Status `erfasst` statt `hochgeladen`.
- Die Historie verwendet dafür „Vorhandene Nextcloud-Datei in ODV erfasst“.
- Nachträglich erfasste vorhandene Dateien erscheinen in „Dateien bearbeiten“ nur, wenn sie in einem der ODV-Hauptbereiche liegen:
  - `00_ORTSCHRONIK`
  - `01_ABLAGE_ORTSCHRONIK`
  - `06_ARBEIT_DER_ORTSCHRONISTEN`
- Wurde die nachträgliche Erfassung bereits durch einen Admin vorgenommen, wird der Datensatz nicht nochmals als Admin-Bearbeitungsfall angezeigt.
- Oberfläche: „Hochgeladen von“ heißt an den Metadatenstellen nun „Erfasst von“.
- Admins können „Erfasst von“ weiterhin per Auswahlliste ändern; automatische Punkte werden dem neuen Benutzer zugeordnet.
- Layout: Der Block „Rechte“ steht nun auf gleicher Höhe wie „Zeit / Ort / Inhalt“.
- Rundmail: neue Standard-Versandart „Keine Anlage“.
- Rundmail verlangt nur bei „Nextcloud-Downloadlink“ oder „Dokument anhängen“ eine ausgewählte Datei.
- Server/API akzeptiert den neuen Dokumentstatus `erfasst`.

## Reset

Der Reset für Bewegungsdaten liegt unter:

`sql/reset_bewegungsdaten_v65.sql`

Er löscht wie bisher nur Bewegungsdaten, nicht Benutzer, Rollen/Rechte, Ortsordner, Punkteregeln, Verteiler, Systemeinstellungen oder Nextcloud-Dateien.
