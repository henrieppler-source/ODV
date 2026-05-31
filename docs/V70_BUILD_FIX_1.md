# ODV v70 Buildfix 1 – Komfort-Updater

Dieser Buildfix ändert keine ODV-Fachversion. `APP_VERSION` bleibt `v70`.

## Behobener Fehler

Beim Start des Komfort-Updaters konnte unter Windows die Meldung erscheinen:

`Failed to load Python DLL ... _internal\python314.dll`

Ursache war nicht das Updatepaket, sondern der Start des Updaters aus einem temporären Ordner, in den nur `ODV_Updater.exe`, aber nicht der zugehörige PyInstaller-Laufzeitordner `_internal` kopiert wurde.

## Änderung

- Der Komfort-Updater wird nun mit `ODV_Updater.exe` und zugehörigem `_internal`-Ordner in einen temporären lauffähigen Updater-Ordner kopiert.
- Der Updater prüft vor dem Ersetzen des Programmordners, ob das Updatepaket vollständig ist:
  - `ODV.exe`
  - `ODV_Updater.exe`
  - `_internal`
  - `_internal/python*.dll`
- Bei unvollständigem Paket wird künftig eine verständliche Fehlermeldung ins Updater-Log geschrieben.

## Wichtig für Tests

Dieser Fix muss einmal lokal installiert bzw. neu gebaut werden, weil ein fehlerhafter alter Updater sich nicht zuverlässig selbst reparieren kann.
