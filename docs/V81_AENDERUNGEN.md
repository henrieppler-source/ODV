# ODV v81 – Fix Fenstergrößen/Fensterpositionen

- `APP_VERSION = "v81"`.
- `server/routes_v81.php` und `server/routes.php` melden `api_version = v81`.
- Fix für lokale UI-Einstellungen: Fenstergrößen und Fensterpositionen werden nun bereits bei Größen-/Positionsänderungen zwischengespeichert und nicht erst beim Zerstören des Fensters.
- Dadurch werden Dialoggrößen wie Benutzerverwaltung, Sitzungen/Geräte, Versandhistorie und weitere Toplevel-Fenster beim nächsten Öffnen zuverlässig wiederhergestellt.
- Schließen über Fenster-X und Schließen-Button wird unterstützt.
- Keine Datenbankänderung erforderlich.
