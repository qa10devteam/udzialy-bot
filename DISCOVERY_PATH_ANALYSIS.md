# DISCOVERY LOOP 1: Forensic Path Analysis

## Installed Layout (NSIS → C:\UdzialyBot\)

```
C:\UdzialyBot\                         ← $INSTDIR (from setup.nsi)
├── python/                            ← File /r "${BUILD_DIR}\python\*.*"
│   ├── python.exe                     ✓ EXISTS
│   ├── pythonw.exe                    ✓ EXISTS (contrary to AXIS-6 claim!)
│   ├── python311._pth                 (import site + Lib/site-packages enabled)
│   ├── python311.dll / python3.dll
│   ├── python311.zip                  (stdlib)
│   ├── get-pip.py
│   └── <pyd files, DLLs>
├── wheels/                            ← File /r "${BUILD_DIR}\wheels\*.*"
│   └── *.whl (cffi, pycparser, selectolax, patchright, certifi, curl_cffi)
├── tor/                               ← File /r "${BUILD_DIR}\tor\*.*"
│   ├── tor.exe
│   ├── torrc                          ⚠️ MINIMAL (no HashedControlPassword!)
│   ├── data/                          ← CreateDirectory
│   ├── geoip / geoip6
│   └── pluggable_transports/
├── app/                               ← File /r "${BUILD_DIR}\app\*.*" = FULL project copy
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py                  ← _find_project_root() starts HERE
│   │   ├── routers/
│   │   ├── keyboards/
│   │   └── middlewares/
│   ├── scraper/
│   ├── detector/
│   ├── storage/
│   ├── geo/
│   ├── data/cities.json
│   ├── config.yaml                    ⚠️ DEV CONFIG (YOUR_BOT_TOKEN_HERE)
│   ├── config.yaml.template
│   ├── config_wizard.pyw              ← FULL 12901-byte wizard (unused!)
│   ├── start_bot.bat                  ← DEV version 3267 bytes (unused!)
│   ├── stop_bot.bat                   ← DEV version (unused!)
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── tor/torrc                      ← HAS HashedControlPassword (unused!)
│   └── <markdown docs, .gitignore, tests/, etc>
├── .venv/                             ← Created by setup_env.bat post-install
│   └── Scripts/
│       ├── python.exe
│       ├── pythonw.exe
│       └── pip.exe
├── setup_env.bat                      ← Runs post-install (NSIS finish page)
├── start_bot.bat                      ← INSTALLER version (975 bytes)
├── stop_bot.bat                       ← INSTALLER version (175 bytes)
├── config_wizard.pyw                  ← STUB version (1764 bytes)
├── icon.ico
├── uninstall.exe
└── config.yaml                        ← Created by config_wizard at RUNTIME
```

---

## Execution Chain Analysis

### Chain 1: setup_env.bat (post-install)

```
1. cd /d "%~dp0"                              → CWD = C:\UdzialyBot\
2. python\python.exe -m venv .venv            → Creates .venv from embedded Python
3. .venv\Scripts\python.exe python\get-pip.py  → Installs pip in venv
4. .venv\Scripts\pip.exe install ... wheels\   → Installs bundled wheels
5. .venv\Scripts\pip.exe install -r app\requirements.txt  → Fallback online
6. .venv\Scripts\python.exe -m patchright install chromium → Downloads browser
7. Checks "config.yaml" existence
8. Launches config_wizard.pyw via pythonw.exe
```

**Issues in setup_env.bat:**
- Step 2: `python -m venv` on embedded Python may fail without ensurepip (no `--without-pip` flag)
- Step 5: References `app\requirements.txt` — this EXISTS (correct path)
- Step 8: Falls back to `python\pythonw.exe` if `.venv\Scripts\pythonw.exe` missing

### Chain 2: start_bot.bat (user runs daily)

```
1. cd /d "%~dp0"                              → CWD = C:\UdzialyBot\
2. start /B "" "tor\tor.exe" -f "tor\torrc" --DataDirectory "tor\data"
3. Wait for Tor SOCKS port 9050
4. .venv\Scripts\python.exe -m bot.main       ← 💥 FATAL ERROR
```

**The `-m bot.main` command:**
- Python adds CWD (`C:\UdzialyBot\`) to sys.path[0]
- Searches for `bot/__init__.py` in sys.path
- `C:\UdzialyBot\bot\` → **DOES NOT EXIST**
- `bot/` lives at `C:\UdzialyBot\app\bot\`
- **RESULT: `ModuleNotFoundError: No module named 'bot'`**

### Chain 3: config_wizard.pyw (Konfiguracja shortcut)

```
NSIS shortcut: python\pythonw.exe "config_wizard.pyw"

config_wizard.pyw (1764 byte stub):
1. os.chdir(os.path.dirname(os.path.abspath(__file__)))  → CWD = C:\UdzialyBot\
2. sys.path.insert(0, os.path.join(..., 'app'))          → Adds C:\UdzialyBot\app\
3. from bot.config_wizard import main                    → ImportError!
4. Falls back to inline minimal tkinter wizard
```

**Issue:** `bot/config_wizard.py` doesn't exist. The full wizard is `app/config_wizard.pyw` (standalone file, not a module inside bot/). Fallback provides only token+owner_id fields (no portal config, no Tor settings).

---

## Path Resolution in bot/config.py

```python
def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent   # C:\UdzialyBot\app\bot\
    for parent in [current.parent, current.parent.parent, Path.cwd()]:
        # current.parent     = C:\UdzialyBot\app\     → app\config.yaml EXISTS!
        # current.parent.parent = C:\UdzialyBot\      → root config.yaml (if wizard ran)
        # Path.cwd()         = C:\UdzialyBot\         → same as above
        if (parent / "config.yaml").exists():
            return parent
```

**Precedence problem:** `app/config.yaml` (dev template) is checked FIRST and found. The user's config at `C:\UdzialyBot\config.yaml` is NEVER reached because iteration stops at first match.

**Result:** Bot always loads the dev config.yaml with `YOUR_BOT_TOKEN_HERE`.

---

## Cross-Package Import Chain

If bot.main could somehow be found and executed:

```python
# bot/main.py
from bot.config import get_settings, PROJECT_ROOT  # OK (bot is already being imported)

# main() does:
sys.path.insert(0, str(PROJECT_ROOT))  # Adds C:\UdzialyBot\app\ to sys.path

# Then routers import:
from scraper.manager import ScraperManager   # ✓ app\scraper\ found
from storage.database import DatabaseManager  # ✓ app\storage\ found
from geo.cities import search_city            # ✓ app\geo\ found
from detector.scorer import PropertyShareScorer # ✓ app\detector\ found (via scraper)
```

**Cross-package imports WOULD work IF the bot module itself could be found first.** The sys.path insert in main() resolves sibling packages because PROJECT_ROOT = app/.

---

## Tor Authentication Chain

| Component | torrc path | HashedControlPassword | Used by |
|-----------|-----------|----------------------|---------|
| `build/tor/torrc` | `C:\UdzialyBot\tor\torrc` | ❌ MISSING | start_bot.bat |
| `app/tor/torrc` | `C:\UdzialyBot\app\tor\torrc` | ✅ Present | NOTHING |
| `bot/config.py` | N/A | expects password `udzialy2026` | TorManager |

**Result:** Tor starts without auth config → rejects control connections → bot can't rotate circuits.

---

## Complete Mismatch Table

| # | Expected Path | Actual Path | Broken? | Impact | Fix |
|---|--------------|-------------|---------|--------|-----|
| 1 | `C:\UdzialyBot\bot\` (for `-m bot.main`) | `C:\UdzialyBot\app\bot\` | **💥 FATAL** | Bot won't start at all | Change start_bot.bat: `cd app && ..\.venv\Scripts\python.exe -m bot.main` OR move source to root |
| 2 | `C:\UdzialyBot\config.yaml` (user's config) | `C:\UdzialyBot\app\config.yaml` found first | **💥 FATAL** | Bot loads dev config, token=YOUR_BOT_TOKEN_HERE | Remove app/config.yaml from build, or fix _find_project_root() order |
| 3 | `C:\UdzialyBot\tor\torrc` (needs HashedControlPassword) | Minimal torrc without auth | **🔴 CRITICAL** | Tor control auth fails, no circuit rotation | build.sh must copy project's tor/torrc or add HashedControlPassword |
| 4 | `C:\UdzialyBot\config_wizard.pyw` (full wizard) | 1764-byte stub, full wizard at `app/config_wizard.pyw` | **🟡 DEGRADED** | User only gets minimal config (token+owner_id) | Stub should import from app/config_wizard directly (not bot.config_wizard) |
| 5 | `python\python.exe -m venv` (needs ensurepip) | Embedded Python may lack ensurepip | **🟡 RISK** | Venv creation may fail on some systems | Add `--without-pip` flag, rely on get-pip.py |
| 6 | `stop_bot.bat` kills only tor.exe + python.exe | `taskkill /IM python.exe /F` | **🟡 DANGEROUS** | Kills ALL python.exe on system (IDE, other scripts) | Use PID file or `wmic` with specific command line filter |
| 7 | `C:\UdzialyBot\data\` (DB + logs) | bot writes to `PROJECT_ROOT/data/` = `app/data/` | **🟡 CONFUSING** | Data hidden inside app/ dir, lost on uninstall/update | Ensure PROJECT_ROOT points to install root |
| 8 | Shortcut: `python\pythonw.exe config_wizard.pyw` | pythonw.exe EXISTS (AXIS-6 was wrong) | ✅ OK | Shortcut works, but runs stub wizard | N/A |
| 9 | `app/` contains dev artifacts (.gitignore, tests/, zip, markdown) | build.sh rsync excludes only __pycache__/.git/.venv | **🟡 BLOAT** | ~200KB+ of unnecessary files in installer | Add excludes for tests/, *.md, *.zip, etc |
| 10 | `start_bot.bat` in app/ (3267 bytes, dev version) | Duplicates + conflicts with root start_bot.bat (975 bytes) | **🟡 CONFUSING** | Two different start_bot.bat in installation | Exclude from app/ copy |

---

## Root Cause Summary

**The fundamental architectural error is the two-level layout:**

```
C:\UdzialyBot\start_bot.bat  →  runs: .venv\Scripts\python.exe -m bot.main
                                         ↑ CWD = C:\UdzialyBot\
                                         ↑ looks for bot\ in CWD
                                         ↑ bot\ is at app\bot\  ← NOT FOUND!
```

The build system copies the **entire project** into `app/` subdirectory but then expects to run `python -m bot.main` from the **parent** directory. This is a fatal structural mismatch.

---

## Recommended Fix Strategy

### Option A: Flatten (move source to root)
Change NSIS to install source files at `$INSTDIR\` directly (not under `app\`):
```nsi
SetOutPath "$INSTDIR"
File /r "${BUILD_DIR}\app\bot\*.*"    → $INSTDIR\bot\
File /r "${BUILD_DIR}\app\scraper\*.*" → $INSTDIR\scraper\
...
```

### Option B: Fix start_bot.bat to cd into app/
```bat
cd /d "%~dp0\app"
"%~dp0\.venv\Scripts\python.exe" -m bot.main
```
And fix config.py to look at `..\\config.yaml` (parent of app/).

### Option C: Add PYTHONPATH (least invasive)
```bat
set PYTHONPATH=%~dp0\app
.venv\Scripts\python.exe -m bot.main
```

**Recommended: Option A** — cleanest, eliminates all path confusion, no duplicate files.

---

## Files Analyzed

| File | Size | Role |
|------|------|------|
| `installer/setup.nsi` | 7407 B | NSIS installer script |
| `installer/build.sh` | 10957 B | Linux build script |
| `installer/setup_env.bat` | 4077 B | Source setup_env |
| `installer/build/setup_env.bat` | 4200 B | Built setup_env (CRLF+BOM) |
| `installer/build/start_bot.bat` | 975 B | Built start_bot |
| `installer/build/stop_bot.bat` | 175 B | Built stop_bot |
| `installer/build/config_wizard.pyw` | 1764 B | Built wizard (stub) |
| `bot/main.py` | 5054 B | Bot entry point |
| `bot/config.py` | 5003 B | Config loader with PROJECT_ROOT |
| `start_bot.bat` (root) | 3267 B | Dev start script |
| `tor/torrc` (root) | 493 B | Project torrc (has hash) |
| `installer/build/tor/torrc` | 95 B | Build torrc (no hash!) |
