#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Bot Udziały – Windows Installer Build Script (v2)
# Builds NSIS installer on Linux
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUNDLE_DIR="$SCRIPT_DIR/bundle"
OUTPUT_DIR="$SCRIPT_DIR/Output"

PYTHON_URL="https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
TOR_URL="https://archive.torproject.org/tor-package-archive/torbrowser/13.5.6/tor-expert-bundle-windows-x86_64-13.5.6.tar.gz"

echo "=== Bot Udziały Installer Builder v2 ==="
echo "Project dir: $PROJECT_DIR"
echo "Bundle dir:  $BUNDLE_DIR"

# Clean previous bundle
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"
mkdir -p "$OUTPUT_DIR"

# -----------------------------------------------------------
# 1. Download Python 3.11.9 full installer
# -----------------------------------------------------------
echo ""
echo "[1/6] Downloading Python 3.11.9 installer..."
if [ ! -f "$SCRIPT_DIR/python-3.11.9-amd64.exe" ]; then
    curl -L -o "$SCRIPT_DIR/python-3.11.9-amd64.exe" "$PYTHON_URL"
else
    echo "  (cached)"
fi
cp "$SCRIPT_DIR/python-3.11.9-amd64.exe" "$BUNDLE_DIR/python-3.11.9-amd64.exe"

# -----------------------------------------------------------
# 2. Download and extract Tor Expert Bundle
# -----------------------------------------------------------
echo ""
echo "[2/6] Downloading Tor Expert Bundle 13.5.6..."
if [ ! -f "$SCRIPT_DIR/tor-expert-bundle-windows-x86_64-13.5.6.tar.gz" ]; then
    curl -L -o "$SCRIPT_DIR/tor-expert-bundle-windows-x86_64-13.5.6.tar.gz" "$TOR_URL"
else
    echo "  (cached)"
fi

echo "  Extracting Tor bundle..."
mkdir -p "$BUNDLE_DIR/tor"
tar -xzf "$SCRIPT_DIR/tor-expert-bundle-windows-x86_64-13.5.6.tar.gz" -C "$BUNDLE_DIR/tor" --strip-components=0

# -----------------------------------------------------------
# 3. Copy project source directories (FLAT layout)
# -----------------------------------------------------------
echo ""
echo "[3/6] Copying source directories..."
for dir in bot scraper detector storage geo data tests; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        cp -r "$PROJECT_DIR/$dir" "$BUNDLE_DIR/$dir"
        echo "  + $dir/"
    else
        echo "  ! $dir/ not found (skipping)"
    fi
done

# -----------------------------------------------------------
# 4. Copy root files
# -----------------------------------------------------------
echo ""
echo "[4/6] Copying root files..."
for file in launcher.pyw config_wizard.pyw config.yaml requirements.txt start_bot.bat stop_bot.bat; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        cp "$PROJECT_DIR/$file" "$BUNDLE_DIR/$file"
        echo "  + $file"
    else
        echo "  ! $file not found (skipping)"
    fi
done

# Copy setup_env.bat from installer directory
cp "$SCRIPT_DIR/setup_env.bat" "$BUNDLE_DIR/setup_env.bat"
echo "  + setup_env.bat"

# -----------------------------------------------------------
# 5. Create torrc
# -----------------------------------------------------------
echo ""
echo "[5/6] Creating tor/torrc..."
mkdir -p "$BUNDLE_DIR/tor"
cp "$SCRIPT_DIR/torrc" "$BUNDLE_DIR/tor/torrc"
echo "  + tor/torrc"

# -----------------------------------------------------------
# 6. Build NSIS installer
# -----------------------------------------------------------
echo ""
echo "[6/6] Building NSIS installer..."
cd "$SCRIPT_DIR"
makensis -DPROJECT_BUNDLE="$BUNDLE_DIR" -DOUTPUT_DIR="$OUTPUT_DIR" setup_v2.nsi

echo ""
echo "=== BUILD COMPLETE ==="
echo "Installer: $OUTPUT_DIR/UdzialyBot-Setup.exe"
ls -lh "$OUTPUT_DIR/UdzialyBot-Setup.exe"
