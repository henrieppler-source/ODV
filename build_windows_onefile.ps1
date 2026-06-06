$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([Parameter(Mandatory=$true)][scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Befehl fehlgeschlagen mit Exitcode $LASTEXITCODE"
    }
}

Write-Host "Baue Ortschronisten-Datei-Verwaltung (ODV) v72 als einzelne EXE fuer Windows..."

if (-Not (Test-Path ".venv")) {
    Invoke-Checked { py -3 -m venv .venv }
}

Invoke-Checked { .\.venv\Scripts\python.exe -m pip install --upgrade pip }
Invoke-Checked { .\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-build.txt }
Invoke-Checked { .\.venv\Scripts\python.exe -m PyInstaller --version }

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

Invoke-Checked { .\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name "ODV" `
    --collect-all PIL `
    --collect-all pypdf `
    --add-data "app\assets;app\assets" `
    launcher.py }

Write-Host ""
Write-Host "Fertig. EXE liegt unter: dist\ODV.exe"

Invoke-Checked { .\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name "ODV_Updater" `
    launcher_updater.py }

if (Test-Path "tools\ghostscript") {
    New-Item -ItemType Directory -Path "dist\tools" -Force | Out-Null
    Copy-Item "tools\ghostscript" "dist\tools\ghostscript" -Recurse -Force
    Write-Host "Ghostscript wurde als Begleitordner mitgeliefert: dist\tools\ghostscript"
} else {
    Write-Host "Hinweis: tools\ghostscript nicht gefunden. PDF/A und starke PDF-Komprimierung funktionieren nur mit systemweit installiertem Ghostscript."
}
if (Test-Path "tools\ghostscript_installer") {
    New-Item -ItemType Directory -Path "dist\tools" -Force | Out-Null
    Copy-Item "tools\ghostscript_installer" "dist\tools\ghostscript_installer" -Recurse -Force
    Write-Host "Ghostscript-Installer wurde als Begleitordner mitgeliefert: dist\tools\ghostscript_installer"
}

Write-Host "Updater liegt unter: dist\ODV_Updater.exe"
