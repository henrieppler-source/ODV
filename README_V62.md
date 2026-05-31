# ODV v62 – robuste Dateiauflösung / Dateiendungen

Änderungen gegenüber v61:

- Die lokale Dateiauflösung in „Dateien bearbeiten“ ist robuster.
- Datensätze mit fehlender oder ersetzter Dateiendung werden toleranter gefunden, z. B. `datei_jpg`, `datei_jpg.jpg` oder `datei.jpg`.
- Wenn der gespeicherte Pfad eines anderen Benutzers nicht passt, sucht ODV im eigenen Nextcloud-Stammverzeichnis nach passenden Namensvarianten.
- Die Dateinamen-Normierung bereinigt künftig Altfälle wie `_jpg` vor der echten Endung, damit nicht mehr unnötig Namen wie `..._jpg.jpg` entstehen.

Keine SQL-Änderung erforderlich.
