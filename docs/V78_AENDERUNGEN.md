# ODV v79 Änderungen

- Bereich „Quelle / Herkunft“ erweitert: Primärquelle und Sekundärquelle.
- Transkriptionshinweis entfällt; Hinweise dazu gehören künftig ins Bemerkungsfeld.
- Dateinamen-Normierung: `Datum_Ort_Dateiname`; fehlendes Datum wird `0000`, Ort wird einmal als Präfix gesetzt und im Restdateinamen entfernt.
- Stichwortvorschläge aus dem Dateinamen werden ins Feld „Stichwörter“ übernommen und können gelöscht/ergänzt werden.
- Suche in „Dateien anzeigen“ berücksichtigt Dateiname, Stichwörter und Beschreibung; nicht erfasste Dateien werden über den Dateinamen gefunden.
- System-/Syncdateien wie `desktop.ini`, `Thumbs.db`, `.DS_Store`, `.nextcloudsync.log`, `.sync_*.db` werden ausgeblendet.
- Versandhistorie: verschiebbarer Detailbereich, Scrollbars, lesbare Mail-/Versanddetails statt Roh-JSON.
- Verteiler: externe Empfänger mit Vorname, Name und E-Mail-Adresse möglich.
- Punkteregeln: Regelkennung nur noch aus gültigem Katalog; bereits verwendete Regeln werden nicht erneut angeboten.
- Funktion umbenannt: „Punkte für vorhandene Dokumente neu berechnen…“.
- Startprüfung: Ortsordner-Stammdaten werden gegen den lokalen Nextcloud-Stammordner geprüft; fehlende Ordner werden gewarnt.
- Start-/Infofenster und Updater-Fortschrittsfenster vergrößert.
- Archiv-/Papierkorbstruktur wird beim Einlesen vorhandener Dateien ignoriert.
