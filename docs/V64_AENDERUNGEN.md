# ODV v64 – Physische Dateien in „Dateien anzeigen“ und Sonderpunkte

## Dateiansicht

- Der Verzeichnisbaum in „Dateien anzeigen“ wird ohne künstliche Tiefenbegrenzung rekursiv aufgebaut.
- Physisch vorhandene Dateien werden angezeigt, auch wenn noch keine ODV-Metadaten vorhanden sind.
- Dateien ohne ODV-Metadaten werden im Baum mit normalem Dateinamen angezeigt; der Hinweis steht im Bereich Metadaten/Historie.
- Doppelklick öffnet auch nicht erfasste Dateien im Standardprogramm.
- Bei fehlenden Metadaten wird weiterhin angezeigt: „Keine JSON-Metadaten vorhanden. Beim Speichern werden neue Metadaten angelegt.“
- Beim Speichern wird aus einer bereits vorhandenen Datei ein ODV-Dokumentdatensatz in MySQL erzeugt; die Datei selbst wird nicht erneut kopiert.

## Punkte

- Punkteberechtigt sind nur Dateien unter:
  - `00_ORTSCHRONIK`
  - `01_ABLAGE_ORTSCHRONIK`
  - `06_ARBEIT_DER_ORTSCHRONISTEN`
- Sonderwertung:
  - „Kinder wie die Zeit vergeht“: 100 Punkte bei neuer ODV-Ablage, 20 Punkte bei nachträglicher Metadatenerfassung.
  - Jahresblätter: 50 Punkte bei neuer ODV-Ablage, 10 Punkte bei nachträglicher Metadatenerfassung.
