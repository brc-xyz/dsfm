#!/usr/bin/env bash
# uninstall.sh — remove DSFM completely
set -euo pipefail

LABEL="xyz.brc.dsfm"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "==> Stopping LaunchAgent…"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && echo "   stopped" || echo "   (not running)"
rm -f "$PLIST" && echo "   plist removed" || true

echo "==> Removing app…"
rm -rf /Applications/DSFM.app && echo "   /Applications/DSFM.app removed" || echo "   (not found)"

echo ""
echo "Done. Log file at ~/Library/Logs/dsfm.log — remove manually if wanted."
