#!/usr/bin/env bash
# uninstall.sh — remove DSFM completely
set -euo pipefail

echo "==> Stopping DSFM…"
pkill -f DSFM 2>/dev/null && echo "   stopped" || echo "   (not running)"

echo "==> Removing app…"
rm -rf /Applications/DSFM.app && echo "   /Applications/DSFM.app removed" || echo "   (not found)"

echo ""
echo "Done. Log file at ~/Library/Logs/dsfm.log — remove manually if wanted."
