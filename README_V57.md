# ODV v57 – Login-Startfix

Diese Version behebt den Startfall, in dem kein gültiger Benutzer bzw. keine gültige config.json geladen werden kann.

## Änderungen

- Beim Programmstart wird das Loginfenster jetzt zwingend angezeigt, wenn kein gültiger API-Token/Benutzer geladen werden kann.
- Das Loginfenster wird unter Windows in den Vordergrund gehoben und kurzzeitig als topmost gesetzt.
- Wird der Login beim Programmstart abgebrochen, beendet sich die Anwendung sauber.
- Die Korrekturen aus v56 bleiben enthalten.

Keine SQL-Änderung erforderlich.
