# ODV v74 – Sitzungen, Geräte und Bearbeitungssperren

## Schwerpunkt

v74 ergänzt die Betriebssicherheit für den Produktivtest:

- Benutzeranmeldungen werden mit Geräteinformationen protokolliert.
- Superadmins können aktive Sitzungen und bekannte Geräte einsehen.
- Superadmins können Sitzungen beenden.
- Superadmins können Geräte sperren oder wieder freigeben.
- Neue Geräte werden nicht blockiert, sondern automatisch zugelassen und per Mail an Superadmins gemeldet.
- Mehrfachanmeldungen desselben Benutzers werden beim Login angezeigt.
- Dokumente erhalten eine Bearbeitungssperre, damit parallele Metadatenbearbeitung nicht versehentlich überschreibt.

## Geräteerkennung

Die Desktop-App erzeugt beim ersten Start lokal eine eindeutige ODV-Geräte-ID und sendet sie beim Login zusammen mit Gerätename, Windows-Benutzer, Betriebssystem und App-Version an die API.

Neue Geräte werden beim Login zugelassen. Superadmins werden per Mail informiert und können das Gerät bei Bedarf sperren.

## Sitzungsverwaltung

Neuer Superadmin-Menüpunkt:

`Admin → Sitzungen und Geräte...`

Dort sichtbar:

- aktive Sitzungen
- Benutzer
- Gerät
- ODV-Version
- IP-Adresse
- Startzeit
- letzte Aktivität
- bekannte Geräte
- gesperrte Geräte

Aktionen:

- ausgewählte Sitzung beenden
- Gerät sperren
- Gerät freigeben

## Dokument-Bearbeitungssperre

Beim Bearbeiten/Speichern von Metadaten wird serverseitig eine Sperre gesetzt bzw. verlängert. Wenn ein anderer Benutzer dasselbe Dokument bearbeitet, wird das Speichern blockiert. Die Sperre läuft nach ca. 15 Minuten ohne Aktivität automatisch ab.

## API/Server

Neue Tabellen:

- `odv_user_devices`
- `odv_user_sessions`
- `odv_document_locks`

Neue bzw. erweiterte Endpunkte:

- `GET /api/admin/sessions`
- `POST /api/admin/sessions/end`
- `POST /api/admin/devices/block`
- `POST /api/documents/{upload_id}/lock`
- `DELETE /api/documents/{upload_id}/lock`
- `POST /api/login` nimmt Geräteinformationen entgegen.

## Migration

Mitgeliefert:

- `sql/schema_v74_sessions_devices_locks.sql`
- `server/routes_v74.php`

`server/routes_v74.php` muss wie üblich als `ortschronik-api/routes.php` hochgeladen werden.
