#!/usr/bin/env bash
# build_and_install.sh — build DSFM.app and install it
set -euo pipefail

cd "$(dirname "$0")/.."  # run from project root

LABEL="xyz.brc.dsfm"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGFILE="$HOME/Library/Logs/dsfm.log"
APP_DEST="/Applications/DSFM.app"
APP_BIN="$APP_DEST/Contents/MacOS/DSFM"

echo "==> Installing Python dependencies…"
pip3 install --quiet hidapi rumps py2app

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

echo "==> Setting up LaunchAgent…"
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/Library/Logs"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$APP_BIN</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$LOGFILE</string>
    <key>StandardErrorPath</key>
    <string>$LOGFILE</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF

launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo ""
echo "✓  DSFM installed to /Applications"
echo "✓  LaunchAgent registered — will auto-start at every login"
echo ""
echo "Logs:   tail -f $LOGFILE"
echo "Status: launchctl print gui/$(id -u)/$LABEL"
echo ""
echo "To uninstall, run:  ./uninstall.sh"
