#!/usr/bin/env bash
# build_and_install.sh — build DSFM.app and install it
set -euo pipefail

cd "$(dirname "$0")/.."  # run from project root

APP_NAME="DualSense for Mac"
APP_DEST="/Applications/${APP_NAME}.app"

echo "==> Installing Python dependencies…"
pip3 install --quiet hidapi rumps py2app  # hidapi bundled into app by py2app

echo "==> Cleaning previous build…"
rm -rf build dist

echo "==> Building ${APP_NAME}.app…"
python3 setup.py py2app 2>&1 | grep -v "^$" | grep -v "^running" || true

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "[ERROR] Build failed — dist/${APP_NAME}.app not found."
    exit 1
fi

echo "==> Installing to /Applications…"
rm -rf "$APP_DEST"
cp -r "dist/${APP_NAME}.app" "$APP_DEST"

echo ""
echo "✓  ${APP_NAME} installed to /Applications"
echo ""
echo "To uninstall, run:  ./uninstall.sh"
