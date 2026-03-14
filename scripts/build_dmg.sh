#!/usr/bin/env bash
# build_dmg.sh — build DSFM.app, convert icons, package as DMG
set -euo pipefail

cd "$(dirname "$0")/.."  # run from project root

VERSION=$(python3 -c "
import ast, sys
for node in ast.walk(ast.parse(open('setup.py').read())):
    if isinstance(node, ast.keyword) and node.arg == 'CFBundleShortVersionString':
        print(ast.literal_eval(node.value)); sys.exit()
")
DMG_NAME="DSFM-${VERSION}.dmg"

echo "==> DSFM ${VERSION}"

echo "==> Installing Python dependencies…"
pip3 install --quiet hidapi rumps py2app cairosvg

echo "==> Installing create-dmg…"
if ! command -v create-dmg &>/dev/null; then
    brew install create-dmg
fi

# ── Icons ─────────────────────────────────────────────────────────────────────

echo "==> Converting SVG icons to PNG…"
python3 - <<'EOF'
import cairosvg, os
icons = [
    ("assets/icons/icon_menubar_active.svg",   "assets/icons/icon_menubar_active.png",    16),
    ("assets/icons/icon_menubar_active.svg",   "assets/icons/icon_menubar_active@2x.png", 32),
    ("assets/icons/icon_menubar_inactive.svg", "assets/icons/icon_menubar_inactive.png",    16),
    ("assets/icons/icon_menubar_inactive.svg", "assets/icons/icon_menubar_inactive@2x.png", 32),
]
for src, dst, size in icons:
    cairosvg.svg2png(url=src, write_to=dst, output_width=size, output_height=size)
    print(f"  {dst}  ({size}x{size})")
EOF

# ── Build ─────────────────────────────────────────────────────────────────────

echo "==> Cleaning previous build…"
rm -rf build dist

echo "==> Building DSFM.app…"
python3 setup.py py2app 2>&1 | grep -v "^$" | grep -v "^running" || true

if [ ! -d "dist/DSFM.app" ]; then
    echo "[ERROR] Build failed — dist/DSFM.app not found."
    exit 1
fi

# ── Code sign ─────────────────────────────────────────────────────────────────
# Once your Apple Developer certificate arrives, uncomment and replace the identity.
#
# IDENTITY="Developer ID Application: Alexandru Bracau (XXXXXXXXXX)"
# echo "==> Signing…"
# codesign --deep --force --options runtime \
#     --entitlements scripts/entitlements.plist \
#     --sign "$IDENTITY" dist/DSFM.app

# ── DMG ───────────────────────────────────────────────────────────────────────

echo "==> Packaging DMG…"
rm -f "dist/${DMG_NAME}"

create-dmg \
    --volname "DualSense for Mac" \
    --volicon "assets/icons/AppIcon.png" \
    --window-pos 200 120 \
    --window-size 560 340 \
    --icon-size 128 \
    --icon "DSFM.app" 140 160 \
    --hide-extension "DSFM.app" \
    --app-drop-link 420 160 \
    "dist/${DMG_NAME}" \
    "dist/"

# ── Notarize ──────────────────────────────────────────────────────────────────
# Uncomment once your Apple Developer account is active and xcrun notarytool
# is configured with your credentials (keychain profile "AC_PASSWORD").
#
# echo "==> Notarizing…"
# xcrun notarytool submit "dist/${DMG_NAME}" \
#     --keychain-profile "AC_PASSWORD" \
#     --wait
# xcrun stapler staple "dist/${DMG_NAME}"

echo ""
echo "✓  dist/${DMG_NAME}"
echo ""
echo "SHA256: $(shasum -a 256 "dist/${DMG_NAME}" | awk '{print $1}')"
echo ""
echo "Next steps:"
echo "  1. Create a GitHub release tagged v${VERSION}"
echo "  2. Attach dist/${DMG_NAME} to the release"
echo "  3. Paste the SHA256 above into homebrew-dsfm/Casks/dsfm.rb"
