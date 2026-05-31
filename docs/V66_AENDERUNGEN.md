# V66 Änderungen

## Dateien anzeigen

- Das Feld **Erfasst von** ist für Admins nun auch in der Dateiansicht als Benutzer-Auswahlliste verfügbar.
- Die Funktion entspricht der Admin-Bearbeitung: Beim Speichern/Ändern wird `uploaded_by_user_id` aktualisiert.
- Die API überträgt vorhandene automatische Punkte auf den neu ausgewählten Benutzer.
- Physisch vorhandene Dateien ohne ODV-Datensatz werden weiterhin erst beim bewussten Speichern/Ändern von Metadaten angelegt.

## Rundmail

- Bei Versandart **Nextcloud-Downloadlink versenden** erzeugt **Direkt versenden** fehlende Links automatisch.
- **Downloadlinks erzeugen** ist nicht mehr zwingender Pflichtschritt, sondern Vorschau/Kontrolle.
- Ohne Dokumente bleibt **Keine Anlage** der saubere Standard.

## Server/API

- `POST /api/documents` akzeptiert bei Admins `uploaded_by_user_id` bzw. `import_uploaded_by_user_id`, damit vorhandene Dateien direkt dem richtigen Erfasser zugeordnet werden können.
