#!/usr/bin/env bash
# uninstall.sh — remove DSFM completely
set -euo pipefail

echo "==> Stopping DualSense for Mac…"
pkill -f "DualSense for Mac" 2>/dev/null && echo "   stopped" || echo "   (not running)"

echo "==> Removing app…"
rm -rf "/Applications/DualSense for Mac.app" && echo "   removed" || echo "   (not found)"

echo ""
echo "Done. Log file at ~/Library/Logs/dsfm.log — remove manually if wanted."
