# PLAN V2 — Bot Udziały (LLM + GUI + Multi-Provider)

## Status: po 8 loopach research→discovery (POO Framework)
## Data: 2026-08-22
## Repo: github.com/qa10devteam/udzialy-bot

---

## RESEARCH ARTIFACTS (input do planu)

| Doc | Zakres | Size |
|-----|--------|------|
| RESEARCH_MULTI_LLM_API.md | 6 providerów, adapter pattern, koszty | 20KB |
| RESEARCH_GUI_DESIGN.md | tkinter modern, clam+custom, DPI, tray | 30KB |
| RESEARCH_LLM_PROMPTS.md | System prompt PL, JSON schema, cost est. | 645 lines |
| RESEARCH_ERROR_HANDLING.md | Degradacja, retry, provider quirks | — |
| RESEARCH_INTEGRATION_ARCHITECTURE.md | Full arch, config schema, file layout | 36KB |
| RESEARCH_ACCEPTANCE_AND_TASKS.md | 15 AC, 39 tasks, 10 risks | 18KB |
| DISCOVERY_LLM_ANALYZER_AUDIT.md | 7 gaps w istniejącym kodzie | 15KB |
| DISCOVERY_LAUNCHER_AUDIT.md | 12 gaps (5 critical, 5 important) | 10.7KB |
| DISCOVERY_PROCESS_MANAGEMENT.md | Subprocess pattern, prototype working | — |

---

## ARCHITEKTURA (FINAL)

```
[Desktop Icon] → launcher.pyw (GUI, jedyny entry point)
                    │
                    ├── [WIZARD] (first-run: token + ID + LLM key + portale)
                    │
                    ├── [DASHBOARD] (status 🟢/🔴, Start/Stop, logi)
                    │
                    ├── manages: tor.exe (CREATE_NO_WINDOW, taskkill /T /PID)
                    │
                    └── manages: python.exe -m bot.main (CREATE_NO_WINDOW)
                          │
                          ├── aiogram 3.x Dispatcher (polling)
                          ├── ScraperManager (4 portale: OLX, Morizon, Domiporta, Otodom)
                          ├── PropertyShareScorer (regex, threshold 25, F1=1.0)
                          ├── ListingAnalyzer (multi-LLM: OpenAI/DeepSeek/Claude/Gemini/Ollama)
                          └── DatabaseManager (SQLite WAL)
```

---

## MULTI-LLM PROVIDER STRATEGY

| Provider | Endpoint | Auth | Format | Cost/month (50/day) |
|----------|----------|------|--------|---------------------|
| **OpenAI** (GPT-4o-mini) | api.openai.com/v1/chat/completions | Bearer | OpenAI-compat | $0.44 |
| **DeepSeek** (v4-flash) | api.deepseek.com/v1/chat/completions | Bearer | OpenAI-compat | $0.17 |
| **Gemini** (flash) | generativelanguage.googleapis.com/v1beta/openai/ | Bearer | OpenAI-compat | $0.22 |
| **Claude** (haiku) | api.anthropic.com/v1/messages | x-api-key | CUSTOM adapter | $0.38 |
| **Ollama** (local) | localhost:11434/v1/chat/completions | None | OpenAI-compat | $0.00 |

**Architecture:** `OpenAICompatProvider` (5/6) + `AnthropicProvider` (1/6). ~200 LOC total.

---

## CONFIG.YAML (FINAL SCHEMA)

```yaml
telegram:
  token: ""          # @BotFather token
  owner_id: 0        # User's Telegram ID

llm:
  enabled: false     # false = basic mode (no AI)
  provider: "openai" # openai | deepseek | gemini | claude | ollama
  api_key: ""        # User's API key
  model: "gpt-4o-mini"
  base_url: ""       # Empty = auto from provider. Custom for ollama.
  max_concurrent: 3
  timeout: 15

portals:
  olx: true
  morizon: true
  domiporta: true
  otodom: true

tor:
  enabled: true
  socks_port: 9050
  control_port: 9051
  password: "udzialy2026"

scraping:
  timeout: 25
  delay_between: 2
  max_pages: 2

scorer:
  threshold: 25

database:
  path: "data/udzialy.db"
```

---

## GRACEFUL DEGRADATION

```
LEVEL 1 (full):     scrape → score → LLM analyze → rich Telegram msg (⭐📍💰📋🔗)
LEVEL 2 (no LLM):   scrape → score → basic Telegram msg (title + price + link)
LEVEL 3 (no Tor):   scrape Tier1 only (Morizon/Domiporta) → score → basic msg
LEVEL 4 (no inet):  show last cached results from SQLite
LEVEL 5 (crash):    launcher shows error in log + restart button
```

---

## 5-PHASE IMPLEMENTATION

### Phase A: LLM Multi-Provider Rewrite (detector/llm_analyzer.py)

| # | Task | LOC | Risk |
|---|------|-----|------|
| A1 | OpenAICompatProvider class (handles 5 providers) | 80 | Low |
| A2 | AnthropicProvider class (Claude custom format) | 60 | Med |
| A3 | System prompt (Polish, 780 tokens, few-shot examples) | 40 | Low |
| A4 | JSON response validator + repair (markdown fences, coercion) | 50 | Med |
| A5 | Retry logic (429→backoff, 401→disable, 5xx→retry once) | 40 | Low |
| A6 | Connection pooling (single httpx client, reused) | 20 | Low |
| A7 | Cost tracker (per-provider rates, session total) | 30 | Low |
| A8 | Provider auto-detection from config (base_url→provider) | 20 | Low |
| **Total** | | **340** | |

### Phase B: Launcher Rewrite (launcher.pyw)

| # | Task | LOC | Risk |
|---|------|-----|------|
| B1 | DPI awareness (SetProcessDpiAwareness before Tk) | 10 | Low |
| B2 | Clam theme + full custom styling (Segoe UI, #0078D4, flat) | 60 | Med |
| B3 | ProcessManager class (start/stop/kill, Queue-based logs) | 120 | High |
| B4 | taskkill /T /F /PID (tree kill, not terminate) | 15 | Low |
| B5 | PYTHONUNBUFFERED=1 in bot subprocess env | 5 | Low |
| B6 | atexit handler (cleanup on crash) | 15 | Low |
| B7 | Single instance mutex (Windows named mutex) | 20 | Med |
| B8 | Wizard Step 4: Multi-LLM provider selection | 80 | Med |
| B9 | Dashboard: status indicator (Canvas circle: 🟢🔴🟡) | 30 | Low |
| B10 | Dashboard: real-time log area (Text + tag colors) | 40 | Low |
| B11 | WM_DELETE_WINDOW handler (confirm + cleanup) | 20 | Low |
| B12 | Config migration (merge defaults for new sections) | 30 | Med |
| **Total** | | **445** | |

### Phase C: Bot Integration (bot/routers/)

| # | Task | LOC | Risk |
|---|------|-----|------|
| C1 | results.py: HTML format with LLM analysis (⭐📍💰📋🔗) | 60 | Low |
| C2 | results.py: fallback basic format when no LLM | 20 | Low |
| C3 | search.py: progress "Analizuję wyniki..." after scraping | 15 | Low |
| C4 | search.py: integrate ListingAnalyzer into search flow | 30 | Med |
| C5 | config.py: load LLM config section | 20 | Low |
| **Total** | | **145** | |

### Phase D: Installer Rebuild

| # | Task | LOC | Risk |
|---|------|-----|------|
| D1 | setup_v2.nsi: Desktop shortcut → pythonw.exe launcher.pyw | 10 | Low |
| D2 | setup_v2.nsi: Remove start_bot/stop_bot shortcuts | 5 | Low |
| D3 | setup_env.bat: run launcher.pyw --first-run after install | 10 | Low |
| D4 | build_v2.sh: include launcher.pyw in bundle root | 5 | Low |
| D5 | Remove deprecated: start_bot.bat, stop_bot.bat, config_wizard.pyw | 0 | Low |
| D6 | Rebuild .exe, verify PE32 | 0 | Low |
| **Total** | | **30** | |

### Phase E: Testing & Verification

| # | Task | LOC | Risk |
|---|------|-----|------|
| E1 | tests/test_llm_analyzer.py: mock multi-provider responses | 100 | Low |
| E2 | tests/test_launcher.py: config load/save, migration | 60 | Low |
| E3 | Integration: scraper → scorer → LLM → format pipeline | 80 | Med |
| E4 | Run all tests: 38 existing + new = pass | 0 | Low |
| E5 | Live portal test: search "udział" → results with scores | 0 | Low |
| E6 | Manual: install on Windows → wizard → search → verify | manual | High |
| **Total** | | **240** | |

---

## TOTAL ESTIMATE

| Phase | LOC | Time |
|-------|-----|------|
| A (LLM) | 340 | 4h |
| B (Launcher) | 445 | 6h |
| C (Bot integration) | 145 | 2h |
| D (Installer) | 30 | 1h |
| E (Testing) | 240 | 3h |
| **TOTAL** | **1200** | **16h** |

---

## ACCEPTANCE CRITERIA (10 core)

| AC | Kryterium | Verification |
|----|-----------|--------------|
| AC1 | Double-click icon → GUI opens (no console) | Manual Windows test |
| AC2 | First run → wizard (token + ID + LLM key) | Manual test |
| AC3 | After config → dashboard with Start button | Manual test |
| AC4 | Start → Tor invisible + bot connects + status 🟢 | Process check + API call |
| AC5 | /search → results with LLM analysis | Telegram test |
| AC6 | LLM results: ⭐ + summary PL + risks | Visual check |
| AC7 | No LLM key → basic mode works | Config without key + test |
| AC8 | Stop → no orphan processes + status 🔴 | tasklist check |
| AC9 | Close window → clean shutdown | atexit + process verify |
| AC10 | Installer no admin (Win10/11) | Fresh VM test |

---

## RISK REGISTER

| # | Risk | Prob | Impact | Mitigation |
|---|------|------|--------|------------|
| R1 | LLM API format changes | Low | Med | Provider pattern isolates — update one adapter |
| R2 | Portal HTML changes | Med | High | Modular scrapers, alerts on 0-result |
| R3 | Windows Defender blocks .exe | Med | High | ZIP fallback + instructions in README |
| R4 | Client can't get API key | Med | Low | Basic mode works without LLM |
| R5 | DeepSeek returns Chinese | Med | Low | "ODPOWIEDZ PO POLSKU" in prompt |
| R6 | Tor exit nodes blocked | Low | Low | OLX works without Tor (proven) |
| R7 | tkinter crash (theme issue) | Low | Med | Exception handling + fallback theme |
| R8 | Port 9050 already in use | Low | Med | Check + user-friendly error |
| R9 | nodriver Chromium outdated | Med | Med | Auto-update on launch |
| R10 | SQLite corruption | Low | High | WAL mode + startup integrity check |

---

## DEPENDENCY GRAPH (Critical Path)

```
A1 (OpenAI provider) ──→ A2 (Claude) ──→ A3-A8 (prompt, retry, etc.)
                                              │
B1-B7 (launcher fixes) ──→ B8 (LLM wizard step) ──→ B9-B12 (dashboard)
                                              │
                              C1-C5 (bot integration) ←─────┘
                                              │
                              D1-D6 (installer rebuild)
                                              │
                              E1-E6 (testing)
```

**Parallelism:** Phase A + Phase B (B1-B7) can run in parallel. Phase C depends on A. Phase D depends on B+C.

---

## EXECUTION STRATEGY

3 parallel subagents:
- **Agent 1:** Phase A (LLM multi-provider) — 340 LOC, 4h
- **Agent 2:** Phase B (Launcher rewrite) — 445 LOC, 6h
- **Agent 3:** Phase C (Bot integration) — after A finishes

Then sequential: D (installer) → E (testing) → verify → release.

---

## DELIVERY

Final product to klient:
1. **UdzialyBot-Setup.exe** (~50MB) — double-click, no admin
2. Wizard guides through: token + ID + wybór LLM provider + API key
3. Dashboard: Start/Stop, logi, status
4. Telegram: /search → ⭐⭐⭐⭐ + podsumowanie PL + rekomendacja

**WOW factor:** AI analizuje każde ogłoszenie i mówi klientowi: "To jest okazja. Syndyk sprzedaje bo musi. Kup zanim inni zobaczą."
