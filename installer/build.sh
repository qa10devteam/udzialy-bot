#!/bin/bash
# ============================================================================
# Udzialy Bot — Windows Installer Build Script
# Runs on Linux, produces a Windows .exe installer via NSIS (makensis)
# Publisher: QA10 sp. z o.o.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT_DIR="$SCRIPT_DIR/Output"

PYTHON_VERSION="3.11.9"
PYTHON_EMBED_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip"
GET_PIP_URL="https://bootstrap.pypa.io/get-pip.py"
TOR_VERSION="13.5.6"
TOR_BUNDLE_URL="https://archive.torproject.org/tor-package-archive/torbrowser/${TOR_VERSION}/tor-expert-bundle-windows-x86_64-${TOR_VERSION}.tar.gz"
TOR_BUNDLE_URL_FALLBACK="https://dist.torproject.org/torbrowser/${TOR_VERSION}/tor-expert-bundle-windows-x86_64-${TOR_VERSION}.tar.gz"

# Pure Python packages (no binary wheels needed — platform-independent)
PURE_PACKAGES=(
    "aiogram>=3.10"
    "aiosqlite>=0.19"
    "httpx[socks]>=0.27"
    "stem>=1.8"
    "PySocks>=1.7"
    "beautifulsoup4>=4.12"
    "pydantic>=2.0"
    "pydantic-settings>=2.0"
    "pyyaml>=6.0"
    "primp>=1.3"
    "nodriver>=0.38"
)

# Binary packages that need win_amd64 platform wheels
BINARY_PACKAGES=(
    "curl_cffi>=0.7"
    "selectolax>=0.3"
)

# Post-install packages (too large to bundle or require post-install steps)
# patchright downloads Chromium (~280MB) at runtime
POST_INSTALL_PACKAGES=(
    "patchright>=1.0"
)

# ============================================================================
echo "=== Udzialy Bot Installer Build ==="
echo "=== Build directory: $BUILD_DIR ==="
echo ""

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"/{python,wheels,tor,app}
mkdir -p "$OUTPUT_DIR"

# ============================================================================
# Step 1: Download Python Embedded for Windows
# ============================================================================
echo "[1/6] Downloading Python ${PYTHON_VERSION} embedded (amd64)..."
PYTHON_ZIP="$BUILD_DIR/python-embed.zip"

if [ ! -f "$PYTHON_ZIP" ]; then
    curl -sSL -o "$PYTHON_ZIP" "$PYTHON_EMBED_URL"
fi

echo "  Extracting..."
unzip -qo "$PYTHON_ZIP" -d "$BUILD_DIR/python/"

# Enable site-packages in embedded Python
PTH_FILE="$BUILD_DIR/python/python311._pth"
if [ -f "$PTH_FILE" ]; then
    sed -i 's/^#import site/import site/' "$PTH_FILE"
    echo "Lib/site-packages" >> "$PTH_FILE"
    echo "  Enabled site-packages in python311._pth"
fi

# ============================================================================
# Step 2: Download get-pip.py
# ============================================================================
echo "[2/6] Downloading get-pip.py..."
curl -sSL -o "$BUILD_DIR/python/get-pip.py" "$GET_PIP_URL"

# ============================================================================
# Step 3: Download wheel dependencies (multi-phase)
# ============================================================================
echo "[3/6] Downloading wheel dependencies..."

# Phase 1: Pure Python wheels (no platform constraint)
echo "  Phase 1: Pure Python packages..."
pip download --dest "$BUILD_DIR/wheels/" \
    --python-version 3.11 \
    --implementation cp \
    --only-binary=:all: \
    --no-deps \
    "${PURE_PACKAGES[@]}" 2>/dev/null || true

# Phase 1b: Pure Python with deps resolution (any platform)
echo "  Phase 1b: Pure Python packages (with deps)..."
pip download --dest "$BUILD_DIR/wheels/" \
    --python-version 3.11 \
    --implementation cp \
    --abi none \
    --platform any \
    --only-binary=:all: \
    "${PURE_PACKAGES[@]}" 2>/dev/null || true

# Phase 2: Binary wheels for win_amd64
echo "  Phase 2: Binary packages (win_amd64)..."
pip download --dest "$BUILD_DIR/wheels/" \
    --platform win_amd64 \
    --python-version 3.11 \
    --implementation cp \
    --abi cp311 \
    --only-binary=:all: \
    "${BINARY_PACKAGES[@]}" 2>/dev/null || true

# Phase 3: Combined pass for remaining transitive deps
echo "  Phase 3: Transitive dependencies (multi-platform)..."
pip download --dest "$BUILD_DIR/wheels/" \
    --platform win_amd64 \
    --platform any \
    --python-version 3.11 \
    --implementation cp \
    --abi cp311 --abi none \
    --only-binary=:all: \
    "${PURE_PACKAGES[@]}" "${BINARY_PACKAGES[@]}" 2>/dev/null || true

# Phase 4: patchright wheel only (browser download is post-install)
echo "  Phase 4: Patchright wheel (browser download is post-install)..."
pip download --dest "$BUILD_DIR/wheels/" \
    --platform win_amd64 \
    --python-version 3.11 \
    --implementation cp \
    --abi cp311 --abi none \
    --only-binary=:all: \
    --no-deps \
    "patchright>=1.0" 2>/dev/null || true

# Deduplicate wheels (keep newest version of each package)
echo "  Deduplicating wheels..."
WHEEL_COUNT=$(ls "$BUILD_DIR/wheels/"*.whl 2>/dev/null | wc -l)
echo "  Total wheels downloaded: $WHEEL_COUNT"

# ============================================================================
# Step 4: Download Tor Expert Bundle
# ============================================================================
echo "[4/6] Downloading Tor Expert Bundle ${TOR_VERSION}..."
TOR_ARCHIVE="$BUILD_DIR/tor-bundle.tar.gz"

if [ ! -f "$TOR_ARCHIVE" ]; then
    curl -sSL -o "$TOR_ARCHIVE" "$TOR_BUNDLE_URL" || \
    curl -sSL -o "$TOR_ARCHIVE" "$TOR_BUNDLE_URL_FALLBACK"
fi

echo "  Extracting..."
tar -xzf "$TOR_ARCHIVE" -C "$BUILD_DIR/tor/"

# Flatten nested directory if exists (tor/tor/*.exe -> tor/*.exe)
if [ -d "$BUILD_DIR/tor/tor" ]; then
    mv "$BUILD_DIR/tor/tor/"* "$BUILD_DIR/tor/" 2>/dev/null || true
    rmdir "$BUILD_DIR/tor/tor" 2>/dev/null || true
fi

# Create default torrc
cat > "$BUILD_DIR/tor/torrc" << 'EOF'
SocksPort 9050
ControlPort 9051
DataDirectory data
Log notice file notices.log
ClientUseIPv4 1
EOF

# ============================================================================
# Step 5: Bundle project source
# ============================================================================
echo "[5/6] Bundling project source..."

# Copy source code (exclude dev/build artifacts)
rsync -a --exclude='__pycache__' \
         --exclude='*.pyc' \
         --exclude='.git' \
         --exclude='.venv' \
         --exclude='installer' \
         --exclude='.pytest_cache' \
         --exclude='*.log' \
         --exclude='.env' \
         "$PROJECT_DIR/" "$BUILD_DIR/app/"

# Copy installer support files
cp "$SCRIPT_DIR/setup_env.bat" "$BUILD_DIR/"
cp "$SCRIPT_DIR/icon.ico" "$BUILD_DIR/" 2>/dev/null || true

# Create start_bot.bat (written inline, converted to CRLF+BOM later)
cat > "$BUILD_DIR/start_bot.bat" << 'BATEOF'
@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo   Udzialy Bot - Uruchamianie...
echo ============================================
echo.

REM Start Tor in background
echo [*] Uruchamianie Tor...
start /B "" "tor\tor.exe" -f "tor\torrc" --DataDirectory "tor\data"

REM Wait for Tor to be ready (max 60s)
set TOR_READY=0
for /L %%i in (1,1,30) do (
    if !TOR_READY!==0 (
        timeout /t 2 /nobreak >nul
        powershell -Command "& { try { $c = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 9050); $c.Close(); exit 0 } catch { exit 1 } }" >nul 2>&1
        if not errorlevel 1 (
            set TOR_READY=1
            echo [OK] Tor gotowy.
        )
    )
)

if !TOR_READY!==0 (
    echo [UWAGA] Tor nie uruchomil sie w ciagu 60s - bot moze nie dzialac prawidlowo.
)

echo [*] Uruchamianie bota...
.venv\Scripts\python.exe -m bot.main
pause
BATEOF

# Create stop_bot.bat
cat > "$BUILD_DIR/stop_bot.bat" << 'BATEOF'
@echo off
chcp 65001 >nul 2>&1
echo Zatrzymywanie bota i Tor...
taskkill /IM python.exe /F >nul 2>&1
taskkill /IM tor.exe /F >nul 2>&1
echo Zatrzymano.
timeout /t 3
BATEOF

# Create config_wizard.pyw launcher
cat > "$BUILD_DIR/config_wizard.pyw" << 'PYEOF'
"""Udzialy Bot - Configuration Wizard (GUI)"""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
try:
    from bot.config_wizard import main
    main()
except ImportError:
    import tkinter as tk
    from tkinter import messagebox, ttk

    def save_config():
        try:
            import yaml
        except ImportError:
            import json
            yaml = None
        config = {
            'telegram': {
                'token': token_var.get().strip(),
                'owner_id': int(owner_var.get().strip()) if owner_var.get().strip() else 0,
            },
            'tor': {'socks_port': 9050, 'control_port': 9051}
        }
        with open('config.yaml', 'w', encoding='utf-8') as f:
            if yaml:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            else:
                import json
                json.dump(config, f, indent=2)
        messagebox.showinfo('Sukces', 'Konfiguracja zapisana!')
        root.destroy()

    root = tk.Tk()
    root.title('Udzialy Bot - Konfiguracja')
    root.geometry('450x250')
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Token bota Telegram:').pack(anchor='w')
    token_var = tk.StringVar()
    ttk.Entry(frame, textvariable=token_var, width=50).pack(fill='x', pady=(0, 10))
    ttk.Label(frame, text='ID wlasciciela (Telegram):').pack(anchor='w')
    owner_var = tk.StringVar()
    ttk.Entry(frame, textvariable=owner_var, width=20).pack(anchor='w', pady=(0, 15))
    ttk.Button(frame, text='Zapisz konfiguracje', command=save_config).pack()
    root.mainloop()
PYEOF

# ============================================================================
# Step 6: Build NSIS installer
# ============================================================================
echo "[6/6] Building NSIS installer..."

# Convert bat files to CRLF + UTF-8 BOM for Windows
for batfile in "$BUILD_DIR/start_bot.bat" "$BUILD_DIR/stop_bot.bat" "$BUILD_DIR/setup_env.bat"; do
    if [ -f "$batfile" ]; then
        python3 -c "
import sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    content = f.read()
with open(sys.argv[1], 'wb') as f:
    f.write(b'\xef\xbb\xbf')
    f.write(content.replace('\n', '\r\n').encode('utf-8'))
" "$batfile"
        echo "  Converted $(basename "$batfile") to CRLF+BOM"
    fi
done

# Run makensis
if command -v makensis &>/dev/null; then
    makensis -DBUILD_DIR="$BUILD_DIR" "$SCRIPT_DIR/setup.nsi"
    echo ""
    echo "=== BUILD COMPLETE ==="
    echo "Installer: $OUTPUT_DIR/UdzialyBot-Setup.exe"
    file "$OUTPUT_DIR/UdzialyBot-Setup.exe" 2>/dev/null || true
else
    echo "[ERROR] makensis not found. Install with: sudo apt-get install -y nsis"
    exit 1
fi
