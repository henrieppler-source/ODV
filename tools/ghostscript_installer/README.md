# Ghostscript-Installer fuer automatische Einrichtung

ODV sucht beim Start nach einem mitgelieferten Ghostscript-Installer in diesem
Ordner:

```text
tools/ghostscript_installer
```

Unterstuetzt werden:

- `*.msi` mit stiller Installation ueber `msiexec /quiet /norestart`
- `*.exe` mit stiller Installation ueber `/S /D=<lokaler ODV-Ghostscript-Ordner>`

Wenn Ghostscript bereits vorhanden ist, wird kein Installer gestartet. Wenn der
Installer erhöhte Rechte verlangt, startet ODV ihn per Windows-UAC.

Wenn kein Installer und keine portable Ghostscript-Struktur vorhanden ist,
arbeitet ODV weiter; PDF/A-Erzeugung und starke PDF-Komprimierung bleiben dann
deaktiviert bzw. nutzen den PyMuPDF-Fallback.

Bitte nur einen fachlich und lizenzrechtlich freigegebenen Ghostscript-Installer
in diesen Ordner legen.

Aktuell abgelegt:

```text
gs10071w64.exe
```

Quelle:

```text
https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10071/gs10071w64.exe
```

SHA256:

```text
3A4C28D0AAC47AA7CCCD35A5932C55110376E9DBD966898DDE388B7FABA444A4
```
