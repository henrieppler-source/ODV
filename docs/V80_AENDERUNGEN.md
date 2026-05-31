# ODV v80 – UI-Zustand und Geräte-/Sitzungsversion

## Änderungen

- `APP_VERSION = "v80"`.
- `server/routes_v80.php` und `server/routes.php` melden `api_version = v80`.
- Fenstergrößen und Fensterpositionen werden lokal in der ODV-Konfiguration gespeichert und beim nächsten Öffnen wiederhergestellt.
- Das Hauptfenster wird ebenfalls gespeichert; bei erstmaligem Start wird weiterhin maximiert.
- Viele wichtige Dialoge werden mit erfasst, u. a. Benutzerverwaltung, Sitzungen/Geräte, Versandhistorie, Dokumentzugriffe, Punkteregeln, Ortsordner-Stammdaten, Verteilerverwaltung, Wartungsmodus, Updatefreigabe und Punktefenster.
- Ungültige Fensterpositionen außerhalb des Bildschirms werden verworfen.
- Neuer API-Endpunkt `POST /api/session/device` zur Aktualisierung der Geräte-/Sitzungsinformationen.
- ODV meldet bei Start, Login und Statusprüfung die aktuelle App-Version an die API.
- Die Übersicht „Sitzungen und Geräte“ zeigt dadurch nach Updates die aktuelle ODV-Version je Gerät/Sitzung.

## Hinweise

Die UI-Einstellungen werden lokal pro Gerät/Benutzer gespeichert. Es handelt sich nicht um fachliche Daten in MySQL.

