# Updater Buildfix 7

- ODV erhält eine Einzelinstanz-Sperre, damit während oder nach einem Update nicht zwei ODV-Fenster parallel laufen.
- Der Komfort-Updater wartet weiterhin auf die alte ODV-Prozess-ID und beendet vor dem Kopieren zusätzlich verbliebene `ODV.exe`-Prozesse.
- Die neue ODV-Version wird erst danach gestartet.
- Das Fortschrittsfenster aus Buildfix 6 bleibt erhalten.

Hinweis: Nach dem Update muss die Server-API-Version separat passen; bei App v71 und API v70 ist `routes_v71.php` noch nicht als `routes.php` hochgeladen.
