# Mitgeliefertes Ghostscript

ODV sucht hier nach einer portablen Ghostscript-Installation:

```text
tools/ghostscript/bin/gswin64c.exe
```

Alternativ wird auch eine Unterstruktur wie `tools/ghostscript/gs10.xx.x/bin/gswin64c.exe`
erkannt.

Beim Windows-Ordner-Build kopiert `build_windows.ps1` diesen Ordner nach:

```text
dist/ODV/tools/ghostscript
```

Der Inno-Setup-Installer nimmt den Ordner automatisch mit, weil er `dist/ODV/*`
rekursiv installiert.

Hinweis: Bitte Ghostscript nur in einer zur ODV-Verteilung passenden Lizenz- und
Versionsform ablegen.
