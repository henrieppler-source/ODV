# ODV v56 – Login- und Transkriptionslayout-Fix

## Änderungen

- Benutzerwechsel ist jetzt abbruchsicher:
  - Wird der Dialog „Benutzer wechseln“ geschlossen oder abgebrochen, bleibt der bisherige Benutzer angemeldet.
  - Der alte API-Token wird erst nach erfolgreichem neuen Login abgemeldet.
  - Dadurch entsteht kein Zustand ohne gültigen Benutzer innerhalb der laufenden Anwendung.
- Beim Programmstart erscheint weiterhin der Login-Dialog, wenn kein gültiger Token/Benutzer geladen werden kann.
- Transkriptionsfelder wurden kompakter angeordnet:
  - `Transkription: [ ] ja   Art: [Auswahlliste]`
  - `Transkriptionshinweis` darunter als eigenes Feld.
- Das neue Transkriptionslayout ist umgesetzt in:
  - Dateien hochladen
  - Dateien bearbeiten / Metadatenbereich
- Kollisionen zwischen Transkriptionshinweis und Rechte-Bereich wurden beseitigt.

## Server

Keine neue SQL-Migration erforderlich.

Die Datei `server/routes_v56.php` entspricht der v55-Route mit dem Nachberechnungs-Fix und kann bei Bedarf als `ortschronik-api/routes.php` verwendet werden.
