# Udziały Bot — Windows Deployment Failure Audit

**Date:** 2026-08-26  
**Target:** Non-technical user (Marek K., Windows 10/11, Gdynia)  
**Delivery:** ZIP → extract → run `setup_env.bat`

---

## CRITICAL (Bot won't start / Data loss / Unrecoverable)

### 1. CRITICAL — `curl_cffi` requires C compiler / pre-built wheel may not exist
**File:** `requirements.txt` line 5  
**Problem:** `curl_cffi>=0.7.0` ships native extensions. If no pre-built wheel for Python 3.11 on win-amd64, pip falls back to source build which requires Visual Studio Build Tools (16+ GB). Fails with `error: Microsoft Visual C++ 14.0 or greater is required`.  
**Fix:** Pin exact version with known wheel (`curl_cffi==0.7.3`), or bundle the `.whl` file in the ZIP and `pip install ./curl_cffi-*.whl`. Same risk for `primp`.

### 2. CRITICAL — `patchright install chromium` needs 200+ MB download; no error handling
**File:** `setup_env.bat` line 51  
**Problem:** `patchright install chromium` downloads ~200MB Chromium binary. If network is slow, proxied, or drops — it fails silently (`2>nul` swallows stderr). User sees "Instalacja zakonczona!" but Otodom scraping will crash at runtime.  
**Fix:** Remove `2>nul`, check `if errorlevel 1`, display clear message. Consider bundling chromium in the ZIP or making it optional.

### 3. CRITICAL — torrc `DataDirectory .\tor\data` is a relative path resolved from CWD
**File:** `tor/torrc` line 4  
**Problem:** When launcher starts Tor with `cwd=os.path.dirname(TOR_PATH)` (which is `SCRIPT_DIR\tor\tor\`), the DataDirectory resolves to `SCRIPT_DIR\tor\tor\tor\data` — nested incorrectly. If the user double-clicks tor.exe manually or CWD differs, data goes to a random location.  
**Fix:** Use absolute path in torrc, or generate torrc at runtime with absolute DataDirectory from SCRIPT_DIR.

### 4. CRITICAL — TOR_PATH points to `tor/tor/tor.exe` (double-nested)
**File:** `launcher.pyw` line 103: `TOR_PATH = os.path.join(SCRIPT_DIR, "tor", "tor", "tor.exe")`  
**Problem:** The bundle has `tor/torrc` at top level, but TOR_PATH expects `tor/tor/tor.exe`. If the actual binary is at `tor/tor.exe` (one level), Tor will never start. The TORRC_PATH (`tor/torrc`) and TOR_PATH (`tor/tor/tor.exe`) are at different nesting levels — inconsistent.  
**Fix:** Verify exact bundle structure; align TOR_PATH with actual layout. Current `start_bot.bat` uses `%~dp0tor\tor\tor.exe` confirming double-nest, but torrc is at `tor/torrc` (top level) — mismatch.

### 5. CRITICAL — `bot/config.py` imports `yaml` and `pydantic-settings` at module level
**File:** `bot/config.py` lines 13-15  
**Problem:** If pip install failed partially (e.g., network cut during install), `import yaml` or `from pydantic_settings import ...` crashes the bot with `ModuleNotFoundError`. The launcher shows wizard correctly, but once user clicks "Uruchom Bota", the subprocess crashes immediately with no visible error (CREATE_NO_WINDOW hides the traceback).  
**Fix:** Add a pre-flight dependency check in launcher before starting bot process. Show error in GUI log if critical imports fail.

### 6. CRITICAL — Windows Defender SmartScreen blocks `python-3.11.9-amd64.exe`
**File:** `setup_env.bat` line 17  
**Problem:** The Python installer exe is not code-signed by the distributor in this bundle context. SmartScreen will show "Windows protected your PC" dialog. With `/quiet` flag, this may fail silently — the installer never runs, `python\python.exe` never appears, and setup exits with "BLAD: Instalacja Python nie powiodla sie." A non-technical user won't know to click "Run anyway" first.  
**Fix:** Add explicit instructions in README. Better: use Python embedded zip (no installer needed, no SmartScreen) or sign the installer.

### 7. CRITICAL — Antivirus quarantines `tor.exe` immediately
**Problem:** Tor is flagged by most AV engines (Windows Defender, Avast, Norton, ESET) as "HackTool:Win32/TorTool" or similar. AV will quarantine/delete tor.exe silently. Bot starts, Tor doesn't, scraping over Tor fails.  
**Fix:** Document AV exclusion steps. Add tor.exe existence check before start with clear "AV blocked Tor" message. Consider making Tor optional with direct HTTPS fallback.

---

## HIGH (Major functionality broken / Likely failure for target user)

### 8. HIGH — Python installer requires admin for `TargetDir` outside user profile
**File:** `setup_env.bat` line 17  
**Problem:** If user extracts to `C:\UdzialyBot` (root of C:), `InstallAllUsers=0` with `TargetDir="C:\UdzialyBot\python"` works. But if extracted to `C:\Program Files\...` or a path requiring elevation, the silent install fails. No UAC prompt appears with `/quiet`.  
**Fix:** The `/quiet` + `InstallAllUsers=0` should work in user-writable locations. Add note in README: "Extract to Desktop or Documents, NOT Program Files."

### 9. HIGH — pip install fails behind corporate proxy/firewall
**File:** `setup_env.bat` lines 28-46  
**Problem:** Many corporate networks block PyPI or require proxy. pip will timeout after ~120s × N packages. Error message says "Sprawdz polaczenie z internetem" but doesn't offer proxy config.  
**Fix:** Bundle all wheels in a `wheels/` folder; install with `pip install --no-index --find-links=wheels/ -r requirements.txt`. Zero network dependency.

### 10. HIGH — `nodriver` downloads Chrome DevTools binary on first use
**Problem:** `nodriver` (used for Otodom) downloads its own Chrome on first `.start()` if not found. This is separate from patchright's chromium. Two 200MB downloads total. May fail at runtime.  
**Fix:** Pre-download during setup_env.bat, or bundle. Add `python -c "import nodriver; ..."` test in setup.

### 11. HIGH — Paths with spaces break `start_bot.bat` Tor launch
**File:** `start_bot.bat` line 11: `start "" /B "%~dp0tor\tor\tor.exe" -f "%~dp0tor\torrc"`  
**Problem:** The `start "" /B` with quoted paths should work, but `netstat -an | find "9050"` loop has no timeout — if Tor never starts (AV, missing exe), infinite loop hangs the console.  
**Fix:** Add iteration counter (max 30 attempts = 60s), then abort with error message.

### 12. HIGH — `__pycache__/*.cpython-311.pyc` files from Linux in bundle
**Files:** Multiple `__pycache__` directories with `.pyc` files  
**Problem:** These .pyc files were compiled on Linux. Python won't use them on Windows (different platform magic number), so it recompiles. Not a crash bug, but: (a) wastes space in ZIP, (b) if the folder is read-only, recompilation fails with PermissionError, (c) confusing for debugging.  
**Fix:** Delete all `__pycache__` directories from bundle before zipping. Add to build script: `find . -type d -name __pycache__ -exec rm -rf {} +`

### 13. HIGH — `tests/` directory included in production bundle
**Files:** `tests/test_*.py`, `tests/conftest.py`  
**Problem:** Unnecessary test files with test dependencies (pytest) that aren't in requirements.txt. Adds confusion, increases ZIP size, user might accidentally run them.  
**Fix:** Exclude `tests/` from production bundle.

### 14. HIGH — Tor control password mismatch between torrc and config
**File:** `tor/torrc` line 3 has hash for one password; `config.yaml` line 53 has `control_password: "udzialy2026"`; `scraper/tor_manager.py` line 24 has `TOR_CONTROL_PASSWORD = "udzialy_bot_tor"`  
**Problem:** Three different passwords! The HashedControlPassword in torrc must match what the code sends via AUTHENTICATE. If `stem` uses "udzialy2026" (from config) but torrc hash is for a different password, circuit renewal fails silently.  
**Fix:** Regenerate torrc hash from "udzialy2026", or align all three values. Verify with `tor --hash-password udzialy2026`.

### 15. HIGH — `config.yaml` has `binary_path: "/usr/bin/tor"` (Linux path)
**File:** `config.yaml` line 55  
**Problem:** The shipped config.yaml has a Linux tor path. If `TorManager` in `scraper/tor_manager.py` reads this config value, it won't find tor on Windows.  
**Fix:** Change to relative Windows path `tor/tor/tor.exe` or remove — the launcher already handles Tor startup independently.

### 16. HIGH — Port 9050/9051 conflict if user has existing Tor Browser
**Problem:** Tor Browser uses the same default ports. If running simultaneously, either Tor instance fails to bind. Error manifests as cryptic socket error or Tor startup timeout.  
**Fix:** Check port availability before starting Tor. Show clear "Port 9050 already in use — close Tor Browser" message. Or use non-standard ports (e.g., 19050/19051).

### 17. HIGH — `launcher.pyw` wizard only shows 4 portals but config supports 9
**File:** `launcher.pyw` line 680: `for portal in ["OLX", "Morizon", "Domiporta", "Otodom"]:`  
**Problem:** Wizard hardcodes only 4 portals in checkboxes, but `ALL_PORTALS` constant lists 9. Config saved from wizard will only have 4 portal entries; the other 5 get default values (all enabled), potentially causing unexpected scraping of portals user didn't intend.  
**Fix:** Iterate over `ALL_PORTALS` in wizard UI instead of hardcoded subset.

### 18. HIGH — Windows Firewall blocks outbound for `python.exe` and `tor.exe`
**Problem:** First time python.exe or tor.exe make outbound connections, Windows Firewall pops up "allow/block" dialog. If user clicks "Block" (or if running as service/scheduled task), all network requests fail silently.  
**Fix:** Document firewall allowance. Or add `netsh advfirewall` commands in setup_env.bat (requires admin). At minimum, detect and warn in GUI.

---

## MEDIUM (Degraded experience / Confusing errors / Intermittent)

### 19. MEDIUM — `chcp 65001` may not stick for subprocess stdout encoding
**File:** `setup_env.bat` line 2, `start_bot.bat` line 2  
**Problem:** `chcp 65001` changes console codepage but Python subprocesses may still use system locale (cp1250 for Polish Windows). Polish characters in log output (`ł`, `ś`, `ź`) may render as garbage or cause UnicodeEncodeError.  
**Fix:** Set `PYTHONIOENCODING=utf-8` env var before launching Python processes.

### 20. MEDIUM — `stop_bot.bat` uses WMIC (deprecated/removed in Win11 24H2)
**File:** `stop_bot.bat` line 9: `wmic process where "CommandLine like '%%bot.main%%'" call terminate`  
**Problem:** WMIC is deprecated since Win10 21H1 and removed in some Win11 builds. Command fails silently (`>nul 2>&1`). Bot process survives stop attempt.  
**Fix:** Replace with PowerShell: `powershell -Command "Get-Process python | Where-Object {$_.CommandLine -like '*bot.main*'} | Stop-Process -Force"` or use `taskkill /FI`.

### 21. MEDIUM — Wizard `owner_id` field accepts non-numeric input → crash
**File:** `launcher.pyw` line 745: `"owner_id": int(self.id_entry.get().strip() or "0")`  
**Problem:** If user types "abc" or "12 34" in owner_id field, `int()` raises ValueError. Unhandled exception crashes wizard.  
**Fix:** Wrap in try/except, validate before save, show messagebox error.

### 22. MEDIUM — `config_wizard.pyw` still bundled alongside `launcher.pyw`
**Problem:** Two wizard files in the bundle. User might double-click the old `config_wizard.pyw` instead of `launcher.pyw`. Old wizard doesn't have LLM config, doesn't launch bot correctly.  
**Fix:** Remove `config_wizard.pyw` from bundle.

### 23. MEDIUM — `.pyw` file association not registered if Python installed locally
**File:** `setup_env.bat` line 17 uses `AssociateFiles=0`  
**Problem:** Since Python install doesn't register file associations, double-clicking `.pyw` files does nothing (opens Notepad or "How do you want to open?" dialog). The setup_env.bat uses `start "" "%BASE%python\pythonw.exe" "%BASE%launcher.pyw"` which works — but if user later tries to launch by clicking launcher.pyw directly, it fails.  
**Fix:** Create a `launcher.bat` wrapper that calls pythonw.exe explicitly. Or create a desktop shortcut during setup.

### 24. MEDIUM — `pythonw.exe` might not exist in target install
**File:** `setup_env.bat` line 61  
**Problem:** If Python installer partially fails or is a custom build, pythonw.exe may not be present even though python.exe is. The `start "" "%BASE%python\pythonw.exe"` fails silently (no error, no window, no bot).  
**Fix:** Check for pythonw.exe existence; fall back to python.exe if missing (user will see console window but at least it works).

### 25. MEDIUM — Long path names >260 chars cause failures
**Problem:** User extracts to deeply nested path like `C:\Users\Marek Knapczyk\OneDrive\Desktop\Projects\Real Estate\UdzialyBot\` — combined with `python\Lib\site-packages\patchright\...` easily exceeds 260-char Windows MAX_PATH limit.  
**Fix:** Add path length check at start of setup_env.bat. Recommend short path. Or enable LongPathsEnabled registry key (requires admin).

### 26. MEDIUM — `data/` directory must exist for database and logs
**Problem:** `bot/main.py` creates `data/` dir on startup (`mkdir(parents=True, exist_ok=True)`), but if launcher.pyw tries to read LOG_FILE before bot runs, or if permissions prevent creation, it fails.  
**Fix:** Create `data/` directory in setup_env.bat. Include empty `data/.gitkeep` in bundle.

### 27. MEDIUM — `TorManager._find_tor_binary()` uses `Path.cwd()` which is unreliable
**File:** `scraper/tor_manager.py` line 62  
**Problem:** `Path.cwd() / "tor" / "tor.exe"` depends on CWD at runtime. If bot is launched from a different directory (e.g., Windows Task Scheduler), CWD won't be SCRIPT_DIR. Tor binary won't be found.  
**Fix:** Use `Path(__file__).parent.parent / "tor" / "tor.exe"` — relative to source file, not CWD.

### 28. MEDIUM — No graceful handling of bot crash → zombie Tor process
**Problem:** If bot subprocess crashes, launcher detects it via `poll()` returning non-None. But Tor keeps running. Status dot stays green-ish. User must manually stop.  
**Fix:** Add periodic health check in `_poll_logs` that detects bot death and updates UI status. Auto-stop Tor if bot dies unexpectedly.

### 29. MEDIUM — Wizard token validation fails if Tor/proxy intercepts HTTPS
**File:** `launcher.pyw` line 716: `urllib.request.urlopen(req, timeout=10)`  
**Problem:** On corporate networks or if system proxy is set, the HTTPS request to `api.telegram.org` may be intercepted by SSL inspection proxy → certificate error → "Błąd połączenia" without clear explanation.  
**Fix:** Catch `ssl.SSLError` specifically, provide clear message about proxy/corporate network.

### 30. MEDIUM — `stem` library authentication uses plaintext password
**File:** `scraper/tor_manager.py` lines 225-228  
**Problem:** `AUTHENTICATE "password"` sent in plaintext over TCP. Not a security issue (localhost only), but if stem uses the wrong password string vs what torrc expects (see #14), all NEWNYM calls fail and scraping gets same IP repeatedly — detected and blocked by portals.  
**Fix:** Align passwords, test circuit renewal during setup.

### 31. MEDIUM — Multiple `setup_env.bat` instances running simultaneously
**Problem:** If user double-clicks setup_env.bat twice quickly, two Python installers fight over the same TargetDir. File locks, partial installs, corrupted Python distribution.  
**Fix:** Add mutex/lockfile check at top of batch: `if exist "%BASE%setup.lock" (echo "Already running..." & exit /b 1)`. Create lockfile, delete on exit.

### 32. MEDIUM — `selectolax` may need pre-built wheel
**File:** `requirements.txt` line 4  
**Problem:** `selectolax` wraps Modest (C library). If no wheel for py3.11/win64, falls back to source build → requires C compiler.  
**Fix:** Verify wheel exists on PyPI for target platform, or bundle.

---

## LOW (Minor UX issues / Edge cases / Cosmetic)

### 33. LOW — `LLM_PROVIDERS` defined twice in launcher.pyw
**File:** `launcher.pyw` lines 115-121 and 481-487  
**Problem:** Two definitions of `LLM_PROVIDERS` — second overrides first (GPT-4o vs GPT-4o-mini naming). Not a crash but confusing during maintenance.  
**Fix:** Remove duplicate, keep one canonical definition.

### 34. LOW — Wizard mousewheel binding is global (`bind_all`)
**File:** `launcher.pyw` line 592  
**Problem:** `canvas.bind_all("<MouseWheel>", ...)` binds to ALL widgets. After wizard closes, the binding leaks to dashboard — scrolling anywhere triggers canvas yview on destroyed widget → potential TclError.  
**Fix:** Use `canvas.bind("<MouseWheel>")` and focus-based binding.

### 35. LOW — `start_bot.bat` runs bot in foreground (blocking)
**File:** `start_bot.bat` line 22  
**Problem:** `"%~dp0python\python.exe" -m bot.main` blocks the console. User can't close window without killing bot. Ctrl+C may leave Tor orphaned.  
**Fix:** Add trap/cleanup, or document that launcher.pyw is the preferred way.

### 36. LOW — Wizard doesn't validate owner_id format (should be ~10 digit number)
**Problem:** User might paste username instead of numeric ID. Bot starts with owner_id=0, never sends notifications.  
**Fix:** Validate: must be 5-12 digits, show example format.

### 37. LOW — `config.yaml` placeholder `owner_id: 0` causes silent bot startup without notifications
**Problem:** If user skips wizard and edits config.yaml manually but forgets owner_id, bot works but user never receives Telegram messages. No error shown.  
**Fix:** Warn in GUI if owner_id is 0 when starting bot.

### 38. LOW — No desktop shortcut created
**Problem:** After setup, user must navigate to folder and run setup_env.bat again (which re-checks Python but works). No Start Menu or Desktop shortcut for launcher.  
**Fix:** Create shortcut in setup_env.bat: `powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut(...)"`

### 39. LOW — No auto-start / Windows startup option
**Problem:** After PC restart, bot doesn't run. Non-technical user won't remember to launch manually.  
**Fix:** Add optional "Start with Windows" checkbox in settings that creates Registry Run entry or Startup folder shortcut.

### 40. LOW — ZIP extraction with Windows built-in extractor may be slow/incomplete
**Problem:** Windows built-in ZIP extractor is slow for large archives and may fail on long filenames. Some AV scanners lock files during extraction.  
**Fix:** Recommend 7-Zip in README, or provide self-extracting .exe.

### 41. LOW — `primp>=0.6.0` is an obscure package — may disappear from PyPI
**Problem:** Low-popularity packages can be yanked or renamed. Future `pip install` could fail.  
**Fix:** Bundle wheel, or pin exact version with hash verification.

### 42. LOW — No version check / auto-update mechanism
**Problem:** If bugs are found post-deployment, user must manually replace files. No mechanism to check for updates.  
**Fix:** Add simple version check against a URL endpoint on startup.

### 43. LOW — Bot log file grows unbounded
**Problem:** `data/bot.log` is appended to forever. On a system running 24/7, file grows to GB over months.  
**Fix:** Add `RotatingFileHandler` with max 5MB × 3 backups.

### 44. LOW — Dashboard log widget has no max line limit
**File:** `launcher.pyw` — Text widget grows forever  
**Problem:** If bot runs for days, tkinter Text widget accumulates thousands of lines → memory bloat, UI lag.  
**Fix:** Trim to last 500 lines periodically.

### 45. LOW — `urllib.request` for token check ignores system proxy settings inconsistently
**Problem:** `urllib.request.urlopen` respects `http_proxy`/`https_proxy` env vars but not Windows system proxy settings by default in all cases.  
**Fix:** Use `urllib.request.getproxies()` explicitly or catch proxy-related errors with guidance.

---

## Summary

| Severity | Count | Key Theme |
|----------|-------|-----------|
| CRITICAL | 7 | AV/SmartScreen blocking, native deps, path/password mismatches |
| HIGH | 11 | Network deps, port conflicts, config inconsistencies |
| MEDIUM | 14 | Encoding, deprecated APIs, UX traps, edge-case crashes |
| LOW | 13 | Polish, missing features, maintenance debt |
| **TOTAL** | **45** | |

### Top 5 Actions (highest impact for least effort):
1. **Bundle all pip wheels** in ZIP → eliminates #1, #9, #32, #41
2. **Fix Tor password alignment** → eliminates #14 (or all circuit renewal breaks)
3. **Delete `__pycache__` and `tests/`** from bundle → eliminates #12, #13
4. **Use Python embedded ZIP** instead of full installer → eliminates #6, #8, #23
5. **Add pre-flight checks in launcher** (Tor exists, ports free, deps importable) → catches #5, #7, #16 with clear UI messages
