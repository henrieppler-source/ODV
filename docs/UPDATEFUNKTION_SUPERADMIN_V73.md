# ODV-Updatefunktion ab v73 – Ablauf für Superadmins

## 1. Neue Version bauen

Buildpaket entpacken und ausführen:

```powershell
.\build_windows.ps1
```

Danach liegt die Anwendung unter `dist\ODV`.

## 2. Update-ZIP erstellen

Den Inhalt von `dist\ODV` als ZIP packen. Auf oberster Ebene des ZIP müssen liegen:

- `ODV.exe`
- `ODV_Updater.exe`
- `_internal\`

Nicht nur die EXE bereitstellen.

## 3. ZIP in Nextcloud ablegen

Empfohlener Pfad:

`02_AUSTAUSCH/ODV_UPDATE/Windows/`

Der Ordner ist ein technischer Systemordner und wird in normalen Zielordnerlisten ausgeblendet.

## 4. SHA256 berechnen

```powershell
Get-FileHash "C:\Nextcloud_OC\02_AUSTAUSCH\ODV_UPDATE\Windows\ODV_v73.zip" -Algorithm SHA256
```

## 5. Updatefreigabe in ODV pflegen

Als Superadmin:

`Admin > ODV-Updatefreigabe verwalten...`

Eintragen:

- freigegebene Version, z. B. `v73`
- Dateiname, z. B. `ODV_v73.zip`
- Nextcloud-Relativpfad `02_AUSTAUSCH/ODV_UPDATE/Windows/`
- SHA256-Prüfsumme
- Pflichtupdate ja/nein
- Release-Hinweise

Mit **Lokal prüfen** kontrollieren, ob das Paket im lokalen Nextcloud-Syncordner vorhanden ist. Danach **Speichern**.

## 6. Verhalten beim Benutzer

Beim Start prüft ODV die freigegebene Version. Wenn eine neuere Version vorliegt, wird das Update angeboten. Bei Zustimmung:

1. ODV bereitet das Paket vor.
2. Der Updater startet mit Fortschrittsfenster.
3. ODV beendet sich.
4. Der Updater ersetzt den Programmordner.
5. Die neue ODV-Version startet.

## 7. Wichtig

Wenn die App nach dem Update z. B. v73 meldet, die API aber v71, muss zusätzlich `server/routes_v73.php` als `ortschronik-api/routes.php` hochgeladen werden.
