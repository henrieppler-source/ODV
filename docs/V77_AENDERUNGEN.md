# V77 Änderungen

## Dateiansicht

- Bearbeiter/Admins verwenden in „Dateien anzeigen“ dieselbe physische Rekursion wie Superadmin.
- Leserecht auf `00_ORTSCHRONIK` zeigt den vollständigen Unterbaum einschließlich tiefer Zeitungsordner.
- Technische Systemdateien (`desktop.ini`, `Thumbs.db`, `.DS_Store`, temporäre Dateien) werden ausgeblendet.
- `ODV_UPDATE` bleibt ausgeblendet.
- Neues Such-/Filterfeld für Dateinamen; Suche ist normalisiert.

## Metadaten/Status

- `Neuer Status` wurde zu `Dokumentstatus` umbenannt.
- Status `archiviert`, `abgelehnt`, `geloescht` verschieben Dateien in den Archivbereich unter `01_ABLAGE_ORTSCHRONIK/_ARCHIV`.
- `archiviert` ist nur aus dem Ablageordner erlaubt.
- `erfasst` reaktiviert Archiv-/Papierkorbdateien, wenn der ursprüngliche Pfad bekannt ist.

## Normierung

- Ortsnamen werden bei der Dateinamen-Normierung nicht mehrfach eingefügt.

## Punktebereich

- Der Punkteblock in „Dateien bearbeiten“ wurde optisch von den normalen Admin-Aktionen abgesetzt.
