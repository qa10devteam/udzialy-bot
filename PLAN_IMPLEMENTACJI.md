# PLAN IMPLEMENTACJI — udzialy-bot
## 200 tasków, 10 faz

**Klient:** Marek Knapczyk, Gdynia | **Budżet:** 2000 PLN | **Delivery:** Telegram bot, Windows PC
**Repo:** github.com/qa10devteam/udzialy-bot | **Status scaffold:** 56 plików, 8473 LOC

---

## FAZA 1: Environment & Dependencies (T001–T020)

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T001 | Utworzenie venv Pythona (3.11+) dla projektu na EC2 | HIGH | 5m |
| T002 | Instalacja requirements.txt w venv | HIGH | 5m |
| T003 | Weryfikacja importu aiogram 3.x (wersja, async compat) | HIGH | 5m |
| T004 | Weryfikacja importu curl_cffi (TLS impersonation działa) | HIGH | 5m |
| T005 | Weryfikacja importu nodriver (CDP headless launch) | HIGH | 10m |
| T006 | Weryfikacja importu patchright (stealth Playwright) | HIGH | 10m |
| T007 | Instalacja Tor na EC2 (apt install tor) | HIGH | 5m |
| T008 | Konfiguracja Tor SOCKS5 (port 9050, ControlPort 9051) | HIGH | 10m |
| T009 | Test stem library — circuit renewal (NEWNYM) | HIGH | 10m |
| T010 | Weryfikacja httpx[socks] — połączenie przez Tor proxy | HIGH | 5m |
| T011 | Weryfikacja curl_cffi z Tor SOCKS5 proxy | HIGH | 10m |
| T012 | Weryfikacja nodriver z --proxy-server socks5 | MED | 15m |
| T013 | Weryfikacja patchright z proxy option | MED | 15m |
| T014 | Instalacja selectolax (parser HTML, alternatywa BS4) | LOW | 5m |
| T015 | Instalacja primp (Rust TLS) — sprawdzenie wheel availability | MED | 10m |
| T016 | Setup pytest + pytest-asyncio w projekcie | HIGH | 5m |
| T017 | Konfiguracja logging (structured, per-module loggers) | MED | 15m |
| T018 | Utworzenie .env.example z placeholderami (TG_TOKEN, TOR_PASSWORD) | LOW | 5m |
| T019 | Weryfikacja aiosqlite — async SQLite operations | HIGH | 5m |
| T020 | Smoke test: cały requirements.txt importuje się bez błędów | HIGH | 10m |

---

## FAZA 2: Core Infrastructure (T021–T040)

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T021 | Implementacja config.py — load config.yaml + env override | HIGH | 20m |
| T022 | Test: config ładuje się z YAML, env vars nadpisują | HIGH | 10m |
| T023 | Implementacja database.py — DDL (CREATE TABLE, indexes) | HIGH | 30m |
| T024 | Test: DB init tworzy 4 tabele + indexy, WAL mode ON | HIGH | 15m |
| T025 | Implementacja models.py — Pydantic Listing/Filter/SearchResult | HIGH | 20m |
| T026 | Implementacja queries.py — upsert_listing (INSERT OR REPLACE) | HIGH | 25m |
| T027 | Implementacja queries.py — get_listings z filtrami + paginacją | HIGH | 30m |
| T028 | Implementacja queries.py — save/unsave_listing | MED | 15m |
| T029 | Implementacja queries.py — CRUD user_filters | MED | 20m |
| T030 | Implementacja queries.py — search_history_add + get | LOW | 15m |
| T031 | Test: upsert 100 listingów, verify deduplikacja (source_url UNIQUE) | HIGH | 15m |
| T032 | Test: get_listings z filtrem voivodeship + city + price range | HIGH | 15m |
| T033 | Test: paginacja (offset/limit) poprawna na 200 rekordach | MED | 10m |
| T034 | Implementacja geo/cities.py — load JSON, search, autocomplete | HIGH | 30m |
| T035 | Rozszerzenie data/cities.json do 1000 miast PL (real coords) | HIGH | 30m |
| T036 | Implementacja geo/distance.py — haversine formula | HIGH | 15m |
| T037 | Test: haversine Warszawa→Gdynia = ~340km (±5km) | HIGH | 5m |
| T038 | Test: filter_by_radius — 10 listingów, 3 w promieniu 50km od Gdyni | HIGH | 10m |
| T039 | Implementacja get_voivodeships() — sorted lista 16 województw | LOW | 5m |
| T040 | Integration test: DB init → insert → query z geo filter → result | HIGH | 20m |

---

## FAZA 3: Stealth Engine (T041–T065)

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T041 | Implementacja headers.py — UA pool (10 realnych Chrome/FF/Edge 2024-2026) | HIGH | 20m |
| T042 | Implementacja headers.py — full Chrome header set (Accept, Sec-*, etc.) | HIGH | 15m |
| T043 | Implementacja stealth.py — block detection (CF patterns, 403, 429, captcha) | HIGH | 30m |
| T044 | Implementacja stealth.py — Layer 1: httpx direct + Chrome headers | HIGH | 20m |
| T045 | Implementacja stealth.py — Layer 2: UA rotation (sample from pool) | HIGH | 15m |
| T046 | Implementacja stealth.py — Layer 3: curl_cffi TLS (chrome131 target) | HIGH | 30m |
| T047 | Implementacja stealth.py — Layer 4: primp Rust TLS (chrome_131) | MED | 25m |
| T048 | Implementacja stealth.py — Layer 5: nodriver CDP headless | HIGH | 40m |
| T049 | Implementacja stealth.py — Layer 6: patchright stealth Playwright | HIGH | 40m |
| T050 | Implementacja stealth.py — Layer 7: Jina relay (r.jina.ai/{url}) | MED | 15m |
| T051 | Implementacja stealth.py — Layer 8: skip + log exhaustion | LOW | 10m |
| T052 | Implementacja stealth.py — fetch_with_stealth() orchestrator z eskalacją | HIGH | 30m |
| T053 | Implementacja stealth.py — PortalConfig dataclass (start_layer, use_tor, timeout) | HIGH | 15m |
| T054 | Implementacja tor_manager.py — find_tor_binary (Linux/Windows path) | HIGH | 15m |
| T055 | Implementacja tor_manager.py — start_tor_process() z ControlPort | HIGH | 25m |
| T056 | Implementacja tor_manager.py — stop_tor_process() graceful shutdown | MED | 10m |
| T057 | Implementacja tor_manager.py — health_check() SOCKS5 connectivity | HIGH | 15m |
| T058 | Implementacja tor_manager.py — new_circuit() via stem NEWNYM | HIGH | 20m |
| T059 | Implementacja tor_manager.py — new_circuit() fallback via raw TCP ControlPort | MED | 20m |
| T060 | Test LIVE: Layer 1 → httpbin.org (verify headers sent) | HIGH | 10m |
| T061 | Test LIVE: Layer 3 → curl_cffi na stronę z Cloudflare (check TLS fingerprint) | HIGH | 15m |
| T062 | Test LIVE: Tor circuit renewal — 3 requests, verify 3 different exit IPs | HIGH | 15m |
| T063 | Test LIVE: nodriver → otwarcie strony z CF challenge | HIGH | 20m |
| T064 | Test LIVE: patchright → otwarcie strony z JS challenge | HIGH | 20m |
| T065 | Implementacja retry.py — @async_retry decorator (exp backoff, jitter, max 3) | MED | 15m |

---

## FAZA 4: Portal Scrapers — Tier 1 / EASY (T066–T095)

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T066 | Implementacja base.py — RawListing finalizacja (all fields, __hash__) | HIGH | 15m |
| T067 | Implementacja base.py — BaseScraper ABC z search/parse/portal_name | HIGH | 10m |
| T068 | **MORIZON** — implementacja search(): URL builder (?q= + pagination) | HIGH | 20m |
| T069 | MORIZON — implementacja parse_listing(): .property-card selectors | HIGH | 25m |
| T070 | MORIZON — extraction: title, price, location, area, rooms, URL | HIGH | 20m |
| T071 | MORIZON — pagination: detect total pages, iterate | MED | 15m |
| T072 | MORIZON — share_fraction extraction z tytułu (regex) | MED | 10m |
| T073 | Test LIVE: Morizon search "udział" → parsuje ≥5 wyników | HIGH | 15m |
| T074 | Test LIVE: Morizon pagination — page 1 + page 2 różne wyniki | MED | 10m |
| T075 | **GRATKA** — implementacja search(): URL builder (?fraza= + pagination) | HIGH | 20m |
| T076 | GRATKA — implementacja parse_listing(): selectors (ta sama firma co Morizon) | HIGH | 20m |
| T077 | GRATKA — extraction: title, price, location, area, URL | HIGH | 15m |
| T078 | GRATKA — pagination detection + iteration | MED | 15m |
| T079 | Test LIVE: Gratka search "udział w nieruchomości" → parsuje wyniki | HIGH | 15m |
| T080 | **DOMIPORTA** — implementacja search(): URL (?KeyWords= + params) | HIGH | 20m |
| T081 | DOMIPORTA — parse: article.sneakpeak, h2.sneakpeak__title--bold | HIGH | 25m |
| T082 | DOMIPORTA — extraction: title, price, area, rooms, detail URL | HIGH | 15m |
| T083 | DOMIPORTA — pagination: .pagination__pages links | MED | 15m |
| T084 | Test LIVE: Domiporta search "udział" → parsuje ≥3 wyników | HIGH | 15m |
| T085 | **NIERUCHOMOSCI-ONLINE** — strategia: brak keyword search → scrape listing page | HIGH | 15m |
| T086 | N-ONLINE — implementacja: iterate listing pages, fetch detail, grep body | HIGH | 30m |
| T087 | N-ONLINE — parse: div.tile.tile-tile, h2.name > a, p.primary-display | HIGH | 20m |
| T088 | N-ONLINE — detail page fetch + body text scan for "udział" keywords | HIGH | 20m |
| T089 | Test LIVE: N-Online → scrape 20 listings, filter by keyword w body | HIGH | 20m |
| T090 | Tier 1 integration: ScraperManager.search_all() z 4 scraperami | HIGH | 25m |
| T091 | Test: parallel gather() 4 portali, deduplikacja wyników | HIGH | 15m |
| T092 | Test: timeout handling — jeden portal timeout → rest kontynuuje | MED | 10m |
| T093 | Test: progress callback fires per-portal completion | MED | 10m |
| T094 | Error handling: HTTPError, TimeoutError, ParseError → graceful skip | HIGH | 20m |
| T095 | Logging: per-portal stats (found, parsed, errors, elapsed_ms) | MED | 15m |

---

## FAZA 5: Portal Scrapers — Tier 2 / Tor + TLS (T096–T125)

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T096 | **OLX** — recon: curl_cffi chrome131 + Tor → check if passes CloudFront | HIGH | 20m |
| T097 | OLX — search URL builder: /nieruchomosci/q-{keyword}/?page={n} | HIGH | 15m |
| T098 | OLX — parse __NEXT_DATA__: extract JSON blob from HTML | HIGH | 30m |
| T099 | OLX — extract listings from __NEXT_DATA__ JSON structure | HIGH | 30m |
| T100 | OLX — handle variant: JSON ads array → title, price, location, url | HIGH | 25m |
| T101 | OLX — pagination: detect totalPages from JSON, iterate | MED | 15m |
| T102 | OLX — location extraction: city, region from params | MED | 15m |
| T103 | OLX — circuit renewal between pages (avoid rate limiting) | MED | 15m |
| T104 | Test LIVE: OLX via curl_cffi+Tor → get 200, extract listings | HIGH | 20m |
| T105 | Test: OLX fallback Layer 3→4 (primp) if cffi blocked | MED | 15m |
| T106 | **OTODOM** — recon: curl_cffi + Tor → check CloudFront bypass | HIGH | 20m |
| T107 | OTODOM — search URL builder: /pl/wyniki/sprzedaz/?search[description]= | HIGH | 15m |
| T108 | OTODOM — parse __NEXT_DATA__: extract searchResults JSON | HIGH | 30m |
| T109 | OTODOM — extract: title, price, area, rooms, location, URL from JSON | HIGH | 25m |
| T110 | OTODOM — pagination from __NEXT_DATA__ (totalPages/currentPage) | MED | 15m |
| T111 | OTODOM — geo coords extraction (if available in JSON) | LOW | 10m |
| T112 | Test LIVE: Otodom via Tor → search "udział" → extract listings | HIGH | 20m |
| T113 | **OLX+OTODOM** — dedup cross-portal (same listing on both) | HIGH | 20m |
| T114 | OLX — rate limiting strategy: 3-5s delay, circuit renewal per page batch | HIGH | 15m |
| T115 | OTODOM — rate limiting: 3-5s delay, check for soft blocks (redirect) | HIGH | 15m |
| T116 | Tier 2 integration: add OLX+Otodom to ScraperManager | HIGH | 15m |
| T117 | Test: ScraperManager z 6 portalami (4 Tier1 + 2 Tier2) parallel | HIGH | 20m |
| T118 | Test: Tor failure graceful — jeśli Tor down → skip Tier2, run Tier1 only | HIGH | 15m |
| T119 | Circuit management: new circuit before each Tier2 portal | MED | 10m |
| T120 | OLX — handle promoted/sponsored listings (exclude or flag) | LOW | 10m |
| T121 | OTODOM — handle developer listings (exclude primary market) | LOW | 10m |
| T122 | OLX error recovery: 403 → new circuit → retry once | HIGH | 15m |
| T123 | OTODOM error recovery: redirect to /login → skip, log | MED | 10m |
| T124 | Test: full Tier2 scraping session — 12 queries × 2 portals × Tor | HIGH | 20m |
| T125 | Performance benchmark: time per portal, avg results per query | MED | 15m |

---

## FAZA 6: Portal Scrapers — Tier 3 / Headless + API (T126–T155)

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T126 | **TROJMIASTO** — recon: nodriver + Tor → check CF Turnstile bypass | HIGH | 25m |
| T127 | TROJMIASTO — search URL: ogloszenia.trojmiasto.pl/nieruchomosci-sprzedam/?q= | HIGH | 15m |
| T128 | TROJMIASTO — nodriver navigation: wait for CF challenge pass | HIGH | 20m |
| T129 | TROJMIASTO — parse listing page: extract selectors (post-challenge HTML) | HIGH | 30m |
| T130 | TROJMIASTO — extract: title, price, location, URL from listings | HIGH | 20m |
| T131 | TROJMIASTO — fallback Layer 6 (patchright) if nodriver blocked | HIGH | 20m |
| T132 | Test LIVE: Trojmiasto via nodriver+Tor → CF challenge passes → HTML | HIGH | 20m |
| T133 | **SZYBKO** — recon: nodriver/patchright + Tor → CF bypass test | HIGH | 25m |
| T134 | SZYBKO — discover search URL structure (post-CF content analysis) | HIGH | 20m |
| T135 | SZYBKO — implement scraper: navigation + wait + parse | HIGH | 30m |
| T136 | SZYBKO — extract listings: title, price, location, URL | HIGH | 20m |
| T137 | Test LIVE: Szybko via patchright+Tor → extract listings | HIGH | 20m |
| T138 | **ALLEGRO** — register OAuth2 app (developer.allegro.pl) | HIGH | 15m |
| T139 | ALLEGRO — implement auth flow: client_credentials grant | HIGH | 20m |
| T140 | ALLEGRO — search endpoint: GET /offers/listing?category= + phrase= | HIGH | 25m |
| T141 | ALLEGRO — parse API response: items[].name, price, location, url | HIGH | 20m |
| T142 | ALLEGRO — pagination: offset/limit in API params | MED | 10m |
| T143 | ALLEGRO — category filter: nieruchomości category ID | MED | 15m |
| T144 | Test LIVE: Allegro API → search "udział nieruchomość" → JSON results | HIGH | 15m |
| T145 | Tier 3 integration: add 4 portali do ScraperManager | HIGH | 15m |
| T146 | Test: full 9-portal search session (Tier 1+2+3) | HIGH | 25m |
| T147 | Performance: headless browser lifecycle (launch once, reuse context) | HIGH | 20m |
| T148 | Resource management: close browser po każdym search batch | HIGH | 15m |
| T149 | Test: memory usage po 9-portal search (target <500MB peak) | MED | 15m |
| T150 | Timeout enforcement: 20s per portal, 120s total search | HIGH | 10m |
| T151 | Portal status reporting: per-portal success/fail/timeout/blocked stats | MED | 15m |
| T152 | Graceful degradation: if all Tier3 fail → report, continue with Tier1+2 | HIGH | 10m |
| T153 | Browser stealth: disable webdriver flag, navigator.plugins mock | MED | 15m |
| T154 | Cookie handling: persist cookies per portal across searches | MED | 20m |
| T155 | Anti-fingerprint: randomize viewport, timezone, language per session | LOW | 20m |

---

## FAZA 7: Detection Engine (T156–T175)

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T156 | Implementacja keywords.py — HIGH_CONFIDENCE patterns (regex, diacritics) | HIGH | 25m |
| T157 | Implementacja keywords.py — MEDIUM/LOW_CONFIDENCE patterns | HIGH | 15m |
| T158 | Implementacja keywords.py — NEGATIVE patterns (false positives) | HIGH | 20m |
| T159 | Implementacja keywords.py — FRACTION_PATTERNS regex (1/2..3/4) | HIGH | 15m |
| T160 | Implementacja keywords.py — SEARCH_QUERIES (12 zapytań do portali) | MED | 10m |
| T161 | Implementacja scorer.py — normalize_text() (lowercase + diacritics handling) | HIGH | 15m |
| T162 | Implementacja scorer.py — title scoring (+35 max, tiered keywords) | HIGH | 25m |
| T163 | Implementacja scorer.py — description scoring (+25 max) | HIGH | 20m |
| T164 | Implementacja scorer.py — fraction detection (+15) | HIGH | 15m |
| T165 | Implementacja scorer.py — inheritance context (+10: spadek, dział, KW) | MED | 15m |
| T166 | Implementacja scorer.py — price anomaly (+8: niska cena/m²) | MED | 20m |
| T167 | Implementacja scorer.py — negative penalties (-15 to -35 per pattern) | HIGH | 20m |
| T168 | Implementacja scorer.py — ScoringResult aggregation (clamp 0-100) | HIGH | 10m |
| T169 | Test: 10 true positives (real ogłoszenia o udziałach) → score ≥60 | HIGH | 25m |
| T170 | Test: 10 false positives (normalne mieszkania z "udział w gruncie") → score <50 | HIGH | 25m |
| T171 | Test: missing diacritics ("udzial 1/2 mieszkanie") → still detects | HIGH | 10m |
| T172 | Test: edge cases (udział w spółce, udział własny kredyt) → rejected | HIGH | 15m |
| T173 | Implementacja filters.py — filter_by_score (apply scorer, return sorted) | HIGH | 15m |
| T174 | Implementacja filters.py — filter_by_location (voivodeship + haversine) | HIGH | 20m |
| T175 | Implementacja filters.py — filter_by_price (min/max PLN) | MED | 10m |

---

## FAZA 8: Telegram Bot (T176–T200)

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T176 | Utworzenie Telegram bota (@BotFather), uzyskanie tokena | HIGH | 5m |
| T177 | Implementacja main.py — Dispatcher + Bot + polling start | HIGH | 20m |
| T178 | Implementacja main.py — lifespan hooks (DB init, Tor start on startup) | HIGH | 15m |
| T179 | Implementacja main.py — graceful shutdown (Tor stop, DB close) | MED | 10m |
| T180 | Implementacja routers/search.py — /start welcome + owner check | HIGH | 20m |
| T181 | Implementacja routers/search.py — /search trigger → run ScraperManager | HIGH | 30m |
| T182 | Implementacja routers/search.py — progress updates (edit_message per portal) | HIGH | 20m |
| T183 | Implementacja routers/search.py — results summary + pass to pagination | HIGH | 15m |
| T184 | Implementacja routers/results.py — inline pagination (5/page, ◀️▶️) | HIGH | 30m |
| T185 | Implementacja routers/results.py — listing detail view (full info + link) | HIGH | 20m |
| T186 | Implementacja routers/results.py — save/hide actions (callback buttons) | MED | 20m |
| T187 | Implementacja routers/filters.py — FSM: voivodeship select (inline kbd) | HIGH | 25m |
| T188 | Implementacja routers/filters.py — FSM: city input (text autocomplete) | HIGH | 25m |
| T189 | Implementacja routers/filters.py — FSM: radius slider (5-100km, inline) | HIGH | 20m |
| T190 | Implementacja routers/filters.py — FSM: price range (optional) | MED | 15m |
| T191 | Implementacja routers/filters.py — FSM: portals on/off toggle | MED | 20m |
| T192 | Implementacja routers/filters.py — save filter preset | MED | 15m |
| T193 | Implementacja routers/saved.py — /saved command + pagination | MED | 20m |
| T194 | Implementacja routers/saved.py — delete saved listing | LOW | 10m |
| T195 | Implementacja keyboards/reply.py — main menu (🔍 Szukaj, ⚙️ Filtry, 📋 Zapisane, ❓ Pomoc) | HIGH | 10m |
| T196 | Implementacja keyboards/inline.py — pagination builder | HIGH | 15m |
| T197 | Implementacja middlewares/throttle.py — rate limit (max 1 search/30s) | MED | 15m |
| T198 | Test E2E: /start → /search → wyniki → pagination → save → /saved | HIGH | 30m |
| T199 | Test E2E: /start → filters FSM → set woj+city+radius → /search z filtrami | HIGH | 25m |
| T200 | Test: owner-only check (unauthorized user → rejected message) | HIGH | 10m |

---

## FAZA 9: Integration & E2E Testing (T201–T215) [BONUS]

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T201 | Full pipeline test: Tor start → 9 portali → scorer → DB → Telegram msg | HIGH | 30m |
| T202 | Stress test: 12 keywords × 9 portali (108 requests) — timing + errors | HIGH | 25m |
| T203 | Dedup test: same listing on Morizon+Gratka → appears once | HIGH | 15m |
| T204 | Empty results test: search z nierealistycznym keyword → graceful "brak wyników" | MED | 10m |
| T205 | Tor failure test: kill tor → bot reports "Tor niedostępny" → Tier1 still works | HIGH | 15m |
| T206 | Portal down test: mock timeout na 3 portale → rest returns results | MED | 15m |
| T207 | Scorer calibration: 50 real listings (25 share + 25 normal) → F1 score report | HIGH | 30m |
| T208 | Memory leak check: 10 consecutive searches → RSS stable | MED | 15m |
| T209 | Browser cleanup: after headless sessions → no zombie chromium processes | HIGH | 10m |
| T210 | SQLite integrity: concurrent search + save → no corruption | MED | 15m |
| T211 | Config hot-reload test: zmiana portals on/off → natychmiast respektowane | LOW | 15m |
| T212 | Telegram message formatting: verify markdown parse mode, link clickable | MED | 10m |
| T213 | Long listing title: truncation + "..." w Telegram (max 4096 chars/msg) | MED | 10m |
| T214 | Unicode handling: Polish chars w tytułach, emoji w buttons | LOW | 5m |
| T215 | Error reporting: unhandled exception → user gets "Wystąpił błąd" + log | HIGH | 15m |

---

## FAZA 10: Windows Packaging & Delivery (T216–T230) [BONUS]

| # | Task | Priorytet | Est. |
|---|------|-----------|------|
| T216 | install.bat — download Python embedded (3.11, x64) | HIGH | 20m |
| T217 | install.bat — create venv, install requirements | HIGH | 15m |
| T218 | install.bat — download Tor Expert Bundle (portable) | HIGH | 15m |
| T219 | install.bat — patchright install (chromium browser binary) | HIGH | 15m |
| T220 | install.bat — nodriver setup (chromium via chrome-for-testing) | HIGH | 15m |
| T221 | install.bat — create config.yaml from user input (TG token prompt) | HIGH | 20m |
| T222 | start_bot.bat — start Tor in background → wait for SOCKS5 ready | HIGH | 15m |
| T223 | start_bot.bat — activate venv → python -m bot.main | HIGH | 5m |
| T224 | stop_bot.bat — graceful kill bot + tor processes | MED | 10m |
| T225 | Test na Windows VM: fresh install → install.bat → start_bot.bat → działa | HIGH | 45m |
| T226 | README.md — screenshots Telegram flow (search, results, filters) | MED | 20m |
| T227 | README.md — troubleshooting (Tor blocked, portal changes, antivirus) | MED | 15m |
| T228 | Pakowanie: zip release (exclude .git, __pycache__, .env) | HIGH | 10m |
| T229 | Versioning: tag v1.0.0 na GitHub | LOW | 5m |
| T230 | Delivery: wysłanie ZIP + instrukcja do klienta (email/Telegram) | HIGH | 10m |

---

## PODSUMOWANIE

| Faza | Taski | Szacunek czasu |
|------|-------|----------------|
| 1. Environment | T001–T020 | 2.5h |
| 2. Core Infrastructure | T021–T040 | 5h |
| 3. Stealth Engine | T041–T065 | 7h |
| 4. Tier 1 Scrapers | T066–T095 | 7h |
| 5. Tier 2 Scrapers (Tor) | T096–T125 | 6h |
| 6. Tier 3 Scrapers (Headless) | T126–T155 | 7h |
| 7. Detection Engine | T156–T175 | 5h |
| 8. Telegram Bot | T176–T200 | 6.5h |
| 9. Integration E2E | T201–T215 | 4h |
| 10. Windows Packaging | T216–T230 | 4h |
| **TOTAL** | **230 tasków** | **~54h** |

---

## ŚCIEŻKA KRYTYCZNA

```
T001-T020 (env) 
  → T041-T065 (stealth engine)
    → T066-T095 (Tier 1 scrapers + LIVE test)
      → T096-T125 (Tier 2 + Tor)
        → T126-T155 (Tier 3 + headless)
  → T021-T040 (DB + geo)
    → T156-T175 (detector/scorer)
      → T176-T200 (Telegram bot)
        → T201-T215 (E2E integration)
          → T216-T230 (Windows packaging + delivery)
```

**Parallelizm:** Fazy 2+3 mogą iść równolegle. Fazy 4-6 sekwencyjne (Tier escalation). Faza 7 niezależna (może iść z 4-6 parallel).

---

## RYZYKA

| Ryzyko | Impact | Prawdop. | Mitigacja |
|--------|--------|----------|-----------|
| OLX/Otodom blokuje curl_cffi+Tor | HIGH | 30% | Layer 5-6 fallback (nodriver/patchright) |
| Trojmiasto CF Turnstile odporna na nodriver | MED | 40% | patchright Layer 6, Jina Layer 7, lub skip |
| Allegro OAuth2 rejection (bot use) | LOW | 20% | Scraping via patchright jako fallback |
| Selektory HTML zmienią się mid-project | LOW | 10% | Modular parsers, łatwa wymiana |
| Windows install issues (antivirus blocks Tor) | MED | 30% | Whitelist instructions w README |
| primp wheel niedostępny na Windows | LOW | 20% | Skip Layer 4, go direct 3→5 |
| Total dev >54h (budżet strain) | MED | 50% | Prioritize Tier1+2 (5 portali), Tier3 optional |

---

## MVP CUT (jeśli budżet napięty)

**Minimum viable za 2000 PLN (~24h):**
- Fazy 1-2 + Faza 3 (Layers 1-4 only) + Faza 4 (Tier 1: 4 portale) + Faza 5 (OLX via Tor) + Faza 7 + Faza 8 + Faza 10
- = 5 portali (Morizon, Gratka, Domiporta, N-Online, OLX) + Telegram + Windows
- Skip: Otodom, Trojmiasto, Szybko, Allegro (add post-MVP)
