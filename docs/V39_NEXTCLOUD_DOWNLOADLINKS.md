# v39 – Nextcloud-Downloadlinks für Rundmails

## Ziel

Rundmails können nun wahlweise ein Dokument als Anlage versenden oder einen öffentlichen Nextcloud-Downloadlink erzeugen und verschicken.

## Wichtige Änderung

Der lokale Nextcloud-Pfad wird nicht mehr als Link verschickt. Die App übergibt an die API:

- lokalen Dateipfad
- lokales Nextcloud-Stammverzeichnis des aktuellen Nutzers

Die API ermittelt daraus den relativen Nextcloud-Pfad und erzeugt über die Nextcloud-OCS-Share-API einen öffentlichen Freigabelink.

## Server-.env

In `ortschronik-api/.env` müssen gesetzt sein:

```ini
NEXTCLOUD_BASE_URL=https://nx94165.your-storageshare.de
NEXTCLOUD_USERNAME=...
NEXTCLOUD_APP_PASSWORD=...
NEXTCLOUD_REMOTE_BASE=
```

`NEXTCLOUD_APP_PASSWORD` sollte ein Nextcloud-App-Passwort sein, nicht das normale Benutzerpasswort.

`NEXTCLOUD_REMOTE_BASE` bleibt leer, wenn das lokale Nextcloud-Stammverzeichnis direkt dem Wurzelverzeichnis der Nextcloud entspricht.

## Neuer API-Endpunkt

```text
POST /api/nextcloud/share
```

Eingabe:

```json
{
  "local_file_path": "C:/Nextcloud_OC/03_INFORMATION/Einladung.docx",
  "local_nextcloud_base": "C:/Nextcloud_OC"
}
```

Antwort:

```json
{
  "success": true,
  "remote_path": "/03_INFORMATION/Einladung.docx",
  "share_url": "https://.../s/...",
  "download_url": "https://.../s/.../download"
}
```

## Rundmail

In `Informationen > Rundmail erstellen...` gibt es weiterhin:

- Nextcloud-Downloadlink versenden
- Dokument anhängen

Bei Auswahl einer Datei erzeugt die App automatisch einen Downloadlink, sofern die Nextcloud-Zugangsdaten korrekt gesetzt sind. Falls die Freigabe nicht erzeugt werden kann, nutzt die App als Fallback den bisherigen Link in die Nextcloud-Dateiansicht des Ordners.

## Hinweise

- Der Versand läuft weiterhin serverseitig über die API.
- Der Empfänger erhält den Link einzeln; E-Mail-Adressen sind nicht gegenseitig sichtbar.
- Die Freigabe wird als öffentlicher Leselink erzeugt.
