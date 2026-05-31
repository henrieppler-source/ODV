# v30 – Rechte-/Admin-Finalisierung

## Schwerpunkt

Diese Version härtet die Rechteprüfung weiter. Rechte werden nicht mehr nur in der Oberfläche berücksichtigt, sondern konsequenter auch serverseitig in der API geprüft.

## App

- Versionsanzeige auf v30 geändert.
- Keine neue Datenbankmigration erforderlich.
- Benutzer-, Ordner- und Ortsordner-Stammdaten aus v27/v29 werden weiterverwendet.

## Server/API

Neue Serverdatei:

- server/routes_v30.php

Wichtige Änderungen:

- erlaubte Statuswerte werden zentral validiert
- Uploads benötigen Schreibrecht auf Zielordner
- Dokumentlisten werden nach Leserechten gefiltert
- Dokumentdetails benötigen Leserecht oder Eigentümerstatus
- Metadatenänderungen benötigen Schreibrecht oder Eigentümerstatus
- Personenzuordnung benötigt Schreibrecht oder Eigentümerstatus
- db-test bleibt Superadmin-only

## Testempfehlung

1. Als Superadmin anmelden und Dokumentliste prüfen.
2. Als Admin anmelden und prüfen, ob nur erlaubte Dokumente sichtbar sind.
3. Als Ortschronist anmelden und prüfen:
   - Upload in erlaubte Ordner möglich
   - Upload in nicht erlaubte Ordner wird verhindert
   - Dateien anzeigen zeigt nur Lesebereiche
4. Statusänderung als Ortschronist muss scheitern.
5. Statusänderung als Admin/Superadmin muss funktionieren.

## Status

v30 ist ein weiterer Schritt Richtung Produktivbetrieb. Vor offizieller Freigabe folgen noch:

- Installationspaket/Testbetriebs-Paket
- Kurzanleitung für Nutzer
- Admin-Anleitung
- Abnahme-/Testprotokoll
