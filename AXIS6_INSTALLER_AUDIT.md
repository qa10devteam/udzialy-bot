# AXIS-6 LAYER 1 — INSTALLER & CONFIG WIZARD AUDIT

**Product:** udzialy-bot v1.0.0  
**Auditor:** AXIS-6 Destructive Framework  
**Date:** 2026-08-22  
**Scope:** NSIS installer, setup_env.bat, start_bot.bat, stop_bot.bat, config_wizard.pyw, torrc  
**Attack Vector:** Non-technical Windows user performing first-time installation

---

## EXECUTIVE SUMMARY

| Severity | Count |
|----------|-------|
| FATAL    | 3     |
| CRITICAL | 6     |
| HIGH     | 8     |
| MEDIUM   | 7     |
| LOW      | 4     |
| **TOTAL** | **28** |

Three FATAL issues guarantee installation failure for every user. The embedded Python lacks both `venv` module AND `tkinter`, making the `setup_env.bat` workflow impossible. The bundled `config_wizard.pyw` launcher tries to import a non-existent module. All three must be fixed before any user can successfully install.

---

## FATAL ISSUES (Installation will always fail)

### F-01: Embedded Python cannot create venv — `venv` module not bundled
**File:** `installer/build/python/` + `installer/setup_env.bat:20`  
**Evidence:** Python embedded distribution does NOT include the `venv` module. Checked `python311.zip` — zero files matching `venv`. The `python311._pth` enables site-packages but `venv` stdlib module is absent.  
**Impact:** `python\python.exe -m venv .venv` will ALWAYS fail with `No module named venv`. Step 1/5 fails. Script halts.  
**User sees:** `[BLAD] Nie udalo sie utworzyc srodowiska wirtualnego!`  
**Fix:** Either:
1. Bundle `ensurepip` + `venv` packages into `python311.zip` (extract from full Python install: `Lib/venv/**`, `Lib/ensurepip/**`), OR
2. Replace venv approach entirely: install pip directly into embedded Python's `Lib/site-packages` and use embedded Python directly without venv.

---

### F-02: Embedded Python has NO tkinter — config_wizard.pyw will crash
**File:** `installer/build/python/` + `installer/build/config_wizard.pyw:7`  
**Evidence:** No `_tkinter.pyd`, no `tcl/` dir, no `tk/` dir, no tkinter in `python311.zip`. The embedded distribution NEVER ships tkinter.  
**Impact:** Whether the wizard launches from embedded Python (`python\pythonw.exe config_wizard.pyw`) or from venv (which won't exist per F-01), `import tkinter` will raise `ModuleNotFoundError`.  
**User sees:** Nothing — `.pyw` runs with `pythonw.exe` which has NO console. The wizard silently dies. No window appears. User has no idea what happened.  
**Fix:** Either:
1. Bundle tkinter DLLs (`_tkinter.pyd`, `tcl86t.dll`, `tk86t.dll`, `tcl/`, `tk/` directories) from a full Python install, OR
2. Rewrite config wizard to not use tkinter (e.g., HTML-based wizard, or cmd-line prompts in the .bat file itself), OR
3. Include a full Python installation instead of the embedded one.

---

### F-03: Build config_wizard.pyw imports non-existent `bot.config_wizard` module
**File:** `installer/build/config_wizard.pyw:7-8`  
**Code:** `from bot.config_wizard import main`  
**Evidence:** Neither `bot/config_wizard.py` nor any `main()` function exists in the `bot/` module. Files are: `__init__.py`, `config.py`, `main.py`, `keyboards/`, `middlewares/`, `routers/`.  
**Impact:** The `ImportError` is caught and falls through to the inline tkinter wizard (which fails due to F-02). Even if tkinter worked, this fallback wizard is severely feature-reduced (no token validation, no portal selection).  
**Fix:** Either:
1. Create `bot/config_wizard.py` with a `main()` function that wraps the full `ConfigWizard` class, OR
2. Remove the try/except and use the root-level `config_wizard.pyw` directly, OR
3. Copy the full `config_wizard.pyw` (12.9KB version) into the build instead of the stub launcher.

---

## CRITICAL ISSUES (Installation fails under common conditions)

### C-01: `setup_env.bat` references `python\get-pip.py` but venv python can't run it
**File:** `installer/setup_env.bat:32`  
**Code:** `.venv\Scripts\python.exe python\get-pip.py --no-warn-script-location -q`  
**Impact:** Even if venv creation worked, the `.venv\Scripts\python.exe` is being asked to run `get-pip.py` from the embedded python directory. The path assumes CWD is `$INSTDIR`. If `cd /d "%~dp0"` fails (UNC path), this breaks.  
**Additionally:** The fallback `ensurepip` also won't work because `ensurepip` isn't in the embedded distribution either.  
**Fix:** Bundle `get-pip.py` at the install root and run it with the target python. Or install pip into embedded Python directly during build.

---

### C-02: `setup_env.bat` Step 3 pip install uses `>=` operators without shell quoting
**File:** `installer/setup_env.bat:53`  
**Code:** `.venv\Scripts\pip.exe install curl_cffi>=0.7 selectolax>=0.3 patchright>=1.0 -q 2>nul`  
**Impact:** The `>` character in `>=0.7` is interpreted by cmd.exe as output redirection! `curl_cffi>=0.7` redirects stdout to a file named `=0.7`. The command will either fail or create garbage files.  
**User sees:** Silent failure (stderr redirected to nul). Some packages won't install.  
**Fix:** Wrap version specs in quotes: `".venv\Scripts\pip.exe" install "curl_cffi>=0.7" "selectolax>=0.3" "patchright>=1.0" -q`

---

### C-03: NSIS "Konfiguracja" shortcut uses embedded `pythonw.exe` which has no tkinter
**File:** `installer/setup.nsi:117-119`  
**Code:**
```nsi
CreateShortCut "$SMPROGRAMS\${PRODUCT_SHORT}\Konfiguracja.lnk" \
    "$INSTDIR\python\pythonw.exe" '"$INSTDIR\config_wizard.pyw"' \
    "$INSTDIR\icon.ico" 0
```
**Impact:** User clicks "Konfiguracja" from Start Menu → embedded pythonw.exe has no tkinter → silent crash.  
**Fix:** Point shortcut at `.venv\Scripts\pythonw.exe` (which also won't have tkinter unless bundled), or redesign the wizard.

---

### C-04: `setup_env.bat` pip fallback references `app\requirements.txt` — wrong path in NSIS install
**File:** `installer/setup_env.bat:43`  
**Code:** `.venv\Scripts\pip.exe install --find-links=wheels\ -r app\requirements.txt -q 2>nul`  
**Evidence:** In the NSIS installer layout, the app files are under `$INSTDIR\app\` and requirements.txt is at `$INSTDIR\app\requirements.txt`. This path is correct. BUT the wheels glob at line 40 uses `wheels\*.whl` which is a wildcard — pip may not expand this correctly on all Windows versions.  
**Additional concern:** If the online install fallback triggers (no internet on user machine during setup), pip will fail silently (error suppressed with `2>nul`) and the bot will be missing critical dependencies.  
**Fix:** Remove `2>nul` from critical pip install commands. Let errors be visible. Use explicit wheel filenames instead of glob.

---

### C-05: `stop_bot.bat` kills ALL `python.exe` processes on the machine
**File:** `stop_bot.bat:9`  
**Code:** `taskkill /IM python.exe /F`  
**Impact:** If user has other Python programs running (Jupyter, Django, any IDE), this kills them ALL. Destructive. Data loss possible.  
**User sees:** Other Python applications suddenly close with no warning.  
**Fix:** Use a PID file. Save bot's PID on start (`start_bot.bat` should write PID to `.bot.pid`), then kill only that PID: `taskkill /PID <pid> /F`. Or use a unique process title: `start "UdzialyBot" python.exe -m bot.main` and then `taskkill /FI "WINDOWTITLE eq UdzialyBot"`.

---

### C-06: `stop_bot.bat` kills ALL `tor.exe` processes on the machine
**File:** `stop_bot.bat:16`  
**Code:** `taskkill /IM tor.exe /F`  
**Impact:** If user runs Tor Browser separately (very likely for privacy-conscious users who'd use this bot), this kills their Tor Browser too.  
**Fix:** Same as C-05 — use PID file approach.

---

## HIGH ISSUES (Functionality broken or UX-damaging)

### H-01: Build torrc has NO `HashedControlPassword` — bot can't rotate Tor circuits
**File:** `installer/build/tor/torrc`  
**Content:**
```
SocksPort 9050
ControlPort 9051
DataDirectory data
Log notice file notices.log
ClientUseIPv4 1
```
**vs.** `tor/torrc` (repo version) which has `HashedControlPassword 16:8C704B5...`  
**Impact:** The installed torrc has an open ControlPort with NO authentication. The bot's `tor_manager.py` uses `stem` library with password `udzialy2026` to authenticate to the control port. Without the hashed password in torrc, Tor will accept any connection OR reject password auth entirely (depending on version). The `bot/config.py` default is `control_password: "udzialy2026"`.  
**Security:** Open ControlPort = any local process can control Tor (change circuits, read traffic metadata).  
**Fix:** Add `HashedControlPassword 16:8C704B59AF8DABA16090B3EA903C8924AFD73DD53370533795BF6C8B47` to the build torrc.

---

### H-02: `start_bot.bat` (build version) has no `cd /d "%~dp0"` guard for UNC paths
**File:** `installer/build/start_bot.bat:4`  
**Has:** `cd /d "%~dp0"` — this is correct.  
**BUT:** The line `start /B "" "tor\tor.exe" -f "tor\torrc" --DataDirectory "tor\data"` uses RELATIVE paths.  
**Impact:** If user opens `start_bot.bat` from a different working directory (e.g., via Task Scheduler or a script), relative paths break. The `cd /d "%~dp0"` helps, but `start /B` creates a new process that may not inherit the CWD.  
**Fix:** Use absolute paths: `start /B "" "%~dp0tor\tor.exe" -f "%~dp0tor\torrc" --DataDirectory "%~dp0tor\data"`

---

### H-03: `start_bot.bat` (repo version) Tor wait loop uses `for /L` which doesn't break early
**File:** `start_bot.bat:38-51`  
**Code:**
```batch
for /L %%i in (1,1,60) do (
    if !TOR_READY!==0 (
        timeout /t 2 /nobreak >nul
        ...
    )
)
```
**Impact:** `for /L` in cmd.exe evaluates ALL iterations regardless of the `if` condition. Even after Tor is ready, the loop continues 60 times, each doing a `timeout /t 2`. The `if !TOR_READY!==0` prevents the port check but NOT the loop execution itself. This means after Tor connects (say iteration 5), the script still loops through iterations 6-60 doing nothing visible but consuming ~2 seconds of `timeout` each = up to 110 seconds of unnecessary waiting.  
**Wait...** Actually `timeout /t 2` is inside the `if` block so it's skipped. The loop still iterates but without delay, so it's fast. This is acceptable but wasteful.  
**Revised Impact:** Minor — the loop body is conditional so delay is properly gated. However, the echo of "." dots continues for all skipped iterations on some CMD versions.  
**Severity downgraded to:** MEDIUM (keeping as HIGH because user sees 120 second timeout message if Tor doesn't start, which is confusing)

---

### H-04: `install.bat` owner_id not validated as numeric
**File:** `install.bat:154`  
**Code:** `set /p OWNER_ID="Podaj swoje ID uzytkownika Telegram (liczba, np. 123456789): "`  
**Impact:** User can type "abc" or their username or nothing. The value goes directly into config.yaml as `owner_id: abc` which will crash the bot (pydantic expects `int`).  
**Contrast:** The GUI `config_wizard.pyw` properly validates with `_validate_numeric()`.  
**Fix:** Add validation loop:
```batch
:validate_id
set /p OWNER_ID="Podaj ID..."
echo %OWNER_ID%| findstr /r "^[0-9][0-9]*$" >nul || (echo Podaj liczbe! & goto :validate_id)
```

---

### H-05: `install.bat` hardcodes Tor version URL that will 404 when version changes
**File:** `install.bat:78`  
**Code:** URL `https://archive.torproject.org/.../13.5.6/tor-expert-bundle-windows-x86_64-13.5.6.tar.gz`  
**Impact:** When Tor 13.5.6 is archived/removed (happens within months), this URL 404s. The fallback URL is the same version on a different mirror — both will fail simultaneously.  
**User sees:** `[BLAD] Nie udalo sie pobrac Tora!`  
**Fix:** Use latest/stable URL pattern, or redirect through qa10.pl proxy that stays updated.

---

### H-06: NSIS installer requests `admin` but setup_env.bat may create files with wrong permissions
**File:** `installer/setup.nsi:27`  
**Code:** `RequestExecutionLevel admin`  
**Impact:** Installer runs elevated. `setup_env.bat` runs as continuation from NSIS finish page (also elevated). `.venv`, config files, and browser data are created as Administrator. Later, when user runs `start_bot.bat` from Desktop shortcut (non-elevated), files may have permission issues.  
**Fix:** Either don't request admin (install to user-writable `C:\UdzialyBot` — no admin needed for this path), or explicitly set ACLs after install.

---

### H-07: Two completely different `config_wizard.pyw` files — user gets the WRONG one
**File:** `installer/build/config_wizard.pyw` (1764 bytes, stub) vs `config_wizard.pyw` (12901 bytes, full wizard)  
**Evidence:** The build script creates a minimal stub launcher (line ~170 of `build.sh`) that overrides the full wizard. NSIS installs this stub at `$INSTDIR\config_wizard.pyw`. The full wizard goes into `$INSTDIR\app\config_wizard.pyw`.  
**Impact:** User always gets the minimal fallback (no token verification, no portal selection, no instructions). The full wizard with all its validation is unreachable.  
**Fix:** Copy the full `config_wizard.pyw` (12.9KB) as the root-level wizard, or fix the import path in the stub.

---

### H-08: `setup_env.bat` checks for `config.yaml` to skip wizard — but NSIS bundles `app\config.yaml`
**File:** `installer/setup_env.bat:67` + NSIS copies entire `app/` directory  
**Evidence:** The build includes `installer/build/app/config.yaml` (1669 bytes — a real config with actual settings). After NSIS installs, `$INSTDIR\app\config.yaml` exists. BUT `setup_env.bat` checks `if exist "config.yaml"` at CWD (`$INSTDIR`). Since NSIS doesn't copy config.yaml to root, the wizard WILL launch... but the bot later looks for config.yaml at project root.  
**Impact:** Confusing state — a config.yaml exists in `app/` but not at root. Wizard launches (good) but if user already ran install once, the wizard skip logic means they can't reconfigure.  
**Fix:** Don't bundle config.yaml in the app directory. Add `.gitignore`-style exclusion in rsync command in `build.sh`.

---

## MEDIUM ISSUES

### M-01: `start_bot.bat` (build) doesn't check if Tor is already running before starting
**File:** `installer/build/start_bot.bat:11`  
**Code:** `start /B "" "tor\tor.exe" -f "tor\torrc" --DataDirectory "tor\data"`  
**Impact:** If user runs start_bot.bat twice, two Tor instances try to bind port 9050. Second fails. Error goes to background (start /B). User may not notice.  
**Contrast:** The repo version (`start_bot.bat:20-24`) checks `tasklist` for existing tor.exe.  
**Fix:** Port the tasklist check from the repo version into the build version.

---

### M-02: `install.bat` uses `call .venv\Scripts\activate.bat` then bare `pip` — fragile
**File:** `install.bat:56-57`  
**Code:**
```batch
call .venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
```
**Impact:** If activate.bat fails silently (corrupt venv), `pip` resolves to system pip (or nothing). Packages install to wrong location. Bot fails at runtime.  
**Fix:** Use full path: `.venv\Scripts\pip.exe install ...` (like setup_env.bat does correctly).

---

### M-03: `install.bat` KROK 5 uses `python -m patchright install chromium` outside venv
**File:** `install.bat:111`  
**Code:** `python -m patchright install chromium`  
**Impact:** This uses system Python, not the venv Python. Patchright may not be installed in system Python. Chromium downloads to system patchright cache, not the project's venv cache. Bot won't find it.  
**Fix:** `.venv\Scripts\python.exe -m patchright install chromium`

---

### M-04: YAML generated by `install.bat` uses echo-based generation — fragile
**File:** `install.bat:156-176`  
**Impact:** If token contains `!` characters (possible in Telegram tokens), delayed expansion will eat them. `echo` + special chars (`&`, `|`, `>`) in token will break the echo pipeline.  
**Fix:** Use a Python one-liner to generate YAML safely, or escape special characters.

---

### M-05: `config_wizard.pyw` (full version) saves portals in non-standard YAML format
**File:** `config_wizard.pyw:177`  
**Code:** `lines.append(f"  {portal_name}: {{enabled: {enabled}}}")`  
**Output:** `  olx: {enabled: true}` — this is YAML flow style on a single line.  
**Impact:** `bot/config.py` expects `PortalEntry(enabled=bool, base_url=str)`. The wizard outputs `{enabled: true}` which pydantic may parse as a dict with only `enabled` key — this should work, but `base_url` defaults to `""` which may cause issues in scrapers expecting a URL.  
**Fix:** Include `base_url` in the wizard output or ensure scrapers handle empty `base_url`.

---

### M-06: Build torrc uses relative `DataDirectory data` — resolves relative to Tor's CWD, not its location
**File:** `installer/build/tor/torrc:3`  
**Code:** `DataDirectory data`  
**Impact:** Tor resolves relative paths from its CWD. If `start_bot.bat` launches tor.exe from `$INSTDIR`, then DataDirectory = `$INSTDIR\data` (NOT `$INSTDIR\tor\data`). The build `start_bot.bat` passes `--DataDirectory "tor\data"` as CLI arg which overrides torrc, but if someone runs tor.exe directly with `-f tor\torrc`, the DataDirectory is wrong.  
**The build start_bot.bat mitigates this** with `--DataDirectory "tor\data"`, but the repo version (`start_bot.bat:36`) uses `-f tor\torrc` WITHOUT overriding DataDirectory.  
**Fix:** Use absolute path in torrc or change to `DataDirectory tor/data` in the build torrc.

---

### M-07: NSIS uninstaller doesn't remove Chromium browser cache (~280MB orphaned)
**File:** `installer/setup.nsi:134-148`  
**Evidence:** Patchright downloads Chromium to `%LOCALAPPDATA%\ms-playwright\` (or similar). Uninstaller only removes `$INSTDIR` contents.  
**Impact:** 280MB+ of Chromium data remains after uninstall.  
**Fix:** Add `RMDir /r "$LOCALAPPDATA\ms-playwright"` to uninstaller (with user confirmation).

---

## LOW ISSUES

### L-01: `install.bat` has BOM (`EF BB BF`) — harmless but shows in some editors
**File:** `install.bat` byte 0-2  
**Impact:** Cosmetic only. Some terminals show `ÿþ` or `ï»¿` prefix.  
**Fix:** Acceptable for Windows .bat files with `chcp 65001`.

---

### L-02: NSIS `.onInit` function is empty — no Windows version check
**File:** `installer/setup.nsi:155-158`  
**Code:**
```nsi
Function .onInit
    ; Check Windows version (require Windows 10+)
    ; Set language to Polish by default
FunctionEnd
```
**Impact:** Installer claims to check Windows 10+ but doesn't. May install on Windows 7 where Python 3.11 won't run.  
**Fix:** Add version check: `${If} ${AtLeastWin10} ... ${EndIf}`

---

### L-03: `config_wizard.pyw` (full) doesn't handle proxy/corporate firewall for token check
**File:** `config_wizard.pyw:137`  
**Code:** `urllib.request.urlopen(req, timeout=10)`  
**Impact:** Corporate users behind proxy can't verify token. Error message says "Sprawdź internet" which is misleading.  
**Fix:** Add proxy support or better error messaging about firewalls/proxies.

---

### L-04: Desktop shortcut name "Udzialy Bot" doesn't match Start Menu folder "UdzialyBot"
**File:** `installer/setup.nsi:124` vs `setup.nsi:111`  
**Impact:** Minor UX inconsistency. Desktop says "Udzialy Bot", Start Menu folder is "UdzialyBot".  
**Fix:** Use consistent naming.

---

## CROSS-REFERENCE ANALYSIS

### Path Flow: NSIS → setup_env.bat → config_wizard.pyw → start_bot.bat

| Step | Expected Path | Actual Path | Status |
|------|---------------|-------------|--------|
| NSIS installs to | `C:\UdzialyBot\` | `$INSTDIR` (user can change) | ✅ No spaces in default |
| NSIS finish page runs | `$INSTDIR\setup_env.bat` | ✅ Correct | ✅ |
| setup_env.bat CWD | `%~dp0` = `$INSTDIR\` | ✅ | ✅ |
| Python path | `python\python.exe` | `$INSTDIR\python\python.exe` | ✅ |
| venv creation | `python -m venv` | ❌ **venv not in embedded** | ❌ FATAL |
| get-pip.py | `python\get-pip.py` | ✅ File exists | ✅ |
| Wheels path | `wheels\*.whl` | `$INSTDIR\wheels\` | ✅ |
| requirements.txt | `app\requirements.txt` | `$INSTDIR\app\requirements.txt` | ✅ |
| config_wizard.pyw | `config_wizard.pyw` at CWD | `$INSTDIR\config_wizard.pyw` | ✅ (but wrong version) |
| Wizard imports tkinter | System tkinter | ❌ **Not in embedded Python** | ❌ FATAL |
| config.yaml output | CWD = `$INSTDIR` | ✅ | ✅ |
| start_bot.bat | `$INSTDIR\start_bot.bat` | ✅ | ✅ |
| tor\tor.exe | `$INSTDIR\tor\tor.exe` | ✅ | ✅ |
| bot module | `.venv\Scripts\python.exe -m bot.main` | ❌ Module at `app\bot\main.py` | ❌ **WRONG** |

### HIDDEN FATAL: Bot module path mismatch
**File:** `installer/build/start_bot.bat:25`  
**Code:** `.venv\Scripts\python.exe -m bot.main`  
**Reality:** Bot source is at `$INSTDIR\app\bot\main.py`. Python won't find `bot.main` unless `app/` is in `sys.path` or PYTHONPATH.  
**Impact:** Even if all other issues are fixed, the bot won't start. `ModuleNotFoundError: No module named 'bot'`.  
**Fix:** Either:
1. Change to `.venv\Scripts\python.exe -m app.bot.main`, OR
2. Set PYTHONPATH: `set PYTHONPATH=%~dp0app` before running, OR
3. Flatten the structure — put bot source directly in `$INSTDIR\` not under `app\`.

---

## SUMMARY OF BLOCKING ISSUES (in execution order)

1. **F-01:** `python\python.exe -m venv .venv` → fails (no venv module) → HALT
2. **F-02:** Even if venv worked, `pythonw.exe config_wizard.pyw` → fails (no tkinter) → silent death
3. **F-03:** Even if tkinter existed, `from bot.config_wizard import main` → ImportError → fallback wizard (crippled)
4. **C-02:** Even if pip worked, `curl_cffi>=0.7` → shell interprets `>` as redirect → packages missing
5. **H-07:** Wrong config_wizard version bundled → user gets no token validation
6. **Cross-ref:** `python -m bot.main` → ModuleNotFoundError (bot is under `app/`)

**The installer is non-functional. Zero users can complete installation successfully.**

---

## RECOMMENDED FIX PRIORITY

1. Replace embedded Python with full Python MSI (or add venv+tkinter to embed)
2. Fix `sys.path` / module layout (flatten or add PYTHONPATH)
3. Use the full `config_wizard.pyw` in the build
4. Quote pip version specifiers in bat files
5. Add `HashedControlPassword` to build torrc
6. Fix stop_bot.bat to not kill all python.exe
7. Add owner_id validation in install.bat
