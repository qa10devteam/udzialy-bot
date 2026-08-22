# RESEARCH: Integration Architecture & Config Schema (Loops 5-6)

## Status: COMPLETE
## Date: 2026-08-22

---

## 1. Integration Architecture — Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        D:\UdzialyBot\  (INSTDIR = CWD)              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  launcher.pyw  (pythonw.exe — NO CONSOLE)                    │    │
│  │  ─────────────────────────────────────────────────────────   │    │
│  │  • Tkinter GUI (SetupWizard → Dashboard)                    │    │
│  │  • reads/writes: config.yaml                                 │    │
│  │  • subprocess.Popen: tor\tor.exe (CREATE_NO_WINDOW)          │    │
│  │  • subprocess.Popen: python\python.exe -u -m bot.main        │    │
│  │  • Thread reader → Queue → after(100ms) poll                 │    │
│  │  • taskkill /T /F /PID for tree kill                         │    │
│  └──────┬──────────────────────┬────────────────────────────────┘    │
│         │                      │                                     │
│         │ manages              │ manages                             │
│         ▼                      ▼                                     │
│  ┌──────────────┐     ┌──────────────────────────────────────┐      │
│  │ tor\tor.exe  │     │ python\python.exe -u -m bot.main     │      │
│  │              │     │ (CWD = D:\UdzialyBot)                │      │
│  │ SOCKS: 9050 │     │                                      │      │
│  │ Ctrl:  9051 │     │  ┌────────────────────────────────┐  │      │
│  └──────────────┘     │  │  bot/main.py                   │  │      │
│         ▲              │  │  • aiogram Dispatcher          │  │      │
│         │              │  │  • registers routers           │  │      │
│         │              │  │  • reads config via bot/config │  │      │
│         │              │  └─────────────┬────────────────┘  │      │
│         │              │                │                    │      │
│         │              │  ┌─────────────┼───────────────┐   │      │
│         │              │  │             │               │   │      │
│         │              │  ▼             ▼               ▼   │      │
│  ┌──────┴──────┐      │ scraper/     detector/      storage/ │      │
│  │ config.yaml │      │ manager.py   scorer.py      database │      │
│  │ (SHARED)    │      │ portals/*    llm_analyzer   models   │      │
│  │             │      │ base.py      keywords       queries  │      │
│  └─────────────┘      │ stealth.py                          │      │
│                        │ tor_manager                          │      │
│                        └──────────────────────────────────────┘      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User clicks "Start" in launcher.pyw
    │
    ├─1→ spawn tor\tor.exe (CREATE_NO_WINDOW)
    │       └→ wait_for_port(9050, timeout=60)
    │
    ├─2→ spawn python\python.exe -u -m bot.main (CREATE_NO_WINDOW)
    │       │
    │       ├→ bot/config.py loads config.yaml (same file launcher wrote)
    │       ├→ aiogram.Dispatcher starts polling Telegram
    │       ├→ user sends /szukaj → ScraperManager.search_all()
    │       │       ├→ portals scrape via Tor SOCKS5 proxy
    │       │       ├→ PropertyShareScorer filters results
    │       │       ├→ ListingAnalyzer (LLM) analyzes top hits
    │       │       └→ DatabaseManager stores results
    │       └→ bot sends results back via Telegram
    │
    └─3→ launcher polls bot stdout via Queue + after(100ms)
            └→ displays log in Dashboard ScrolledText widget
```

---

## 2. Config File — Race Condition Analysis

### Question: Can launcher + bot BOTH read/write config.yaml simultaneously?

**Answer: NO RACE CONDITION in the designed architecture.**

| Actor | Reads config.yaml | Writes config.yaml | When |
|-------|:-:|:-:|------|
| launcher.pyw | ✅ | ✅ | At startup (load) + when user clicks "Save" in Settings |
| bot/main.py | ✅ | ❌ | Once at startup (`get_settings()` singleton) |
| bot (at runtime) | ❌ | ❌ | Never re-reads config during operation |

**Safety guarantees:**

1. **Launcher writes config ONLY when bot is STOPPED** — Settings dialog is available only from Dashboard "⚙️ Ustawienia" button. The designed workflow:
   - User stops bot → opens Settings → edits → saves → restarts bot
   - The config wizard (first-run) runs BEFORE the bot ever starts

2. **Bot reads config ONCE at startup** — `get_settings()` uses a singleton pattern. After initialization, config values are frozen in memory. No hot-reload.

3. **If we ever need live-reload** (future enhancement):
   - Use file locking: `fcntl.flock()` / `msvcrt.locking()` — NOT needed for v1.0
   - Or: launcher sends SIGUSR1/custom signal to bot to trigger re-read — overkill

**Design rule: Launcher MUST stop the bot before allowing config save. Enforce this in GUI (disable Save button while bot is running, or force stop before applying).**

---

## 3. Final config.yaml Schema (COMPLETE)

```yaml
# =============================================================================
# Udziały Bot — Configuration
# Generated by launcher.pyw | Manual edits OK
# =============================================================================

# --- Telegram Bot ---
telegram:
  token: "YOUR_BOT_TOKEN_HERE"     # BotFather token (required)
  owner_id: 0                       # Your Telegram user ID (required)

# --- LLM Analysis (optional — bot works without it) ---
llm:
  enabled: true                     # false = skip all LLM analysis
  provider: "openai"                # openai | anthropic | local
  api_key: ""                       # API key (leave empty to disable)
  model: "gpt-4o-mini"             # Model name for provider
  base_url: "https://api.openai.com/v1"  # API endpoint URL
  max_concurrent: 5                 # Max parallel LLM calls (semaphore)
  timeout: 15                       # Per-call timeout in seconds

# --- Portal Scrapers ---
portals:
  otodom:
    enabled: true
    base_url: "https://www.otodom.pl"
  olx:
    enabled: true
    base_url: "https://www.olx.pl"
  gratka:
    enabled: true
    base_url: "https://gratka.pl"
  morizon:
    enabled: true
    base_url: "https://www.morizon.pl"
  nieruchomosci_online:
    enabled: true
    base_url: "https://www.nieruchomosci-online.pl"
  domiporta:
    enabled: true
    base_url: "https://www.domiporta.pl"
  lento:
    enabled: true
    base_url: "https://www.lento.pl"
  gethome:
    enabled: true
    base_url: "https://gethome.pl"
  ogloszenia24:
    enabled: false
    base_url: "https://www.ogloszenia24.pl"

# --- Tor Proxy ---
tor:
  enabled: true                     # false = direct connection (no anonymity)
  socks_port: 9050                  # SOCKS5 proxy port
  control_port: 9051                # Tor control port (for circuit rotation)
  control_password: "udzialy2026"   # HashedControlPassword in torrc
  circuit_rotate_interval: 300      # Rotate Tor circuit every N seconds
  binary_path: "tor\\tor.exe"       # Relative to INSTDIR (or absolute)

# --- Scraping Behavior ---
scraping:
  timeout: 30                       # HTTP request timeout (seconds)
  max_concurrent: 3                 # Max concurrent requests per portal
  retry_count: 2                    # Retries on failure per request
  retry_delay: 5                    # Delay between retries (seconds)
  delay_between: 2                  # Delay between sequential portal requests
  user_agent_rotate: true           # Rotate User-Agent headers

# --- Database ---
database:
  path: "data\\udzialy.db"          # SQLite database path (relative to CWD)

# --- Logging ---
logging:
  level: "INFO"                     # DEBUG | INFO | WARNING | ERROR
  file: "data\\bot.log"             # Log file path (relative to CWD)

# --- Scorer ---
scorer:
  threshold: 25                     # Minimum score for LLM analysis trigger
  keywords_file: ""                 # Custom keywords file (empty = use built-in)
```

### Schema Documentation Table

| Section | Field | Type | Default | Required | Description |
|---------|-------|------|---------|:--------:|-------------|
| telegram | token | string | "" | ✅ | BotFather API token |
| telegram | owner_id | int | 0 | ✅ | Telegram user ID of bot owner |
| llm | enabled | bool | true | ❌ | Master LLM on/off switch |
| llm | provider | string | "openai" | ❌ | LLM provider: openai, anthropic, local |
| llm | api_key | string | "" | ❌ | API key (empty = LLM disabled gracefully) |
| llm | model | string | "gpt-4o-mini" | ❌ | Model identifier |
| llm | base_url | string | "https://api.openai.com/v1" | ❌ | API endpoint (change for local/Anthropic) |
| llm | max_concurrent | int | 5 | ❌ | Concurrency limit for API calls |
| llm | timeout | int | 15 | ❌ | Per-call timeout (seconds) |
| portals.{name} | enabled | bool | true | ❌ | Enable/disable individual portal |
| portals.{name} | base_url | string | varies | ❌ | Portal base URL (for reference) |
| tor | enabled | bool | true | ❌ | Enable Tor proxy |
| tor | socks_port | int | 9050 | ❌ | SOCKS5 proxy port |
| tor | control_port | int | 9051 | ❌ | Control port for circuit rotation |
| tor | control_password | string | "udzialy2026" | ❌ | Control auth password |
| tor | circuit_rotate_interval | int | 300 | ❌ | Auto-rotate circuit every N sec |
| tor | binary_path | string | "tor\\tor.exe" | ❌ | Path to Tor binary |
| scraping | timeout | int | 30 | ❌ | HTTP request timeout |
| scraping | max_concurrent | int | 3 | ❌ | Per-portal concurrency |
| scraping | retry_count | int | 2 | ❌ | Retry attempts per request |
| scraping | retry_delay | int | 5 | ❌ | Retry wait (seconds) |
| scraping | delay_between | int | 2 | ❌ | Inter-portal delay |
| scraping | user_agent_rotate | bool | true | ❌ | Rotate UA headers |
| database | path | string | "data\\udzialy.db" | ❌ | SQLite file path |
| logging | level | string | "INFO" | ❌ | Minimum log level |
| logging | file | string | "data\\bot.log" | ❌ | Log file path |
| scorer | threshold | int | 25 | ❌ | Min score for LLM analysis |
| scorer | keywords_file | string | "" | ❌ | Custom keywords path |

### Provider Presets (launcher auto-fills these)

| Provider | base_url | model (default) | Notes |
|----------|----------|-----------------|-------|
| openai | https://api.openai.com/v1 | gpt-4o-mini | Cheapest, best for this task |
| anthropic | https://api.anthropic.com/v1 | claude-3-5-haiku-20241022 | Needs `x-api-key` header |
| local | http://localhost:1234/v1 | (auto-detect) | LM Studio / Ollama |
| groq | https://api.groq.com/openai/v1 | llama-3.1-8b-instant | Free tier, fast |

---

## 4. File Layout — Final Flat Structure (After Install)

```
D:\UdzialyBot\                          ← INSTDIR = CWD for all scripts
│
├── python\                             ← Full Python 3.11.9 (private install)
│   ├── python.exe                      ← Main interpreter
│   ├── pythonw.exe                     ← No-console interpreter (for launcher)
│   ├── Lib\
│   │   └── site-packages\             ← All pip packages installed here
│   ├── Scripts\
│   │   └── pip.exe
│   └── DLLs\
│
├── tor\                                ← Tor Expert Bundle
│   ├── tor.exe
│   ├── torrc                           ← WITH HashedControlPassword
│   ├── geoip
│   ├── geoip6
│   └── data\                           ← Created at runtime (Tor state)
│
├── bot\                                ← Main bot package (FLAT at root)
│   ├── __init__.py
│   ├── __main__.py                     ← enables `python -m bot`
│   ├── main.py                         ← Entry point (aiogram setup)
│   ├── config.py                       ← Settings loader (reads ../config.yaml)
│   ├── routers\
│   │   ├── __init__.py
│   │   ├── search.py                   ← /szukaj command
│   │   ├── saved.py                    ← /zapisane command
│   │   ├── settings.py                 ← /ustawienia command
│   │   └── filters.py                  ← /filtry command
│   ├── keyboards\
│   │   ├── __init__.py
│   │   ├── inline.py
│   │   └── reply.py
│   └── middlewares\
│       ├── __init__.py
│       └── throttle.py
│
├── scraper\                            ← Web scraping engine
│   ├── __init__.py
│   ├── manager.py                      ← ScraperManager orchestrator
│   ├── base.py                         ← BaseScraper ABC
│   ├── stealth.py                      ← Anti-detection (curl_cffi)
│   ├── tor_manager.py                  ← Tor SOCKS5 client
│   └── portals\
│       ├── __init__.py
│       ├── otodom.py                   ← nodriver (Layer 5)
│       ├── olx.py                      ← curl_cffi + Tor
│       ├── morizon.py                  ← curl_cffi + Tor
│       └── domiporta.py                ← curl_cffi + Tor
│
├── detector\                           ← Share detection intelligence
│   ├── __init__.py
│   ├── scorer.py                       ← PropertyShareScorer
│   ├── keywords.py                     ← SEARCH_QUERIES list
│   ├── filters.py                      ← Rule-based filters
│   └── llm_analyzer.py                 ← ListingAnalyzer (multi-provider)
│
├── storage\                            ← Database layer
│   ├── __init__.py
│   ├── database.py                     ← DatabaseManager (aiosqlite)
│   ├── models.py                       ← Dataclass models
│   └── queries.py                      ← SQL query constants
│
├── geo\                                ← Geolocation
│   ├── __init__.py
│   ├── cities.py                       ← City search + matching
│   └── distance.py                     ← Haversine distance calc
│
├── data\                               ← Runtime data (created on first run)
│   ├── udzialy.db                      ← SQLite database
│   ├── bot.log                         ← Application log
│   ├── cities.json                     ← City database
│   └── tor_data\                       ← Tor state directory
│
├── config.yaml                         ← USER CONFIGURATION (at root!)
├── launcher.pyw                        ← MAIN ENTRY POINT (GUI)
├── setup_env.bat                       ← First-run setup (pip install)
├── requirements.txt                    ← Python dependencies
├── icon.ico                            ← App icon
└── uninstall.exe                       ← NSIS uninstaller
```

### Key References (What Reads What)

| Component | Reads | Writes | Starts |
|-----------|-------|--------|--------|
| launcher.pyw | config.yaml | config.yaml | tor\tor.exe, python\python.exe -m bot.main |
| bot/config.py | config.yaml | — | — |
| bot/main.py | (via config.py) | data/bot.log | — |
| scraper/manager.py | (via bot/config) | — | (HTTP requests via Tor) |
| detector/llm_analyzer.py | (via scraper/manager) | — | (HTTP to LLM API) |
| storage/database.py | data/udzialy.db | data/udzialy.db | — |

### Path Resolution Design

**`bot/config.py` — Fixed algorithm:**
```python
def _find_project_root() -> Path:
    """Find config.yaml — PRIORITY: CWD first, then parent dirs."""
    # 1. CWD (the correct path when launched via launcher/bat)
    if (Path.cwd() / "config.yaml").exists():
        return Path.cwd()
    # 2. Parent of this file's directory (bot/ → D:\UdzialyBot\)
    parent = Path(__file__).resolve().parent.parent
    if (parent / "config.yaml").exists():
        return parent
    # 3. Fallback: CWD
    return Path.cwd()
```

**Why CWD-first works:**
- launcher.pyw starts bot with `cwd=SCRIPT_DIR` (D:\UdzialyBot)
- start_bot.bat has `cd /d "%~dp0"` (sets CWD to D:\UdzialyBot)
- config.yaml lives at D:\UdzialyBot\config.yaml
- `python -m bot.main` adds CWD to sys.path → bot/ found, config in CWD found

**Critical fix from DISCOVERY_PATH_ANALYSIS:** The old code checked `app/config.yaml` FIRST (dev template). New code checks CWD first, which is always INSTDIR for production.

---

## 5. Installer Integration — New Architecture with launcher.pyw

### Install Sequence

```
NSIS Installer
    │
    ├─1→ Install Python 3.11.9 to $INSTDIR\python\ (silent, per-user)
    ├─2→ Install Tor bundle to $INSTDIR\tor\
    ├─3→ Install source code (bot/, scraper/, detector/, storage/, geo/)
    ├─4→ Install support files (launcher.pyw, requirements.txt, icon.ico)
    ├─5→ Create shortcuts (Desktop + Start Menu → launcher.pyw)
    ├─6→ Write uninstaller
    │
    └─7→ FINISH PAGE: "Uruchom konfigurację" (checked by default)
              │
              └→ Exec: "$INSTDIR\python\pythonw.exe" "$INSTDIR\launcher.pyw" --first-run
```

### First Run Sequence (setup_env.bat is ELIMINATED)

```
launcher.pyw --first-run
    │
    ├─1→ Detect: config.yaml missing? → Show SetupWizard
    │       ├─ Step 1: pip install -r requirements.txt (background thread, progress bar)
    │       ├─ Step 2: patchright install chromium (background thread)
    │       ├─ Step 3: Token + Owner ID input
    │       ├─ Step 4: (Optional) LLM API key + provider selection
    │       ├─ Step 5: Portal selection checkboxes
    │       └─ Step 6: Save config.yaml → Done
    │
    └─2→ Show Dashboard (ready to Start)
```

**Why eliminate setup_env.bat:**
- Launcher.pyw already has full wizard capability (SetupWizard class)
- Can show real progress bars for pip install (via subprocess + Queue)
- Can handle errors gracefully (GUI error dialog vs. cmd window vanishing)
- Single entry point = simpler mental model for user

### Shortcuts (NSIS Post-Install Section)

```nsi
; --- Desktop Shortcut ---
CreateShortCut "$DESKTOP\Bot Udziały.lnk" \
    "$INSTDIR\python\pythonw.exe" \
    '"$INSTDIR\launcher.pyw"' \
    "$INSTDIR\icon.ico" 0

; --- Start Menu ---
CreateDirectory "$SMPROGRAMS\Bot Udziały"
CreateShortCut "$SMPROGRAMS\Bot Udziały\Bot Udziały.lnk" \
    "$INSTDIR\python\pythonw.exe" \
    '"$INSTDIR\launcher.pyw"' \
    "$INSTDIR\icon.ico" 0
CreateShortCut "$SMPROGRAMS\Bot Udziały\Odinstaluj.lnk" \
    "$INSTDIR\uninstall.exe"
```

**No more separate shortcuts for:**
- ❌ start_bot.bat (launcher does this)
- ❌ stop_bot.bat (launcher does this)
- ❌ config_wizard.pyw (launcher has built-in wizard + settings dialog)
- ❌ Konfiguracja shortcut (launcher Settings button)

### What setup_env.bat BECOMES (minimal, for manual recovery only)

```bat
@echo off
title UdzialyBot - Manual Setup
cd /d "%~dp0"
echo Installing packages...
python\python.exe -m pip install --no-warn-script-location -r requirements.txt
echo Installing browser...
python\python.exe -m patchright install chromium
echo Done! Run launcher.pyw to configure.
pause
```

**This file is a FALLBACK** — only needed if the user deletes packages or launcher's built-in setup fails.

---

## 6. Upgrade Path — Config Migration Strategy

### Scenario: User has v1.0 installed, installs v1.1

```
NSIS v1.1 Installer
    │
    ├─ Reads previous INSTDIR from registry: HKCU\Software\BotUdzialy\InstallDir
    │
    ├─ IfFileExists "$INSTDIR\config.yaml"
    │       │
    │       ├─ YES: Set flag $CONFIG_EXISTS = 1
    │       │       DON'T overwrite config.yaml!
    │       │       Copy config.yaml.bak (safety backup)
    │       │
    │       └─ NO: Will be created by wizard on first run
    │
    ├─ Overwrite ALL code files (bot/, scraper/, detector/, etc.)
    ├─ Overwrite requirements.txt, launcher.pyw
    ├─ Overwrite tor\ (new version if bundled)
    │
    └─ Post-install: launcher.pyw detects upgrade scenario
```

### Config Migration in launcher.pyw

```python
def _migrate_config(self, config: dict) -> dict:
    """Add missing keys from new version defaults to existing user config."""
    DEFAULTS = {
        "llm": {
            "enabled": True,
            "provider": "openai",
            "api_key": "",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "max_concurrent": 5,
            "timeout": 15,
        },
        "scorer": {
            "threshold": 25,
            "keywords_file": "",
        },
        # ... other new sections
    }
    
    migrated = False
    for section, defaults in DEFAULTS.items():
        if section not in config:
            config[section] = defaults
            migrated = True
        else:
            # Add missing keys within existing section
            for key, value in defaults.items():
                if key not in config[section]:
                    config[section][key] = value
                    migrated = True
    
    if migrated:
        # Re-save with new fields (preserving user values)
        self._save_config_yaml(config)
        logger.info("Config migrated to new version — added missing sections")
    
    return config
```

### NSIS Implementation

```nsi
Section "Pliki konfiguracyjne" SecConfig
    SetOutPath "$INSTDIR"
    
    ; --- CRITICAL: Don't overwrite user's config ---
    IfFileExists "$INSTDIR\config.yaml" +3
        File "${PROJECT_BUNDLE}\config.yaml.template"  ; Fresh install: template
        Rename "$INSTDIR\config.yaml.template" "$INSTDIR\config.yaml"
    ; (else: user config preserved, migration handled by launcher.pyw)
    
    ; These are always overwritten:
    File "${PROJECT_BUNDLE}\launcher.pyw"
    File "${PROJECT_BUNDLE}\requirements.txt"
    File "${PROJECT_BUNDLE}\setup_env.bat"
SectionEnd
```

### Upgrade Matrix

| File | Fresh Install | Upgrade v1→v1.1 | Rationale |
|------|:---:|:---:|------|
| config.yaml | Create from template | PRESERVE (never overwrite) | User's tokens + settings |
| launcher.pyw | Install | OVERWRITE | New features/bugfixes |
| requirements.txt | Install | OVERWRITE | New dependencies |
| bot/*.py | Install | OVERWRITE | All code files updated |
| scraper/*.py | Install | OVERWRITE | All code files updated |
| detector/*.py | Install | OVERWRITE | All code files updated |
| storage/*.py | Install | OVERWRITE | All code files updated |
| geo/*.py | Install | OVERWRITE | All code files updated |
| data/udzialy.db | Created at runtime | PRESERVE | User's saved listings |
| data/bot.log | Created at runtime | PRESERVE | Can delete, not critical |
| data/cities.json | Install | OVERWRITE | Updated city database |
| tor/* | Install | OVERWRITE | Updated Tor binary |
| python/* | Install | OVERWRITE (re-install) | Updated Python/packages |

---

## 7. Launcher ↔ Bot Communication Protocol

### How launcher.pyw knows bot state:

```
┌────────────┐         ┌─────────────┐         ┌──────────┐
│  launcher  │──spawn──│  bot.main   │──write──│  stdout  │
│  (GUI)     │         │  (asyncio)  │         │  (pipe)  │
│            │◄──read──│             │         │          │
│  Queue     │         └─────────────┘         └──────────┘
│  after()   │
└────────────┘
```

**Signals via stdout (parsed by launcher log reader):**

| Line Pattern | Meaning | Launcher Action |
|------|---------|---------|
| `Bot starting up...` | Bot process alive | Update status: "Starting..." |
| `Starting polling...` | Bot ready for commands | Update status: "🟢 Running" |
| `Bot stopped by user.` | Graceful shutdown | Update status: "🔴 Stopped" |
| `❌ Bot token not configured!` | Config error | Show error dialog |
| `[ERROR]` prefix | Any error | Highlight red in log |
| `Portal X: N results` | Scrape progress | Update portal status |

**Process state detection (poll-based):**

```python
# In _poll_logs() called every 100ms:
if self.bot_proc and self.bot_proc.poll() is not None:
    exit_code = self.bot_proc.returncode
    if exit_code == 0:
        self._set_state("stopped")       # Graceful exit
    elif exit_code == 1:
        self._set_state("config_error")  # Token not set
    else:
        self._set_state("crashed")       # Unexpected exit
```

---

## 8. Module Import Chain (Runtime)

When `python -m bot.main` runs with CWD=D:\UdzialyBot:

```
sys.path[0] = "D:\UdzialyBot"  (CWD, added by -m flag)

bot.main imports:
  ├── bot.config          → D:\UdzialyBot\bot\config.py     ✓
  ├── bot.middlewares     → D:\UdzialyBot\bot\middlewares\   ✓
  └── bot.routers         → D:\UdzialyBot\bot\routers\      ✓

bot.config adds PROJECT_ROOT to sys.path:
  sys.path.insert(0, "D:\UdzialyBot")  → already there, no-op

bot.routers.search imports:
  ├── scraper.manager     → D:\UdzialyBot\scraper\manager.py ✓
  ├── storage.database    → D:\UdzialyBot\storage\database.py ✓
  └── detector.scorer     → D:\UdzialyBot\detector\scorer.py  ✓

scraper.manager imports:
  ├── scraper.base        → D:\UdzialyBot\scraper\base.py    ✓
  ├── scraper.portals.*   → D:\UdzialyBot\scraper\portals\   ✓
  └── detector.llm_analyzer → D:\UdzialyBot\detector\llm_analyzer.py ✓

detector.llm_analyzer imports:
  └── httpx               → python\Lib\site-packages\httpx\  ✓

scraper.portals.olx imports:
  ├── curl_cffi           → python\Lib\site-packages\        ✓
  └── selectolax          → python\Lib\site-packages\        ✓
```

**No sys.path manipulation needed beyond what `-m` provides!** The flat layout makes all top-level packages directly importable from CWD.

---

## 9. Configuration Loading — Unified Pattern

### Single Source of Truth: `bot/config.py`

Both launcher and bot should use the same config structure, but with different loading mechanisms:

| Component | Library | Loading |
|-----------|---------|---------|
| launcher.pyw | PyYAML (or regex fallback) | `yaml.safe_load()` → plain dict |
| bot/config.py | pydantic + PyYAML | `Settings.from_yaml()` → typed dataclass |

**Why launcher uses plain dict (not pydantic):**
- Launcher is a tkinter GUI that may not have pydantic installed during first-run
- Launcher only needs: token, owner_id, portals[].enabled, llm.api_key, llm.provider
- The regex fallback (`_parse_config_fallback`) handles the case where PyYAML isn't installed yet

**Why bot uses pydantic:**
- Type safety, validation, defaults, env var overrides (UDZIALY_TELEGRAM__TOKEN=xxx)
- Singleton pattern guarantees config is loaded once and frozen
- Bot always runs AFTER setup_env.bat/wizard has installed all dependencies

---

## 10. Error States & Recovery

| State | Detection | User-facing | Recovery |
|-------|-----------|-------------|----------|
| No config.yaml | `os.path.exists(CONFIG_PATH)` returns False | SetupWizard opens | Complete wizard |
| Invalid token | Bot exits with code 1 + stderr msg | Error dialog: "Token nieprawidłowy" | Open Settings, fix token |
| Tor won't start | `wait_for_port(9050)` times out after 60s | Error: "Tor nie może się uruchomić" | Check firewall, restart |
| Pip install fails | setup thread catches non-zero exit | Error in wizard: "Brak internetu" | Retry button, manual setup_env.bat |
| Port 9050 busy | `connect_ex()` returns 0 before we start Tor | "Tor already running" | Kill stale tor.exe, retry |
| Bot crashes | `proc.poll() != None` + exit code != 0 | "Bot uległ awarii (kod: X)" | Show last 10 log lines, restart button |
| LLM API error | `ListingAnalyzer` returns None | Silent (bot continues without LLM) | Check API key in Settings |
| DB locked | aiosqlite timeout | Log warning, retry | Automatic (single-writer) |

---

## 11. Version & Compatibility Matrix

| Component | Min Version | Max Tested | Notes |
|-----------|:-----------:|:----------:|-------|
| Windows | 10 (1809) | 11 (24H2) | No XP/7/8 support |
| Python | 3.11.0 | 3.11.9 | Bundled (no system Python) |
| Tkinter | 8.6 | 8.6 | Bundled with Python |
| aiogram | 3.4 | 3.7 | Telegram bot framework |
| httpx | 0.25 | 0.27 | LLM API calls |
| pydantic | 2.5 | 2.9 | Config validation |
| curl_cffi | 0.5.10 | 0.7 | TLS fingerprint spoofing |
| aiosqlite | 0.19 | 0.20 | Async SQLite |
| Tor | 0.4.7 | 0.4.8 | Bundled in installer |

---

## 12. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| API keys in config.yaml | File is local-only, never committed to git (.gitignore) |
| Tor control password in config | Hashed in torrc; plaintext only in config.yaml (local file) |
| Bot token exposure | Same as above — local file, user's machine |
| SOCKS proxy open | Binds to 127.0.0.1 only (not 0.0.0.0) |
| SQLite injection | Parameterized queries in storage/queries.py |
| LLM prompt injection | User descriptions are sandwiched in structured prompt |
| Process killing | taskkill by PID, not by image name (won't kill other python.exe) |

---

## 13. Summary: Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Flat layout (no `app/` subdirectory) | Eliminates all path confusion; `python -m bot.main` just works |
| launcher.pyw as sole entry point | One file, one shortcut, handles wizard + dashboard + stop/start |
| config.yaml at root (CWD) | Both launcher and bot find it trivially; no path traversal needed |
| Full Python install (not embedded zip) | pip works normally, no ._pth shenanigans, tkinter included |
| No venv | Private Python = IS the venv; packages go to site-packages directly |
| CWD-first config resolution | Production path (via launcher/bat) always wins over dev paths |
| Singleton settings in bot | Config loaded once → no file contention at runtime |
| Queue-based log streaming | Thread-safe, decoupled, batchable; standard tkinter pattern |
| taskkill /T /F /PID | Only reliable process tree kill on Windows |
| Config migration in launcher | Upgrade-safe; new sections added without losing user values |
| setup_env.bat as recovery-only | Primary setup via launcher wizard; bat for manual fallback |

---

## 14. Open Questions for Implementation

1. **LLM provider headers:** Anthropic uses `x-api-key` not `Authorization: Bearer`. Should `llm_analyzer.py` switch headers based on `provider` field, or always use OpenAI format (requiring Anthropic users to use a proxy like LiteLLM)?
   - **Recommendation:** Native multi-provider with header switching. See RESEARCH_MULTI_LLM_API.md §3.

2. **Hot config reload:** Should we ever support changing config while bot is running?
   - **Recommendation:** No. Stop → Edit → Start. Keeps architecture simple.

3. **Chromium for patchright:** ~150MB download on first run. Show progress in launcher?
   - **Recommendation:** Yes, but make it optional. If otodom is disabled, skip chromium install.

4. **Multiple instances:** What if user double-clicks launcher while it's already open?
   - **Recommendation:** Mutex/lockfile. launcher.pyw checks for `data/.launcher.lock` on startup.

5. **Log rotation:** `data/bot.log` can grow unbounded.
   - **Recommendation:** Add `logging.handlers.RotatingFileHandler` (5MB, 3 backups) in bot/main.py.
