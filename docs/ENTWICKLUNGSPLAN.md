# Entwicklungsplan

## Stand MVP v4

Der Prototyp unterstützt inzwischen:

- lokale App für Windows/macOS
- Upload in lokal synchronisierte Nextcloud-Ordner
- zentrale JSON-Metadatenablage
- Metadaten inklusive Urheberrechts- und Archivfeldern
- optionale Personenmarkierung bei Bilddateien
- Admin-Funktionen für Status, Umbenennen und Verschieben
- eigene lokale Rechteverwaltung mit Rollen Ortschronist/Admin/Superadmin
- Benutzer-/Rechte-Reiter

## Nächste Schritte

1. Start-Dashboard fachlich filtern:
   - eigene Dateien
   - eigener Bereich
   - alle sichtbaren Vorgänge
   - Aktionen anderer Ortschronisten
   - Admin-Aktionen

2. Adminbereich verbessern:
   - Zielordner-Liste statt freie Pfade
   - Rückfrage-Textfeld
   - Statuskommentar
   - Protokollansicht je Upload

3. Datenmodell stabilisieren:
   - Pflichtfelder festlegen
   - Wertelisten für Dokumenttyp, Rechte, Orte, Ereignisse
   - Import der JSON-Dateien in MySQL vorbereiten

4. Server/API:
   - zentrale Benutzer- und Rechteverwaltung
   - zentrale Historie
   - Uploaddaten in MySQL/MariaDB

5. Installation:
   - Windows-EXE
   - macOS-App
   - Konfigurationsassistent beim ersten Start
