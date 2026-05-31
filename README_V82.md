# ODV v82 – Uploadmaske und Layoutkorrekturen

Diese Version baut auf v81 auf.

## Änderungen

- Die Metadatenmaske im Reiter **Dateien hochladen** wurde an **Dateien anzeigen** und **Dateien bearbeiten** angeglichen.
- Technische Felder werden nun auch beim Upload angezeigt:
  - Upload-ID
  - Dokumenttyp
  - Status
  - Aktueller Dateiname
  - Erfasst von
  - Hochgeladen am
- Felder, die erst beim Upload final entstehen, werden ausgegraut dargestellt.
- **Erfasst von** wird mit dem aktuell angemeldeten Benutzer vorbelegt und ist im Upload nicht änderbar.
- **Aktueller Dateiname** und **Hochgeladen am** werden bei Dateiauswahl bzw. Drag & Drop vorbelegt; beim Upload wird die Upload-ID erzeugt.
- Der Button **Baum...** in der Dateiansicht wurde optisch vom Verzeichnis-Auswahlfeld abgesetzt, damit er auf Laptop-Bildschirmen nicht direkt am Feld klebt.

## Server

`server/routes_v82.php` muss als `ortschronik-api/routes.php` hochgeladen werden.

## SQL

Keine strukturelle Datenbankänderung erforderlich. Die Datei `sql/schema_v82_upload_form_layout.sql` enthält nur einen Hinweis.
