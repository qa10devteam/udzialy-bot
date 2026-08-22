# RESEARCH: Installer Architecture V2 — Correct Design

## Status: COMPLETE
## Date: 2026-08-22

---

## 1. NSIS Embedding & Executing Python Installer

### Can NSIS embed and silently execute the Python .exe installer?

**YES.** This is the standard NSIS pattern for bundling prerequisites:

```nsi
; Extract bundled Python installer to $TEMP
SetOutPath $TEMP
File "python-3.11.9-amd64.exe"   ; ~27MB, embedded in our .exe

; Execute silently with custom target directory
DetailPrint "Installing Python 3.11.9..."
ExecWait '"$TEMP\python-3.11.9-amd64.exe" /quiet InstallAllUsers=0 TargetDir=$INSTDIR\python Include_pip=1 Include_tcltk=1 Include_test=0 Include_doc=0 Include_launcher=0 AssociateFiles=0 Shortcuts=0 PrependPath=0' $0
```

**Key points:**
- `File` command embeds the .exe into the NSIS installer at compile time
- At runtime, `SetOutPath $TEMP` + `File` extracts it to user's temp dir
- `ExecWait` runs it and waits for completion (NOT nsExec — Python installer is GUI-based even in /quiet)
- Return code in `$0`: 0 = success
- Delete temp file after: `Delete "$TEMP\python-3.11.9-amd64.exe"`

### Python 3.11.9 Installer Command Line Options (EXACT)

| Flag | Value | Purpose |
|------|-------|---------|
| `/quiet` | (none) | Silent install, no UI at all |
| `/passive` | (none) | Progress bar only, no interaction |
| `InstallAllUsers` | `0` | Per-user install (**NO ADMIN NEEDED**) |
| `TargetDir` | path | Custom install directory |
| `Include_pip` | `1` | Install pip (REQUIRED for us) |
| `Include_tcltk` | `1` | Tkinter for GUI (config wizard needs it) |
| `Include_test` | `0` | Skip test suite (save ~25MB) |
| `Include_doc` | `0` | Skip documentation |
| `Include_launcher` | `0` | Don't install py.exe global launcher |
| `AssociateFiles` | `0` | Don't associate .py files system-wide |
| `Shortcuts` | `0` | Don't create Python Start menu shortcuts |
| `PrependPath` | `0` | Don't modify system/user PATH |
| `CompileAll` | `0` | Skip .pyc precompilation (faster install) |

**Full silent install command:**
```
python-3.11.9-amd64.exe /quiet InstallAllUsers=0 TargetDir=C:\UdzialyBot\python Include_pip=1 Include_tcltk=1 Include_test=0 Include_doc=0 Include_launcher=0 AssociateFiles=0 Shortcuts=0 PrependPath=0 CompileAll=0
```

**No admin required** because `InstallAllUsers=0` installs per-user only.

---

## 2. Installing Packages WITHOUT venv

### The Key Insight

When Python is installed to `C:\UdzialyBot\python\`, it's a **DEDICATED** installation — NOT the user's system Python. We own it entirely. Therefore:

**Just use pip normally. No --target, no --prefix, no venv.**

```bat
python\python.exe -m pip install -r requirements.txt
```

This installs packages directly into `python\Lib\site-packages\` — exactly what we want!

### Why NOT other approaches?

| Approach | Problem |
|----------|---------|
| `--target dir` | Scripts/entry points broken, .pth files ignored, metadata scattered |
| `--prefix dir` | Unnecessary indirection, confusing layout |
| `--user` | Goes to %APPDATA%, not our directory |
| venv | Extra layer, activation scripts, path confusion |
| **Plain `pip install`** | **Installs to interpreter's own site-packages. Perfect for dedicated Python.** |

### Technical: Why full installer Python finds its own packages

The **full** Python installer (NOT the embeddable zip!) uses standard `sys.path`:
- `python\python311.zip` (stdlib compressed)
- `python\Lib\` (stdlib)  
- `python\Lib\site-packages\` (third-party packages)
- `python\DLLs\` (C extensions)

There is NO `python311._pth` file restricting imports (that's the embeddable zip only).

---

## 3. FLAT Layout Design

```
C:\UdzialyBot\                    <- INSTDIR = CWD when bot runs
+-- python\                       <- Full Python 3.11.9
|   +-- python.exe
|   +-- pythonw.exe
|   +-- Lib\
|   |   +-- site-packages\        <- pip installs here
|   +-- Scripts\
|   +-- DLLs\
+-- tor\                          <- Tor Expert Bundle
|   +-- tor.exe
+-- bot\                          <- Main bot package (FLAT, not under app/)
|   +-- __init__.py
|   +-- __main__.py               <- enables `python -m bot`
|   +-- main.py
|   +-- config.py                 <- reads config.yaml from CWD
+-- scraper\
+-- detector\
+-- storage\
+-- geo\
+-- data\                         <- Runtime data (created at runtime)
+-- config.yaml                   <- User configuration (AT ROOT)
+-- config_wizard.pyw
+-- start_bot.bat
+-- stop_bot.bat
+-- setup_env.bat
+-- requirements.txt
+-- uninstall.exe
```

### Why This Layout Works

1. **CWD = `C:\UdzialyBot\`** when start_bot.bat runs -> bot/, scraper/, etc. directly importable
2. **`python -m bot.main`** -> Python adds CWD to sys.path[0], finds bot/ package
3. **`config.yaml` in CWD** -> `Path("config.yaml")` just works
4. **No PATH pollution** -> self-contained, no system changes
5. **No admin** -> per-user Python, everything under one directory
6. **No conflicts** -> private Python won't interfere with any system Python

---

## 4. start_bot.bat

```bat
@echo off
title UdzialyBot - Share Detector
cd /d "%~dp0"

:: Ensure data directory exists
if not exist "data" mkdir data

:: Kill stale processes from previous run
taskkill /f /im tor.exe > nul 2>&1

echo ============================================
echo   UdzialyBot - Starting...
echo ============================================
echo.

:: Start Tor in background
echo [1/2] Starting Tor proxy...
start /B "" "tor\tor.exe" --SocksPort 9050 --DataDirectory "data\tor_data" > "data\tor.log" 2>&1

:: Wait for Tor SOCKS port to be ready
echo      Waiting for Tor to bootstrap...
set RETRIES=0
:wait_tor
timeout /t 2 /nobreak > nul
set /a RETRIES+=1
if %RETRIES% GEQ 15 (
    echo [!] Tor failed to start after 30s. Check data\tor.log
    pause
    exit /b 1
)
python\python.exe -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',9050)); s.close()" 2>nul && goto tor_ready
goto wait_tor

:tor_ready
echo      Tor ready on port 9050!
echo.

:: Start bot (CWD is C:\UdzialyBot, so bot/ package is in sys.path)
echo [2/2] Starting bot...
echo      Press Ctrl+C to stop
echo.
python\python.exe -m bot.main

:: Cleanup on exit
echo.
echo [*] Shutting down Tor...
taskkill /f /im tor.exe > nul 2>&1
echo [*] Done.
timeout /t 3 /nobreak > nul
```

**Key design:**
- `cd /d "%~dp0"` -> CWD = directory where bat lives = C:\UdzialyBot\
- `start /B` -> Tor runs in background, same console
- Socket probe loop -> robust Tor readiness check (not blind sleep)
- `python\python.exe -m bot.main` -> finds bot/ in CWD via sys.path[0]
- On Ctrl+C or bot exit -> Tor gets killed

---

## 5. setup_env.bat (Post-Install, runs once)

```bat
@echo off
title UdzialyBot - First Time Setup
cd /d "%~dp0"

echo ============================================
echo   UdzialyBot - First Time Setup
echo ============================================
echo.
echo   Internet connection required.
echo.

:: Step 1: Install Python packages
echo [1/3] Installing Python packages...
python\python.exe -m pip install --no-warn-script-location --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo [!] FAILED: Could not install packages.
    echo     Check internet connection and run setup_env.bat again.
    pause
    exit /b 1
)
echo      OK!
echo.

:: Step 2: Install Chromium for patchright
echo [2/3] Installing Chromium browser (~150MB download)...
python\python.exe -m patchright install chromium
if errorlevel 1 (
    echo.
    echo [!] FAILED: Could not install Chromium.
    echo     Check internet and run setup_env.bat again.
    pause
    exit /b 1
)
echo      OK!
echo.

:: Step 3: Launch config wizard
echo [3/3] Opening configuration wizard...
start "" "python\pythonw.exe" "config_wizard.pyw"

echo.
echo ============================================
echo   Setup complete!
echo   Configure settings in the wizard, then
echo   run start_bot.bat to launch.
echo ============================================
pause
```

---

## 6. NSIS Uninstaller

### Strategy: Just delete everything

Since our Python is **private** (installed with no system integration), uninstall is trivial:

```nsi
Section "Uninstall"
    ; Kill running processes
    nsExec::ExecToLog 'taskkill /f /im tor.exe'
    nsExec::ExecToLog 'taskkill /f /im python.exe'
    nsExec::ExecToLog 'taskkill /f /im pythonw.exe'
    Sleep 2000

    ; Recursive delete all subdirectories
    RMDir /r "$INSTDIR\python"
    RMDir /r "$INSTDIR\tor"
    RMDir /r "$INSTDIR\bot"
    RMDir /r "$INSTDIR\scraper"
    RMDir /r "$INSTDIR\detector"
    RMDir /r "$INSTDIR\storage"
    RMDir /r "$INSTDIR\geo"
    RMDir /r "$INSTDIR\data"

    ; Remove individual files
    Delete "$INSTDIR\config.yaml"
    Delete "$INSTDIR\config_wizard.pyw"
    Delete "$INSTDIR\start_bot.bat"
    Delete "$INSTDIR\stop_bot.bat"
    Delete "$INSTDIR\setup_env.bat"
    Delete "$INSTDIR\requirements.txt"
    Delete "$INSTDIR\uninstall.exe"

    ; Remove directory itself
    RMDir "$INSTDIR"

    ; Start Menu + Registry
    Delete "$SMPROGRAMS\UdzialyBot\*.lnk"
    RMDir "$SMPROGRAMS\UdzialyBot"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\UdzialyBot"
    DeleteRegKey HKCU "Software\Python\PythonCore\3.11"
SectionEnd
```

### Why no Python uninstaller needed:
- `PrependPath=0` -> no PATH modifications
- `AssociateFiles=0` -> no .py file associations
- `Include_launcher=0` -> no py.exe launcher
- Everything is just files in our directory -> RMDir /r handles it

---

## 7. COMPLETE installer/setup.nsi

```nsi
; ================================================================
; UdzialyBot NSIS Installer Script v2
; Architecture: Flat layout, embedded Python installer, no admin
; ================================================================

!include "MUI2.nsh"
!include "LogicLib.nsh"

; ============================================================
; DEFINES
; ============================================================
!define PRODUCT_NAME "UdzialyBot"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "UdzialyBot"
!define PYTHON_INSTALLER "python-3.11.9-amd64.exe"

; ============================================================
; GENERAL
; ============================================================
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "UdzialyBot-${PRODUCT_VERSION}-Setup.exe"
InstallDir "C:\UdzialyBot"
RequestExecutionLevel user          ; NO ADMIN!
SetCompressor /SOLID lzma
ShowInstDetails show

; ============================================================
; MODERN UI
; ============================================================
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\setup_env.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Run first-time setup (install packages & configure)"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Polish"
!insertmacro MUI_LANGUAGE "English"

; ============================================================
; INSTALLER SECTION
; ============================================================
Section "Install" SecInstall
    SetOutPath $INSTDIR

    ; STEP 1: Silent Python installation
    DetailPrint "Installing Python 3.11.9..."
    SetOutPath $TEMP
    File "bundle\${PYTHON_INSTALLER}"

    ExecWait '"$TEMP\${PYTHON_INSTALLER}" /quiet InstallAllUsers=0 TargetDir=$INSTDIR\python Include_pip=1 Include_tcltk=1 Include_test=0 Include_doc=0 Include_launcher=0 AssociateFiles=0 Shortcuts=0 PrependPath=0 CompileAll=0' $0

    ${If} $0 != 0
        MessageBox MB_OK|MB_ICONSTOP "Python installation failed (code: $0).$\r$\nEnsure ~200MB free disk space."
        Delete "$TEMP\${PYTHON_INSTALLER}"
        Abort
    ${EndIf}
    Delete "$TEMP\${PYTHON_INSTALLER}"

    ; STEP 2: Tor Expert Bundle
    DetailPrint "Installing Tor..."
    SetOutPath $INSTDIR
    File /r "bundle\tor"

    ; STEP 3: Application source (FLAT)
    DetailPrint "Installing application..."
    SetOutPath $INSTDIR
    File /r "source\bot"
    File /r "source\scraper"
    File /r "source\detector"
    File /r "source\storage"
    File /r "source\geo"
    File "source\config_wizard.pyw"
    File "source\start_bot.bat"
    File "source\stop_bot.bat"
    File "source\setup_env.bat"
    File "source\requirements.txt"

    ; Config: don't overwrite existing
    IfFileExists "$INSTDIR\config.yaml" skip_config
        File /oname=config.yaml "source\config.yaml.default"
    skip_config:

    CreateDirectory "$INSTDIR\data"

    ; STEP 4: Uninstaller + Registry
    WriteUninstaller "$INSTDIR\uninstall.exe"

    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME} ${PRODUCT_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "NoRepair" 1

    ; STEP 5: Start Menu
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Start Bot.lnk" "$INSTDIR\start_bot.bat"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Configuration.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\config_wizard.pyw"'
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"

SectionEnd

; ============================================================
; UNINSTALLER
; ============================================================
Section "Uninstall"
    nsExec::ExecToLog 'taskkill /f /im tor.exe'
    nsExec::ExecToLog 'taskkill /f /im python.exe'
    nsExec::ExecToLog 'taskkill /f /im pythonw.exe'
    Sleep 2000

    RMDir /r "$INSTDIR\python"
    RMDir /r "$INSTDIR\tor"
    RMDir /r "$INSTDIR\bot"
    RMDir /r "$INSTDIR\scraper"
    RMDir /r "$INSTDIR\detector"
    RMDir /r "$INSTDIR\storage"
    RMDir /r "$INSTDIR\geo"
    RMDir /r "$INSTDIR\data"

    Delete "$INSTDIR\config.yaml"
    Delete "$INSTDIR\config_wizard.pyw"
    Delete "$INSTDIR\start_bot.bat"
    Delete "$INSTDIR\stop_bot.bat"
    Delete "$INSTDIR\setup_env.bat"
    Delete "$INSTDIR\requirements.txt"
    Delete "$INSTDIR\uninstall.exe"

    RMDir "$INSTDIR"

    Delete "$SMPROGRAMS\${PRODUCT_NAME}\*.lnk"
    RMDir "$SMPROGRAMS\${PRODUCT_NAME}"

    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
    DeleteRegKey HKCU "Software\Python\PythonCore\3.11"
SectionEnd
```

---

## 8. installer/build_v2.sh

```bash
#!/usr/bin/env bash
# ================================================================
# build_v2.sh - Build UdzialyBot Windows installer on Linux
# Prerequisites: sudo apt install nsis wget
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUNDLE_DIR="$SCRIPT_DIR/bundle"
SOURCE_DIR="$SCRIPT_DIR/source"
ASSETS_DIR="$SCRIPT_DIR/assets"

PYTHON_VERSION="3.11.9"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe"
TOR_VERSION="13.0.9"
TOR_URL="https://archive.torproject.org/tor-package-archive/torbrowser/${TOR_VERSION}/tor-expert-bundle-windows-x86_64-${TOR_VERSION}.tar.gz"

echo ""
echo "=== UdzialyBot Installer Builder v2 ==="
echo ""

# Check prerequisites
for cmd in makensis wget tar; do
    command -v "$cmd" &>/dev/null || { echo "ERROR: $cmd not found. Install: sudo apt install nsis wget"; exit 1; }
done

# Clean
rm -rf "$SOURCE_DIR"
mkdir -p "$BUNDLE_DIR" "$SOURCE_DIR" "$ASSETS_DIR"

# Download Python installer (cached)
echo "[1/5] Python ${PYTHON_VERSION}..."
PYTHON_FILE="$BUNDLE_DIR/python-${PYTHON_VERSION}-amd64.exe"
[ -f "$PYTHON_FILE" ] || wget -q --show-progress -O "$PYTHON_FILE" "$PYTHON_URL"
echo "  Size: $(du -h "$PYTHON_FILE" | cut -f1)"

# Download + extract Tor
echo "[2/5] Tor Expert Bundle..."
TOR_ARCHIVE="$BUNDLE_DIR/tor-expert-bundle.tar.gz"
[ -f "$TOR_ARCHIVE" ] || wget -q --show-progress -O "$TOR_ARCHIVE" "$TOR_URL"
rm -rf "$BUNDLE_DIR/tor"
mkdir -p "$BUNDLE_DIR/tor"
tar -xzf "$TOR_ARCHIVE" -C "$BUNDLE_DIR/tor"
echo "  Extracted."

# Copy source (FLAT layout)
echo "[3/5] Application source..."
for pkg in bot scraper detector storage geo; do
    [ -d "$PROJECT_ROOT/$pkg" ] && cp -r "$PROJECT_ROOT/$pkg" "$SOURCE_DIR/$pkg"
done
cp "$PROJECT_ROOT/requirements.txt" "$SOURCE_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/config_wizard.pyw" "$SOURCE_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/config.yaml" "$SOURCE_DIR/config.yaml.default" 2>/dev/null ||     cp "$PROJECT_ROOT/config.yaml.default" "$SOURCE_DIR/config.yaml.default" 2>/dev/null || true

# Generate .bat files
echo "[4/5] Generating batch scripts..."

cat > "$SOURCE_DIR/start_bot.bat" << 'EOF'
@echo off
title UdzialyBot
cd /d "%~dp0"
if not exist "data" mkdir data
taskkill /f /im tor.exe > nul 2>&1
echo [1/2] Starting Tor...
start /B "" "tor	or.exe" --SocksPort 9050 --DataDirectory "data	or_data" > "data	or.log" 2>&1
set RETRIES=0
:wait_tor
timeout /t 2 /nobreak > nul
set /a RETRIES+=1
if %RETRIES% GEQ 15 (echo [!] Tor timeout & pause & exit /b 1)
python\python.exe -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',9050)); s.close()" 2>nul && goto tor_ready
goto wait_tor
:tor_ready
echo      Tor ready!
echo [2/2] Starting bot (Ctrl+C to stop)...
python\python.exe -m bot.main
taskkill /f /im tor.exe > nul 2>&1
EOF

cat > "$SOURCE_DIR/stop_bot.bat" << 'EOF'
@echo off
taskkill /f /im python.exe > nul 2>&1
taskkill /f /im tor.exe > nul 2>&1
echo Stopped.
timeout /t 2 /nobreak > nul
EOF

cat > "$SOURCE_DIR/setup_env.bat" << 'EOF'
@echo off
title UdzialyBot - Setup
cd /d "%~dp0"
echo [1/3] Installing packages...
python\python.exe -m pip install --no-warn-script-location --disable-pip-version-check -r requirements.txt
if errorlevel 1 (echo FAILED & pause & exit /b 1)
echo [2/3] Installing Chromium...
python\python.exe -m patchright install chromium
if errorlevel 1 (echo FAILED & pause & exit /b 1)
echo [3/3] Config wizard...
start "" "python\pythonw.exe" "config_wizard.pyw"
echo Setup complete! Run start_bot.bat to launch.
pause
EOF

# Build NSIS
echo "[5/5] Building NSIS installer..."
cd "$SCRIPT_DIR"
makensis -V2 setup.nsi

echo ""
echo "=== BUILD COMPLETE ==="
ls -lh UdzialyBot-*-Setup.exe 2>/dev/null || echo "(check for output)"
```

---

## 9. Import Resolution

When `start_bot.bat` runs `python\python.exe -m bot.main` with CWD = `C:\UdzialyBot\`:

```
sys.path[0] = "C:\UdzialyBot"                      <- CWD (added by -m flag)
sys.path[1] = "C:\UdzialyBot\python\python311.zip"
sys.path[2] = "C:\UdzialyBot\python\Lib"
sys.path[3] = "C:\UdzialyBot\python\DLLs"
sys.path[4] = "C:\UdzialyBot\python"
sys.path[5] = "C:\UdzialyBot\python\Lib\site-packages"
```

- `from bot.config import load_config` -> sys.path[0] -> bot/config.py
- `from scraper.engine import Scraper` -> sys.path[0] -> scraper/engine.py
- `import patchright` -> sys.path[5] -> site-packages/patchright/
- `import yaml` -> sys.path[5] -> site-packages/yaml/

**Zero sys.path manipulation needed.**

### bot/__main__.py:
```python
from bot.main import main
if __name__ == "__main__":
    main()
```

### bot/config.py:
```python
from pathlib import Path
import yaml

def load_config() -> dict:
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("config.yaml not found. Run config_wizard.pyw first.")
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))
```

---

## 10. Architecture Decisions Summary

| Decision | Choice | Why |
|----------|--------|-----|
| Python dist | Full installer .exe (~27MB) | Tkinter, pip, all stdlib works |
| Embed method | NSIS File + ExecWait /quiet | Single-file distribution |
| Package install | Plain `pip install` (no venv) | Dedicated Python = we own site-packages |
| App layout | FLAT (packages at INSTDIR root) | `-m bot.main` works with CWD in sys.path |
| Admin rights | NOT REQUIRED | `InstallAllUsers=0`, HKCU registry only |
| Tor bundle | Pre-extracted in installer | Offline install |
| Config location | config.yaml at root | Bot CWD = INSTDIR, Path("config.yaml") works |
| Uninstall | RMDir /r | Private Python = no system footprint |
| Post-install | setup_env.bat | pip + chromium + wizard, needs internet once |
| Upgrade safety | IfFileExists config.yaml | Preserves user settings |

---

## 11. Size Estimates

| Component | Size |
|-----------|------|
| Python installer (in NSIS) | ~27 MB |
| Tor Expert Bundle (in NSIS) | ~15 MB |
| App source | ~500 KB |
| **Installer .exe** | **~43 MB** |
| After full setup (on disk) | **~350 MB** |

---

## 12. Pitfalls & Mitigations

| Pitfall | Mitigation |
|---------|-----------|
| pip needs internet | Clear error in setup_env.bat, retryable |
| AV blocks tor.exe | Document in README, consider signing |
| Existing system Python | Ours is private, zero conflict |
| SmartScreen | Code-sign or document "Run anyway" |
| Disk space | User can change InstallDir |
| Tor port 9050 busy | start_bot kills stale tor first |
| Upgrade overwrites config | NSIS IfFileExists preserves it |
| Unicode in path | Default path is ASCII, document limitation |

---

## 13. Build Directory Layout

```
udzialy-bot/                      <- PROJECT_ROOT
+-- bot/
+-- scraper/
+-- detector/
+-- storage/
+-- geo/
+-- config.yaml
+-- config_wizard.pyw
+-- requirements.txt
+-- installer/                    <- INSTALLER BUILD SYSTEM
    +-- setup.nsi               <- NSIS script
    +-- build_v2.sh            <- Build script
    +-- assets/
    |   +-- icon.ico
    +-- bundle/                 <- Downloaded (GITIGNORED)
    |   +-- python-3.11.9-amd64.exe
    |   +-- tor-expert-bundle.tar.gz
    |   +-- tor/
    +-- source/                 <- Built (GITIGNORED)
    +-- UdzialyBot-1.0.0-Setup.exe  <- OUTPUT (GITIGNORED)
```

### .gitignore:
```
installer/bundle/
installer/source/
installer/*.exe
```
