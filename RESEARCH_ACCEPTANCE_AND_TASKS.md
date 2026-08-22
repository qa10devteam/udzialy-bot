# POO Loops 7-8: Acceptance Criteria, Task Breakdown & Test Plan

**Date:** 2026-08-22  
**Project:** udzialy-bot (Bot Udziały)  
**User:** Non-technical real estate professional, Windows PC, Gdynia  
**Budget:** 2000 PLN  
**WOW Factor:** LLM analysis with stars, Polish summary, risks, price assessment

---

## 1. ACCEPTANCE CRITERIA (Definition of Done)

| AC# | Criterion | Verification Method | Priority |
|-----|-----------|-------------------|----------|
| AC1 | User double-clicks `.exe` icon → GUI opens (no console window, no crash) | Manual: double-click on Win10/11 | 🔴 P0 |
| AC2 | First run → wizard guides through: Telegram token + Owner ID + LLM provider/key + portal selection | Manual: delete config.yaml, relaunch | 🔴 P0 |
| AC3 | After config saved → dashboard shows Start button, status indicator = red (stopped) | Manual: complete wizard | 🔴 P0 |
| AC4 | Click Start → Tor starts invisibly (no console), bot connects, status = green, log shows activity | Manual: click Start, verify no console windows appear | 🔴 P0 |
| AC5 | User sends `/search` in Telegram → gets results with LLM analysis (stars + summary) | Manual: send /search to bot | 🔴 P0 |
| AC6 | LLM results show: ⭐ stars (1-5), summary in Polish, risks list, price assessment (okazja/uczciwa/droga) | Manual: inspect message formatting | 🟡 P1 |
| AC7 | No LLM key configured → bot still works (basic mode: title + price + link only) | Manual: leave LLM key empty in wizard, run /search | 🔴 P0 |
| AC8 | Click Stop → bot + Tor stop completely, no orphan processes, status = red | Manual: click Stop, check Task Manager | 🔴 P0 |
| AC9 | Close window (X button) → all processes stop cleanly (no zombies) | Manual: close GUI, check Task Manager | 🔴 P0 |
| AC10 | Installer (.exe) runs without admin privileges on Windows 10/11, installs to `%LOCALAPPDATA%` | Manual: run installer on standard user account | 🟡 P1 |

### Additional Acceptance Criteria (Derived from Audit)

| AC# | Criterion | Verification Method | Priority |
|-----|-----------|-------------------|----------|
| AC11 | GUI is crisp on HiDPI displays (125%, 150%, 200% scaling) — no blur | Manual: test on 1080p laptop with 125% | 🟡 P1 |
| AC12 | GUI uses modern flat design (white/light bg, accent blue, no 3D borders) | Visual inspection | 🟢 P2 |
| AC13 | LLM provider selection works: OpenAI / DeepSeek / Gemini / Claude / Ollama / LM Studio | Manual: configure each provider | 🟡 P1 |
| AC14 | Crash recovery: if previous Tor still on port 9050, launcher detects and handles | Manual: kill launcher via Task Manager, re-launch | 🟡 P1 |
| AC15 | Single instance: cannot run two launchers simultaneously | Manual: try double-launch | 🟢 P2 |

---

## 2. IMPLEMENTATION TASK BREAKDOWN

### Phase A: LLM Multi-Provider Rewrite (`detector/llm_analyzer.py`)

| Task | Description | Files | LOC Δ | Risk | Deps |
|------|-------------|-------|-------|------|------|
| A1 | Provider adapter base class + OpenAI adapter | `detector/llm_analyzer.py` | +120 new | Low | None |
| A2 | Claude adapter (different endpoint, headers, request/response) | `detector/llm_analyzer.py` | +80 new | Med | A1 |
| A3 | Shared httpx.AsyncClient (connection pooling, reuse) | `detector/llm_analyzer.py` | ~30 changed | Low | A1 |
| A4 | Retry with exponential backoff (429/500/timeout) | `detector/llm_analyzer.py` | +40 new | Low | A1 |
| A5 | Error differentiation (401→invalid key, 429→rate limit, 500→retry) | `detector/llm_analyzer.py` | +30 new | Low | A4 |
| A6 | Multi-model cost tracking (per-provider pricing table) | `detector/llm_analyzer.py` | +25 new | Low | A1 |
| A7 | Fallback chain (primary→fallback provider on failure) | `detector/llm_analyzer.py` | +35 new | Med | A1, A5 |
| A8 | API key validation method (test call with short prompt) | `detector/llm_analyzer.py` | +20 new | Low | A1 |
| A9 | Updated system prompt (v2 from RESEARCH_LLM_PROMPTS.md) | `detector/llm_analyzer.py` | ~50 changed | Low | None |

**Phase A Totals:** 1 file, ~430 LOC new/changed | Overall Risk: **Medium**

---

### Phase B: Launcher Rewrite (`launcher.pyw` — fix all 12 gaps)

| Task | Description | Files | LOC Δ | Risk | Deps |
|------|-------------|-------|-------|------|------|
| B1 | DPI awareness: `SetProcessDpiAwareness(2)` before `Tk()` | `launcher.pyw` | +5 new | Low | None |
| B2 | Theme: force `clam` + full custom style overrides (50+ lines) | `launcher.pyw` | +55 new, ~10 changed | Low | None |
| B3 | Tree kill: replace `terminate()` with `taskkill /T /F /PID` | `launcher.pyw` | ~25 changed | Med | None |
| B4 | PYTHONUNBUFFERED=1 in bot Popen env | `launcher.pyw` | +3 new | Low | None |
| B5 | atexit.register() safety net for cleanup | `launcher.pyw` | +5 new | Low | None |
| B6 | Stale Tor detection (port 9050 busy → offer reuse/kill) | `launcher.pyw` | +20 new | Med | None |
| B7 | Queue-based log polling (thread → Queue → after(100ms)) | `launcher.pyw` | ~40 changed | Med | None |
| B8 | LLM provider selection in wizard Step 4 (dropdown + key field) | `launcher.pyw` | +70 new, ~20 changed | Med | A1 |
| B9 | LLM provider in Settings dialog | `launcher.pyw` | +30 new | Low | B8 |
| B10 | Modern styling: white bg, accent color, flat buttons, card panels | `launcher.pyw` | +40 new | Low | B2 |
| B11 | Single-instance mutex (`CreateMutexW`) | `launcher.pyw` | +12 new | Low | None |
| B12 | Config save/load for multi-provider LLM section | `launcher.pyw` | ~30 changed | Med | A1 |
| B13 | Colored log tags ([INFO] green, [ERROR] red, [WARN] yellow) | `launcher.pyw` | +20 new | Low | B7 |

**Phase B Totals:** 1 file, ~250 LOC new/changed | Overall Risk: **Medium-High** (most complex phase)

---

### Phase C: Bot Integration (Results Formatting with LLM)

| Task | Description | Files | LOC Δ | Risk | Deps |
|------|-------------|-------|-------|------|------|
| C1 | Format LLM results into Telegram message (stars, summary, risks) | `bot/routers/search.py` | ~60 changed | Low | A1 |
| C2 | Basic mode formatter (title + price + link when no LLM) | `bot/routers/search.py` | +20 new | Low | None |
| C3 | Initialize LLM analyzer from config in bot startup | `bot/main.py` | +15 new | Low | A1, B12 |
| C4 | Pass LLM results through ScraperManager pipeline | `scraper/manager.py` | ~20 changed | Med | A1 |
| C5 | Pagination for multiple results (inline keyboard buttons) | `bot/keyboards/inline.py`, `bot/routers/search.py` | +40 new | Low | C1 |
| C6 | `/status` command showing LLM provider + cost spent | `bot/routers/settings.py` | +25 new | Low | A6 |

**Phase C Totals:** 4-5 files, ~180 LOC new/changed | Overall Risk: **Medium**

---

### Phase D: Installer Rebuild (NSIS)

| Task | Description | Files | LOC Δ | Risk | Deps |
|------|-------------|-------|-------|------|------|
| D1 | Update NSIS script: entry point = `launcher.pyw` via `pythonw.exe` | `installer/udzialy.nsi` | ~30 changed | Med | B* |
| D2 | Desktop shortcut: `pythonw.exe launcher.pyw` (no console) | `installer/udzialy.nsi` | ~5 changed | Low | D1 |
| D3 | Install to `%LOCALAPPDATA%\BotUdzialy` (no admin required) | `installer/udzialy.nsi` | ~15 changed | Med | None |
| D4 | Bundle updated `detector/llm_analyzer.py` | `installer/build.py` or equivalent | ~5 changed | Low | A* |
| D5 | Remove old batch files from bundle | `installer/build.py` | ~5 changed | Low | None |
| D6 | Test build: produce .exe installer artifact | CI/manual | N/A | High | D1-D5 |
| D7 | Code-sign the installer (optional — reduces Defender warnings) | CI/manual | N/A | High | External cert |

**Phase D Totals:** 2-3 files, ~60 LOC changed | Overall Risk: **High** (Windows-only testing)

---

### Phase E: Testing & Verification

| Task | Description | Files | LOC Δ | Risk | Deps |
|------|-------------|-------|-------|------|------|
| E1 | Unit tests: LLM provider adapters (mock httpx responses) | `tests/test_llm_analyzer.py` | +200 new | Low | A* |
| E2 | Unit tests: scorer unchanged behavior | `tests/test_scorer.py` | verify existing | Low | None |
| E3 | Unit tests: config load/save with multi-provider section | `tests/test_config.py` | +50 new | Low | B12 |
| E4 | Integration test: ScraperManager + LLM analyzer pipeline | `tests/test_pipeline.py` | +80 new | Med | A*, C4 |
| E5 | E2E test: /search flow with mocked LLM (CI-safe) | `tests/test_e2e_search.py` | +100 new | Med | C* |
| E6 | Manual: Windows install + wizard + search + results | Checklist | N/A | High | All |
| E7 | Manual: HiDPI display test (125%, 150%) | Checklist | N/A | Med | B1 |
| E8 | Manual: process cleanup verification (Task Manager) | Checklist | N/A | Med | B3, B5 |

**Phase E Totals:** 4-5 new test files, ~430 LOC | Overall Risk: **Medium**

---

## 3. TASK SIZING SUMMARY

| Phase | Files Modified | New Files | LOC New/Changed | Risk | Calendar Estimate |
|-------|---------------|-----------|-----------------|------|-------------------|
| A: LLM Multi-Provider | 1 | 0 | ~430 | Medium | 4-6 hours |
| B: Launcher Rewrite | 1 | 0 | ~250 | Medium-High | 6-8 hours |
| C: Bot Integration | 4-5 | 0 | ~180 | Medium | 3-4 hours |
| D: Installer Rebuild | 2-3 | 0 | ~60 | High | 2-3 hours |
| E: Testing | 0 | 4-5 | ~430 | Medium | 4-5 hours |
| **TOTAL** | **8-10** | **4-5** | **~1350** | **Med-High** | **19-26 hours** |

### Dependency Graph

```
Phase A (LLM) ──────────────────────────┐
                                         ├──→ Phase C (Bot Integration)
Phase B (Launcher) ─────────────────────┤
    B1-B7: independent                  │
    B8-B12: depends on A1               │
                                         ├──→ Phase D (Installer)
                                         │
                                         └──→ Phase E (Testing)
```

**Critical Path:** A1 → A2 → B8 → C1 → C3 → D1 → D6 → E6

---

## 4. TEST PLAN

### 4.1 Unit Tests (Automated, CI-safe)

| Test Suite | What It Validates | Mocking Strategy |
|------------|-------------------|------------------|
| `test_llm_analyzer.py` | Provider adapter dispatch, request building, response parsing, error handling, retry logic, cost calculation | Mock `httpx.AsyncClient` with predefined responses |
| `test_scorer.py` | Scoring algorithm (existing), keyword matching, filters | Pure functions, no mocking needed |
| `test_config.py` | YAML read/write, multi-provider section, migration from old format | Temp files, fixture configs |
| `test_formatters.py` | Telegram message formatting (stars→emoji, risks→bullet list, basic mode fallback) | AnalysisResult fixtures |

**Coverage target:** ≥80% on `detector/llm_analyzer.py`, `bot/routers/search.py`

### 4.2 Integration Tests (Automated, CI-safe)

| Test | Pipeline | Mocking |
|------|----------|---------|
| ScraperManager → LLM Analyzer | Feed scraped listing dict → get AnalysisResult | Mock httpx for LLM, real scorer logic |
| Config wizard → Config file → LLM init | Save config via wizard logic → load → create analyzer | Temp config file |
| Bot router → ScraperManager → formatted message | Simulate /search → verify output message contains stars + summary | Mock ScraperManager results |

### 4.3 End-to-End Tests (CI with mocks)

| Test | Flow | Mocked Components |
|------|------|-------------------|
| Full /search | User sends /search → bot triggers scrape → LLM analysis → formatted reply | httpx (LLM), aiohttp (portals via fixtures) |
| Graceful degradation | /search with LLM timeout → fallback to basic mode | httpx raises TimeoutError |
| Multi-provider switch | Change provider in config → next /search uses new provider | Both providers mocked |

### 4.4 Manual Test Checklist (Windows only)

```markdown
## Pre-deployment Manual Test Checklist

### Installation
- [ ] Run installer on Win10 (standard user, no admin)
- [ ] Run installer on Win11 (standard user, no admin)
- [ ] Verify installs to %LOCALAPPDATA%\BotUdzialy
- [ ] Desktop shortcut created and has icon
- [ ] Start menu entry created

### First Run
- [ ] Double-click shortcut → GUI opens (no console)
- [ ] Wizard appears with Welcome screen
- [ ] Enter Telegram token → validates with BotFather
- [ ] Enter Owner ID → numeric validation
- [ ] Select LLM provider from dropdown (test: OpenAI, DeepSeek)
- [ ] Enter LLM API key → validation test call succeeds
- [ ] Select portals → at least Otodom + OLX checked
- [ ] Click Finish → config.yaml created correctly
- [ ] Dashboard appears with Start button

### Operation
- [ ] Click Start → Tor starts (no console window)
- [ ] Status turns green within 30s
- [ ] Log area shows real-time output
- [ ] Send /search in Telegram → results appear
- [ ] Results show: ⭐ stars + Polish summary + risks
- [ ] Price assessment shows: okazja/uczciwa/droga
- [ ] Send /help → command list appears
- [ ] Click Stop → status turns red within 5s
- [ ] Task Manager: no orphan tor.exe or python.exe

### Error Handling
- [ ] Remove LLM key from config → /search gives basic results (no crash)
- [ ] Start with port 9050 already busy → launcher detects, offers solution
- [ ] Kill launcher via Task Manager → Tor+Bot processes cleaned up
- [ ] Double-launch → second instance shows "already running" message

### Display
- [ ] 100% scaling: UI crisp, text readable
- [ ] 125% scaling: no blur, proper layout
- [ ] 150% scaling: no blur, buttons accessible
```

---

## 5. RISK REGISTER

| # | Risk | Probability | Impact | Mitigation | Contingency |
|---|------|-------------|--------|------------|-------------|
| R1 | **LLM API changes response format** (OpenAI drops `choices` array, Claude changes `content` structure) | Low (stable APIs) | High (breaks analysis) | Version-pin model names; validate response schema before parsing; unit tests with recorded responses | Graceful fallback to basic mode (AC7 ensures this always works) |
| R2 | **Portal HTML changes** (Otodom redesign, OLX new layout) | Medium (happens ~2x/year) | Medium (one portal breaks) | CSS selector config per portal (not hardcoded); multiple portals = redundancy; error-per-portal logging | Disable broken portal via config; alert user; other portals continue |
| R3 | **Windows Defender / SmartScreen blocks installer** | Medium (unsigned .exe) | High (user can't install) | Install to `%LOCALAPPDATA%` (no admin = fewer flags); add publisher info to NSIS metadata; document "allow" click for user | Provide .zip alternative (manual extract); long-term: EV code signing cert (~$400/year) |
| R4 | **Client can't get API key** (doesn't understand, afraid of credit card) | High (non-tech user) | Medium (loses WOW factor) | Step-by-step Polish guide with screenshots in wizard; recommend DeepSeek (no credit card required for free tier); basic mode always works (AC7) | Pre-configure DeepSeek free tier key; or offer Ollama local option (if user has decent hardware) |
| R5 | **Tor blocked by ISP/network** | Low (Poland ISPs don't block) | High (scraping stops) | Bundle Tor bridges (obfs4); detect connection failure → suggest bridges config | Direct scraping mode (no Tor) as fallback with rotating user agents |
| R6 | **Python embedded runtime conflicts** | Low | Medium | Pin Python 3.11.x in bundle; test with exact bundled version; no system Python dependency | Include full Python in installer bundle (already done) |
| R7 | **Concurrent LLM calls exceed rate limit** | Medium (heavy /search) | Low (retry handles it) | Semaphore (max 3 concurrent); exponential backoff on 429; cost cap per day | Queue excess requests; inform user of delay |
| R8 | **Large Telegram messages truncated** (>4096 chars) | Medium | Low (formatting issue) | Split messages >4000 chars; paginate with inline buttons; truncate risk list to top-3 | Send as multiple messages |
| R9 | **Config migration from v1.x** | Certain (existing users) | Medium | Detect old config format → auto-migrate adding `llm:` section with empty provider; preserve existing `openai.api_key` | Manual config edit instructions in release notes |
| R10 | **DPI scaling breaks layout on unusual displays** | Low | Low (cosmetic) | Use relative sizing (`pack fill`, `grid weight`); test on 100/125/150/200%; min window size | Works functionally even if layout shifts |

---

## 6. DEFINITION OF "SHIPPING READY"

All **P0 acceptance criteria (AC1-AC5, AC7-AC9)** pass on actual Windows 10 or 11.

### Minimum Viable Release:
- AC1 ✅ — GUI opens clean
- AC2 ✅ — Wizard works
- AC3 ✅ — Dashboard functional
- AC4 ✅ — Start works
- AC5 ✅ — /search with LLM
- AC7 ✅ — Basic mode fallback
- AC8 ✅ — Stop works clean
- AC9 ✅ — Close works clean

### Nice-to-have for v1.0 (can ship without):
- AC6 — Full formatting polish
- AC10 — No-admin installer (can use .zip)
- AC11-AC15 — DPI, styling, multi-provider full suite

---

## 7. IMPLEMENTATION ORDER (Optimal Sequence)

```
Week 1 (Phases A + B-core):
├── Day 1-2: A1-A5 (provider adapters + retry + errors)
├── Day 2-3: A6-A9 (cost tracking + fallback + prompt)
├── Day 3-4: B1-B7 (launcher fixes: DPI, theme, kill, log)
└── Day 4-5: B8-B13 (LLM selection in wizard + settings)

Week 2 (Phases C + D + E):
├── Day 1-2: C1-C6 (bot integration + formatting)
├── Day 2-3: D1-D6 (installer rebuild)
├── Day 3-4: E1-E5 (automated tests)
└── Day 4-5: E6-E8 (manual Windows testing + fixes)
```

**Total estimated effort: 19-26 hours of focused development**

---

## 8. SUCCESS METRICS

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first search result | < 60s from Start click | Stopwatch |
| LLM analysis accuracy | > 85% correct is_real_share | Sample of 20 listings |
| Process cleanup reliability | 100% (no orphans) | 10 start/stop cycles |
| Install success rate | 100% on clean Win10/11 | 3 test machines |
| Basic mode (no LLM) usability | All core features work | /search returns results |
| User satisfaction | Client says "WOW" | Demo session |

---

*Document generated by POO Framework — Loops 7-8 (Acceptance & Planning)*
