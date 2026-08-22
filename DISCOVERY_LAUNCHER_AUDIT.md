# Launcher.pyw Audit — Gap Analysis vs Research Recommendations

**Date:** 2026-08-22  
**Source files audited:**
- `launcher.pyw` (984 lines, 38KB, 4 classes: SetupWizard, SettingsDialog, Dashboard, Application)
- `RESEARCH_GUI_DESIGN.md` (30KB — theme, fonts, colors, patterns)
- `DISCOVERY_PROCESS_MANAGEMENT.md` (17KB — subprocess, kill, buffering)

---

## AUDIT CHECKLIST

### ✅ = Present and correct
### ⚠️ = Partially implemented / needs improvement
### ❌ = Missing entirely

---

## 1. DPI Awareness — SetProcessDpiAwareness(2) before Tk()

**Status: ❌ MISSING**

- **Required:** Call `windll.shcore.SetProcessDpiAwareness(2)` (per-monitor DPI) BEFORE `tk.Tk()` is instantiated
- **Current:** `Application.__init__()` just calls `self.root = tk.Tk()` at line 899 with no DPI setup
- **Impact:** Text and UI will look BLURRY on HiDPI displays (125%, 150%, 200% scaling)
- **Fix:** Add DPI awareness block between imports and the `Application()` construction at `__main__`

---

## 2. Theme: 'clam' with custom style overrides

**Status: ⚠️ PARTIAL — uses clam as fallback only, NO custom styling**

- **Current (line 913-918):**
  ```python
  style = ttk.Style()
  if "vista" in available:
      style.theme_use("vista")  # PREFERS vista!
  elif "clam" in available:
      style.theme_use("clam")
  ```
- **Problem:** Prefers `vista` theme which CANNOT be customized (colors/padding locked by OS). Falls back to `clam` only if `vista` unavailable (never on real Windows).
- **Missing:** Zero `style.configure()` calls. No custom colors, no accent color, no flat buttons, no modern styling at all.
- **Research says:** Use `clam` ALWAYS + full custom style overrides (50+ lines of `style.configure/style.map`)
- **Impact:** App looks like default 2005 Windows — gray, 3D borders, no brand identity

---

## 3. CREATE_NO_WINDOW for subprocesses

**Status: ✅ CORRECT**

- Constant defined at line 38: `CREATE_NO_WINDOW = 0x08000000`
- Applied to Tor (line 729): `creationflags=CREATE_NO_WINDOW`
- Applied to Bot (line 774): `creationflags=CREATE_NO_WINDOW`
- Both correct.

---

## 4. Thread + Queue + after() for log capture

**Status: ⚠️ PARTIAL — Thread + after() used, but NO Queue**

- **Current:** Uses `root.after(0, _do)` directly from reader thread (line 703 in `_log()`)
- **Missing:** No `queue.Queue` — directly schedules GUI updates from worker thread
- **Risk:** While `root.after()` is technically thread-safe for scheduling, the recommended pattern uses Queue for cleaner separation (process manager decoupled from GUI).
- **Missing:** No periodic `after(100, poll)` loop — instead relies on `root.after(0, ...)` from thread
- **Research says:** Thread → Queue → `after(100ms)` poll = standard tkinter threading pattern
- **Impact:** Works functionally but architecturally fragile; no batching of rapid log lines

---

## 5. taskkill /T /F /PID (tree kill)

**Status: ❌ MISSING — only uses terminate()/kill()**

- **Current `_kill_bot()` (line 845-855):**
  ```python
  self.bot_proc.terminate()
  self.bot_proc.wait(timeout=5)
  # fallback:
  self.bot_proc.kill()
  ```
- **Current `_kill_tor()` (line 857-867):** Same pattern — terminate + kill
- **Problem:** `terminate()` on Windows = TerminateProcess() which ONLY kills the direct process, NOT children
- **Research says:** Must use `taskkill /T /F /PID {pid}` to kill entire process tree
- **Impact:** Orphaned Tor child processes will persist after stop. Bot subprocesses may linger.

---

## 6. PYTHONUNBUFFERED=1 for bot subprocess

**Status: ❌ MISSING**

- **Current (line 770-777):**
  ```python
  self.bot_proc = subprocess.Popen(
      [PYTHON_PATH, "-m", "bot.main"],
      ...
      bufsize=1  # Only helps if child is line-buffered
  )
  ```
- **Missing:** No `env={'PYTHONUNBUFFERED': '1'}` parameter
- **Missing:** No `-u` flag in command
- **Research says:** Python buffers stdout when not connected to a terminal. MUST set `PYTHONUNBUFFERED=1` or pass `-u`
- **Impact:** Log output will appear in large chunks (4KB buffer), not real-time. User sees nothing for minutes, then a flood.

---

## 7. First-run wizard (token + ID + LLM key + portals)

**Status: ⚠️ PARTIAL — has 4/5 required steps, missing LLM provider selection**

- **Current wizard steps:**
  1. Welcome (✅)
  2. Telegram token (✅ — with validation + live check)
  3. Owner ID (✅ — with numeric validation)
  4. OpenAI key — **hardcoded to OpenAI only** (⚠️)
  5. Portal selection (✅)

- **Missing:** No multi-provider LLM selection (Claude, DeepSeek, Gemini, Local/Ollama)
- **Current:** Step 4 only mentions "OpenAI" and "GPT-4" — config saves as `openai.api_key`
- **Research context says:** Step 4 should offer: OpenAI / Claude / DeepSeek / Gemini / Local (Ollama)
- **Impact:** Users with non-OpenAI keys have no way to configure them through the wizard

---

## 8. Error handling: Tor already running? Port 9050 busy? Python not found?

**Status: ⚠️ PARTIAL**

| Check | Status | Location |
|-------|--------|----------|
| Python not found | ✅ | Line 763: `if not os.path.exists(PYTHON_PATH)` |
| Tor not found | ✅ | Line 718: `if not os.path.exists(TOR_PATH)` |
| Tor already running / Port 9050 busy | ❌ MISSING | No pre-check before starting Tor |
| Port 9050 timeout | ✅ | Line 738-755: 60s polling loop |

- **Missing:** No check for stale Tor on startup. If port 9050 is already bound (previous crash), the launcher will start ANOTHER Tor process, which will fail silently.
- **Research says:** On startup, check if port 9050 is already bound → offer to reuse or kill existing
- **Impact:** Confusing failure mode when user double-launches or previous instance crashed

---

## 9. atexit handler for cleanup

**Status: ❌ MISSING**

- No `import atexit` anywhere in the file
- No `atexit.register()` call
- `Dashboard.cleanup()` exists but is only called from `Application._on_close()`
- **Problem:** If the GUI crashes (unhandled exception), or is killed via Task Manager, Tor+Bot processes become orphans
- **Research says:** `atexit.register(pm.stop_all)` as safety net
- **Impact:** Zombie Tor/Bot processes after crash

---

## 10. UI: Segoe UI font, generous padding, flat design

**Status: ⚠️ PARTIAL — fonts yes, padding/flat design NO**

| Aspect | Status | Evidence |
|--------|--------|----------|
| Segoe UI font | ✅ | Used everywhere: line 229, 292-308, etc. |
| Consolas for mono | ✅ | Line 328, 651 |
| Generous padding | ⚠️ | `padx=20, pady=10` (line 217) — research says 32px window padding |
| Flat design | ❌ | No `relief='flat'` anywhere. Uses default ttk 3D borders |
| White background | ❌ | Uses default gray (#d9d9d9) |
| Accent color (#0078D4) | ❌ | No accent color defined or used |
| Card-style panels | ❌ | Uses LabelFrame with default border styling |

- **Impact:** App looks dated, not professional. Default gray tk bg, raised borders everywhere.

---

## 11. config.yaml read/write

**Status: ✅ CORRECT (with caveats)**

- **Read:** Line 64-106 — loads YAML with pyyaml or fallback regex parser
- **Write:** Line 109-184 — generates well-formatted YAML with comments
- **Validation:** Line 187-194 — checks for placeholder tokens
- **Caveat 1:** Fallback parser (regex) handles only basic patterns — nested YAML breaks
- **Caveat 2:** `save_config()` regenerates the ENTIRE file — any manual edits/comments are lost
- **Caveat 3:** Only saves OpenAI section — no support for other LLM providers in config format

---

## 12. LLM provider selection (OpenAI/Claude/DeepSeek/Gemini/Local)

**Status: ❌ MISSING — hardcoded to OpenAI only**

- Wizard step 4 (line 366-386): Only "Klucz OpenAI" field
- Settings dialog (line 520-525): Only "Klucz API OpenAI" field  
- Config save (line 122-127): Only saves `openai:` section
- Config load fallback (line 91-93): Only parses `openai_api_key`
- **No dropdown/radio for provider selection**
- **No fields for Claude API key, DeepSeek key, Gemini key, or Ollama URL**
- **Impact:** Bot cannot use alternative LLM providers — locked to OpenAI

---

## SUMMARY: GAP PRIORITY LIST

### 🔴 Critical (must fix — functional impact)

| # | Gap | Impact |
|---|-----|--------|
| 1 | No DPI awareness | Blurry UI on most modern laptops (125%+ scaling) |
| 2 | No tree kill (taskkill /T) | Orphan processes after stop |
| 3 | No PYTHONUNBUFFERED=1 | Log output delayed/batched, not real-time |
| 4 | No atexit handler | Zombie processes on crash |
| 5 | No stale-Tor detection | Double Tor launch on re-run after crash |

### 🟡 Important (should fix — UX/architecture)

| # | Gap | Impact |
|---|-----|--------|
| 6 | Wrong theme (vista instead of clam) | Cannot customize colors/padding |
| 7 | No custom style overrides | App looks like 2005 Windows |
| 8 | No Queue-based log polling | Architecturally fragile |
| 9 | No multi-provider LLM selection | Users locked to OpenAI |
| 10 | Padding too small, no flat design | Not modern/professional |

### 🟢 Nice to have (polish)

| # | Gap | Impact |
|---|-----|--------|
| 11 | No single-instance mutex | Can launch multiple copies |
| 12 | Fallback YAML parser is fragile | May break on complex configs |
| 13 | No colored log tags (INFO/ERROR/WARN) | Log less readable |
| 14 | No status indicator Canvas circles | Less visual feedback |
| 15 | Settings doesn't show LLM provider | Incomplete settings |

---

## WHAT'S ALREADY GOOD ✅

1. **CREATE_NO_WINDOW** — correctly used for both Tor and Bot
2. **Threading** — daemon threads for start sequence and log reading
3. **Port polling** — socket.connect_ex() with timeout for Tor readiness
4. **Wizard flow** — multi-step with back/forward, validation, live token check
5. **Close handling** — asks user about running bot on window close
6. **Config I/O** — YAML read/write with fallback parser
7. **Font choice** — Segoe UI + Consolas throughout
8. **Token validation** — regex + live API check to BotFather
9. **Log area** — dark bg ScrolledText with auto-scroll and line pruning
10. **State management** — stopped/starting/running with button enable/disable

---

## RECOMMENDED FIX ORDER

1. Add DPI awareness before Tk() (2 lines)
2. Switch to `clam` + full custom style (50 lines)
3. Add `taskkill /T /F /PID` in kill functions (10 lines)
4. Add `PYTHONUNBUFFERED=1` to bot Popen env (3 lines)
5. Add `atexit.register()` (2 lines)
6. Add stale port 9050 check on start (15 lines)
7. Replace direct after() logging with Queue + poll pattern (30 lines)
8. Add LLM provider selection to wizard Step 4 (60 lines)
9. Apply full modern style (white bg, accent color, flat buttons, padding)
10. Add single-instance mutex (10 lines)

**Estimated total diff: ~200-250 lines changed/added**
