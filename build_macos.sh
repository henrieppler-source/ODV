#!/usr/bin/env bash
set -euo pipefail

echo "Baue Ortschronisten-Datei-Verwaltung (ODV) v45 fuer macOS..."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-build.txt

rm -rf build dist

pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "ODV" \
  --collect-all PIL \
  launcher.py

echo ""
echo "Fertig. App liegt unter: dist/ODV.app"
echo "Hinweis: Fuer Verteilung auf andere Macs ist Signierung/Notarisierung sinnvoll."
