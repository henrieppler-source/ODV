# V38 Rundmail-Versand

## Neue Funktionen

- `Informationen > Rundmail erstellen...`
- Empfänger aus Benutzern, Verteilern und manuellen E-Mail-Adressen
- Versandart wählbar:
  - Nextcloud-Link versenden
  - Dokument anhängen
- Direkter Versand über API-Endpunkt `POST /api/mails/send`
- Versand erfolgt einzeln je Empfänger, damit keine E-Mail-Adressen gegenseitig sichtbar sind.

## Nextcloud-Link

Die App erzeugt aus einem lokalen Pfad unterhalb des Nextcloud-Stammordners einen Link in die Nextcloud-Dateiansicht des betreffenden Ordners. Ohne Nextcloud-Share-API wird kein öffentlicher Freigabelink erzeugt. Der Dateiname wird im Mailtext zusätzlich genannt.

Die Web-Dateiansicht kann unter `Admin > Admin-Einstellungen...` gesetzt werden, z. B.:

```text
https://nx94165.your-storageshare.de/apps/files/files
```

## Server-.env

Bitte ergänzen:

```ini
MAIL_FROM=cloud@heimatverein-milz.de
MAIL_FROM_NAME=Ortschronisten Römhild
MAIL_REPLY_TO=cloud@heimatverein-milz.de
```

Der Versand nutzt aktuell die PHP-Funktion `mail()`. Falls der Hoster SMTP erzwingt, muss später PHPMailer/SMTP ergänzt werden.

## Serverupdate

`server/routes_v38.php` als `ortschronik-api/routes.php` hochladen.

Keine SQL-Migration erforderlich, wenn v36/v37 bereits eingespielt wurden.
