#!/usr/bin/env bash
# build_and_install.sh — build DSFM.app and install it
set -euo pipefail

cd "$(dirname "$0")/.."  # run from project root

APP_BUNDLE="DSFM.app"
APP_DEST="/Applications/${APP_BUNDLE}"

echo "==> Installing Python dependencies…"
pip3 install --quiet hidapi rumps py2app  # hidapi bundled into app by py2app

echo "==> Cleaning previous build…"
rm -rf build dist

echo "==> Building ${APP_NAME}.app…"
python3 setup.py py2app 2>&1 | grep -v "^$" | grep -v "^running" || true

if [ ! -d "dist/${APP_BUNDLE}" ]; then
    echo "[ERROR] Build failed — dist/${APP_BUNDLE} not found."
    exit 1
fi

echo "==> Installing to /Applications…"
rm -rf "$APP_DEST"
cp -r "dist/${APP_BUNDLE}" "$APP_DEST"

echo ""
echo "✓  DualSense for Mac installed to /Applications"
echo ""
echo "To uninstall, run:  ./uninstall.sh"
