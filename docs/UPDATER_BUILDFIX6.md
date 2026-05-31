# ODV Komfort-Updater Buildfix 6

Dieser Buildfix ergänzt den Komfort-Updater um ein sichtbares Fortschrittsfenster.

## Änderung

- Der Updater zeigt während der Aktualisierung ein eigenes Fenster „ODV wird aktualisiert“.
- Angezeigt werden die Schritte: alte ODV-Version beenden, Updatepaket prüfen, Programmdateien ersetzen, neue ODV-Version starten.
- Kurz aufflackernde Konsolen-/Hilfsfenster sollen dadurch vermieden werden.
- Bei Fehlern erscheint eine verständliche Meldung mit Hinweis auf `%TEMP%\ODV\updates\odv_updater.log`.

## Testhinweis

Vor dem Test alte Update-Reste löschen:

```powershell
Remove-Item "$env:LOCALAPPDATA\ODV\updates" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:TEMP\ODV" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:TEMP\ODVUpdates" -Recurse -Force -ErrorAction SilentlyContinue
```
