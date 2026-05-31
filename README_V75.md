# ODV v75 – Dateiansicht und Metadatenrechte korrigiert

## Schwerpunkt

v75 korrigiert die Dateiansicht und die Editierbarkeit der Metadaten in „Dateien anzeigen“.

## Änderungen

- `APP_VERSION = "v75"`
- `server/routes_v75.php`
- `server/routes.php` meldet `api_version = v75`
- `00_ORTSCHRONIK` wird in „Dateien anzeigen“ für Bearbeiter, Admins und Superadmins rekursiv angezeigt.
- Tiefe Ordner wie `00_ORTSCHRONIK\90_Archive_und_Quellen\90-10_Zeitungen\Freies_Wort\...` sollen auch bei Bearbeitern/Ortschronisten korrekt aufklappbar sein.
- Die Rekursion orientiert sich am lesbaren Hauptbereich und nicht an gesonderten Unterordner-Rechten tiefer Ebenen.
- `ODV_UPDATE` bleibt in normalen Bäumen und Auswahllisten ausgeblendet.
- Metadaten in „Dateien anzeigen“ sind nur bearbeitbar, wenn:
  - Schreibrecht auf den Ordner besteht, oder
  - die Datei bereits in ODV erfasst ist und dem angemeldeten Benutzer gehört, oder
  - der Benutzer Admin/Superadmin ist.
- Wenn bei einem vorhandenen ODV-Dokument kein „Erfasst von“ hinterlegt ist, dürfen nur Admin/Superadmin Metadaten bearbeiten.

## Server

Wie üblich:

`server/routes_v75.php` als `ortschronik-api/routes.php` hochladen.

## SQL

Für v75 ist keine neue Tabellenstruktur erforderlich.
