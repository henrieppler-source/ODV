# Ortschronisten-Datei-Verwaltung (ODV) v45

Diese Version ergänzt den Startbildschirm mit dem Logo der Ortschronisten und benennt die Anwendung in **Ortschronisten-Datei-Verwaltung (ODV)** um.

## Windows-Build

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Ergebnis:

```text
dist\ODV\ODV.exe
```

Bitte den gesamten Ordner `dist\ODV` verteilen.

## Einzel-EXE

```powershell
.\build_windows_onefile.ps1
```

Ergebnis:

```text
dist\ODV.exe
```

## macOS-Build

```bash
chmod +x build_macos.sh
./build_macos.sh
```

Ergebnis:

```text
dist/ODV.app
```
