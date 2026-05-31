# V69 Änderungen

## Updateverwaltung über Nextcloud

- Neuer API-Endpunkt `GET /api/app-update` für die freigegebene ODV-Version.
- Neuer Superadmin-Endpunkt `PUT /api/admin/app-update` zum Hinterlegen der Updatefreigabe.
- Speicherung der Updateinformationen in `system_settings`.
- Superadmin-Menü **ODV-Updatefreigabe verwalten...**.
- Startprüfung auf neuere freigegebene ODV-Version.
- Manueller Prüflauf über **Hilfe → Nach ODV-Update suchen...**.
- Update-Datei wird aus dem lokalen Nextcloud-Syncordner kopiert.
- Standardpfad: `02_AUSTAUSCH/ODV_UPDATE/Windows`.
- Optionale SHA256-Prüfsummenprüfung.
- ZIP-Dateien werden nach `%LOCALAPPDATA%\ODV\versions\vXX` entpackt.
- Die laufende EXE wird nicht überschrieben; die neue EXE kann nach Bereitstellung gestartet werden.

## Nicht enthalten

- Kein vollautomatisches Ersetzen der laufenden Installation durch eine separate `ODV_Updater.exe`. Dieser Komfort-Updater ist für eine spätere Version vorgesehen.
