#!/usr/bin/env bash
# build_and_install.sh — build DSFM.app and install it
set -euo pipefail

cd "$(dirname "$0")/.."  # run from project root

APP_DEST="/Applications/DSFM.app"

echo "==> Installing Python dependencies…"
pip3 install --quiet hidapi rumps py2app pyobjc-framework-IOBluetooth

echo "==> Cleaning previous build…"
rm -rf build dist

echo "==> Building DSFM.app…"
python3 setup.py py2app 2>&1 | grep -v "^$" | grep -v "^running" || true

if [ ! -d "dist/DSFM.app" ]; then
    echo "[ERROR] Build failed — dist/DSFM.app not found."
    exit 1
fi

echo "==> Installing to /Applications…"
rm -rf "$APP_DEST"
cp -r dist/DSFM.app "$APP_DEST"

echo ""
echo "✓  DSFM installed to /Applications"
echo ""
echo "To uninstall, run:  ./uninstall.sh"
