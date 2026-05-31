# ODV v45 – Admin-/PDF-Korrekturen

## Korrigiert

- Benutzerverwaltung: Passwortfeld hat jetzt einen Auge-Button. Solange die Maustaste gedrückt wird, wird das Passwort im Klartext angezeigt; beim Loslassen/Verlassen wird es wieder maskiert.
- Dateien bearbeiten: Mehrfachauswahl bleibt beim Rechtsklick erhalten. Damit kann „Ausgewählte PDFs zusammenfassen...“ funktionieren.
- Dateien bearbeiten: zusätzlich Button „Ausgewählte PDFs zusammenfassen...“ im Admin-Aktionsbereich.
- Dateien bearbeiten: Doppelklick auf einen Datensatz öffnet die Datei im Standardprogramm.
- Dateien anzeigen: Rechtsklick bietet bei Bilddateien die PDF-Umwandlung nur noch für Admin/Superadmin an.
- Dateien bearbeiten: Button „Bearbeitung speichern“ wurde zu „Datei umbenennen / verschieben“ umbenannt.
- Dateien bearbeiten: Nach erfolgreichem Umbenennen/Verschieben wird der Status automatisch auf `uebernommen` gesetzt.
- Dateinamen-Normierung: Punkte im Dateinamenstamm werden vor der Dateiendung durch Unterstriche ersetzt.

## PDF-Zusammenführung

1. Im Reiter „Dateien bearbeiten“ mindestens zwei PDF-Datensätze markieren.
2. Entweder Rechtsklick auf eine der markierten Dateien und „Ausgewählte PDFs zusammenfassen...“ wählen oder den gleichnamigen Button im Admin-Aktionsbereich verwenden.
3. Zielname/-ort auswählen.
4. Die neue PDF wird erzeugt, in MySQL/API registriert und als JSON gesichert.

Die Reihenfolge entspricht der aktuellen Reihenfolge in der Liste.
