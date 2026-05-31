# Ortschronik-Uploader v42 – Buildpaket

Dieses Paket enthält den aktuellen App-Stand v42 und Skripte zur Erstellung einer Windows-EXE bzw. macOS-App.

## Voraussetzungen Windows

- Windows 10/11
- Python 3.11 oder neuer, empfohlen: aktuelle Python-Version von python.org
- Beim Installieren von Python: „Add Python to PATH“ aktivieren

## Windows-Ordner-Build empfohlen

PowerShell im entpackten Projektordner öffnen:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Ergebnis:

```text
dist\OrtschronikUploader\OrtschronikUploader.exe
```

Bitte den gesamten Ordner verteilen:

```text
dist\OrtschronikUploader
```

Nicht nur die einzelne EXE aus dem Ordner herauskopieren.

## Windows-Onefile-Build

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows_onefile.ps1
```

Ergebnis:

```text
dist\OrtschronikUploader.exe
```

Hinweis: Onefile startet oft langsamer und wird von Virenscannern eher skeptisch betrachtet. Für den Testbetrieb ist der Ordner-Build meist robuster.

## Optional: Installer mit Inno Setup

1. Erst `build_windows.ps1` ausführen.
2. Inno Setup installieren.
3. Datei öffnen:

```text
installer\windows\OrtschronikUploader.iss
```

4. Kompilieren.

Der Installer wird in `installer\windows\output` erzeugt.

## macOS-App bauen

Auf einem Mac im Projektordner:

```bash
chmod +x build_macos.sh
./build_macos.sh
```

Ergebnis:

```text
dist/OrtschronikUploader.app
```

Für die Verteilung auf andere Macs sollte die App signiert/notarisiert werden.

## Server

Die Desktop-App setzt voraus, dass die API auf dem Server bereits auf dem aktuellen Stand läuft. Für v42 ist serverseitig keine neue Migration nötig, wenn v40/v41 bereits eingespielt wurde.
