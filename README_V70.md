# ODV v70 – Komfort-Updater über Nextcloud

Diese Version ergänzt v69 um den vollautomatischen Komfort-Updater.

## Neu

- neue mitzuliefernde `ODV_Updater.exe`
- ODV erkennt freigegebene Updates wie in v69 über die API
- Updatepaket wird aus dem lokalen Nextcloud-Updateordner kopiert und entpackt
- ODV startet den Updater und beendet sich selbst
- der Updater ersetzt den Programmordner und startet anschließend `ODV.exe` neu
- die laufende `ODV.exe` wird nicht von sich selbst überschrieben

## Wichtig für die Verteilung

Beim Windows-Build muss der gesamte Ordner `dist\ODV` verteilt werden. Darin muss neben `ODV.exe` auch `ODV_Updater.exe` liegen.

## Server

`server/routes_v70.php` wie gewohnt als `ortschronik-api/routes.php` hochladen.
