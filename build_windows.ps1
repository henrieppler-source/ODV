$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([Parameter(Mandatory=$true)][scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Befehl fehlgeschlagen mit Exitcode $LASTEXITCODE"
    }
}

Write-Host "Baue Ortschronisten-Datei-Verwaltung (ODV) v76 fuer Windows..."

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
    --name "ODV" `
    --collect-all PIL `
    --collect-all pypdf `
    --collect-all tkinterdnd2 `
    --add-data "app\assets;app\assets" `
    launcher.py }

Invoke-Checked { .\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "ODV_Updater" `
    launcher_updater.py }

if (Test-Path "dist\ODV_Updater\ODV_Updater.exe") {
    Copy-Item "dist\ODV_Updater\ODV_Updater.exe" "dist\ODV\ODV_Updater.exe" -Force
}

Write-Host ""
Write-Host "Fertig. EXE liegt unter: dist\ODV\ODV.exe"
Write-Host "Updater liegt unter: dist\ODV\ODV_Updater.exe"
Write-Host "Wichtig: Den gesamten Ordner dist\ODV verteilen, nicht nur die EXE."
