# Änderungen v70

## Komfort-Updater

- Vollautomatischer Updateablauf über Nextcloud-Updatefreigabe.
- `ODV_Updater.exe` wird beim Build zusätzlich erzeugt und in den Ordner `dist\ODV` kopiert.
- Bei verfügbarer neuer Version kopiert/entpackt ODV das freigegebene Paket aus dem lokalen Nextcloud-Syncordner.
- ODV schreibt einen Updateplan in den lokalen TEMP-Bereich, startet `ODV_Updater.exe` und beendet sich.
- Der Updater wartet auf das Ende des laufenden ODV-Prozesses, ersetzt die Dateien im Programmordner und startet die neue `ODV.exe`.
- Bei Fehlern schreibt der Updater ein Log unter `%TEMP%\ODV\updates\odv_updater.log`.

## Betriebshinweis

Für Updates weiterhin ZIP-Pakete im Nextcloud-Ordner `02_AUSTAUSCH/ODV_UPDATE/Windows` bereitstellen und die Freigabe in ODV durch Superadmin pflegen. SHA256-Prüfung bleibt möglich und empfohlen.


## Buildfix 5

- Updater startet Hilfsprozesse ohne sichtbare Konsolenfenster.
- Alte ODV-Instanz wird vor dem Kopieren zuverlässig abgewartet und notfalls beendet.
- Bei Fehlern wird kein Explorer-/Eingabefenster mehr automatisch geöffnet; Details stehen im Updater-Log.
