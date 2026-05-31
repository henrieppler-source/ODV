# ODV v59 – Login-Startfix 2

## Änderung

Diese Version korrigiert den Start ohne gültige Anmeldung erneut und robuster:

- Wenn kein gültiger Benutzer/Token geladen werden kann, wird das Hauptfenster selbst als Loginfenster genutzt.
- Dadurch entsteht kein leeres Hauptfenster mehr ohne sichtbaren Login-Dialog.
- Erst nach erfolgreicher Anmeldung wird die eigentliche Oberfläche aufgebaut.
- Wird die Anmeldung beim Start abgebrochen, beendet sich die Anwendung sauber.

Keine SQL-Änderung erforderlich.
