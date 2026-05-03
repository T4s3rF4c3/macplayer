#!/usr/bin/env bash
# ============================================================
#  MacPlayer — macOS Build Script
#  Produces: dist/MacPlayer.app  and  dist/MacPlayer.dmg
# ============================================================
set -euo pipefail

echo ""
echo "╔══════════════════════════════════╗"
echo "║   MacPlayer Build  (macOS)       ║"
echo "╚══════════════════════════════════╝"
echo ""

# ── 1. Sanity checks ──────────────────────────────────────
command -v python3 >/dev/null 2>&1 || { echo "✗  Python 3 not found"; exit 1; }

PYTHON=python3
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
    echo "→  Using virtualenv: .venv"
fi

# ── 2. Install build dependencies ─────────────────────────
echo "→  Installing build dependencies…"
$PYTHON -m pip install --quiet --upgrade pyinstaller pyinstaller-hooks-contrib Pillow

# ── 3. Generate icons ─────────────────────────────────────
echo "→  Generating icons…"
$PYTHON create_icon.py

# ── 4. Clean previous build ───────────────────────────────
echo "→  Cleaning previous build…"
rm -rf build dist

# ── 5. PyInstaller ────────────────────────────────────────
echo "→  Building MacPlayer.app…"
$PYTHON -m PyInstaller MacPlayer.spec --noconfirm

echo ""
echo "✓  Build complete:  dist/MacPlayer.app"
echo ""

# ── 6. DMG (optional) ─────────────────────────────────────
if command -v create-dmg >/dev/null 2>&1; then
    echo "→  Creating DMG…"
    rm -f dist/MacPlayer.dmg

    create-dmg \
        --volname        "MacPlayer" \
        --volicon        "assets/icon.icns" \
        --window-pos     200 140 \
        --window-size    560 400 \
        --icon-size      128 \
        --icon           "MacPlayer.app" 160 195 \
        --hide-extension "MacPlayer.app" \
        --app-drop-link  390 195 \
        "dist/MacPlayer.dmg" \
        "dist/MacPlayer.app"

    echo "✓  DMG ready:  dist/MacPlayer.dmg"
else
    echo "ℹ  Skipping DMG  (install with: brew install create-dmg)"
fi

echo ""
