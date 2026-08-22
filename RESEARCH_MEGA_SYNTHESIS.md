# MEGA-SYNTEZA RESEARCHU — Bot "Udziały w Nieruchomościach"

## Klient
- **Marek Knapczyk**, MK, 81-326 Gdynia, Szczecińska 11/21, NIP 586-100-81-41
- **Budżet:** 2000 PLN netto (50/50)
- **Dostarczenie:** Telegram bot, lokalnie na Windows PC klienta
- **Bez umowy** — faktura

---

## 1. MATRYCA WYKONALNOŚCI PORTALI

| Portal | Trudność | Keyword Search | Anti-Bot | JS Required | Rating |
|--------|----------|---------------|----------|-------------|--------|
| **Domiporta.pl** | Easy | ✅ `KeyWords=` | Brak | Nie | **EASY** ✅ |
| **Morizon.pl** | Easy | ✅ `?q=` | Cloudflare (przepuszcza) | Nie | **EASY** ✅ |
| **Gratka.pl** | Easy | ✅ `?fraza=` | Cloudflare (przepuszcza) | Nie | **EASY** ✅ |
| **Allegro.pl** | Medium | ✅ via API | DataDome | Tak (scraping) | **MEDIUM** |
| **Nieruchomosci-online** | Medium | ❌ Brak text search | Brak | Nie | **MEDIUM** |
| **OLX.pl** | Hard | ✅ `/q-{keyword}/` | CloudFront WAF | Tak | **HARD** |
| **Otodom.pl** | Hard | ✅ description param | CloudFront WAF | Tak | **HARD** |
| **Trojmiasto.pl** | Hard | ? | Cloudflare Turnstile | Tak | **HARD** |
| **Szybko.pl** | Hard | ? | Cloudflare Turnstile | Tak | **HARD** |

### Kluczowy insight:
Bot działa na **Windows PC klienta = residential IP** → OLX/Otodom stają się bardziej wykonalne (WAF blokuje datacenter IPs, residential przepuszcza).

### Strategia portali (optymalna dla 2000 PLN):
**Tier 1 (Simple HTTP, requests + BS4):** Morizon, Gratka, Domiporta
**Tier 2 (Playwright + stealth):** OLX, Otodom (residential IP pomaga)
**Tier 3 (If time allows):** Nieruchomosci-online (scrape listing pages, filter locally), Allegro (API OAuth2)
**Tier 4 (Poza budżetem):** Trojmiasto, Szybko (Cloudflare Turnstile = captcha solver $$$)

---

## 2. ARCHITEKTURA BOTA

### Framework: **aiogram 3.x**
- Natywne asyncio, wbudowany FSM, router-based
- Lżejszy od python-telegram-bot, lepszy async support
- Popularne w PL community

### Scraping stack: **Hybrid**
- **httpx + selectolax** — szybkie async dla statycznych portali (Morizon, Gratka, Domiporta)
- **Playwright async** — dla JS-rendered (OLX, Otodom)
- **curl_cffi** opcjonalnie — Cloudflare bypass z impersonate

### Storage: **SQLite (aiosqlite)**
- UNIQUE constraints dla deduplikacji (source_url)
- SQL filtrowanie (voivodeship, city, radius)
- WAL mode dla concurrent access
- Pagination via LIMIT/OFFSET

### Packaging na Windows:
- **Embedded Python + .bat launcher** (PyInstaller niekompatybilny z Playwright)
- `install.bat` — instalacja zależności + Playwright browsers
- `start_bot.bat` — uruchomienie
- Total ~400MB (z Chromium dla Playwright)

### Async patterns:
- `asyncio.create_task()` dla background scraping
- `asyncio.gather()` — wszystkie portale jednocześnie
- Progress updates via `message.edit_text()`
- Per-portal timeout 15-20s z graceful skip
- 5 listingów/stronę w Telegram (inline keyboard pagination)

---

## 3. SYSTEM DETEKCJI UDZIAŁÓW

### Problem: needle-in-haystack
- **~3-8 ogłoszeń o udziałach na 1000 listingów** (0.3-0.8%)
- Strategia: **pre-filter via portal search** (NIE scrape-all)
- 12 zapytań × portale = ~150-300 HTTP requests → 100-500 kandydatów
- Full run: 5-15 minut

### Strategia wyszukiwania (portal search queries):
```
"udział w nieruchomości"
"sprzedaż udziału"  
"współwłasność"
"udział 1/2"
"udział 1/4"
"część nieruchomości"
"ułamek nieruchomości"
"udział w działce"
"udział w kamienicy"
"sprzedaż części"
"współwłaściciel sprzedaje"
"dział spadku"
```

### Scoring system (0-100):
| Signal | Max points |
|--------|-----------|
| Tytuł (frazy kluczowe) | 35 |
| Opis (patterns) | 25 |
| Ułamek wykryty (1/2, 1/4, etc.) | 15 |
| Kontekst spadkowy | 10 |
| Anomalia cenowa (niska cena/m²) | 8 |
| **Kary (false positives)** | **-35** |

**Próg:** score ≥ 50 → akceptacja (~70% precision, ~90% recall)

### False positives do odrzucenia:
1. "udział w gruncie pod budynkiem" — **STANDARD** w każdej sprzedaży mieszkania!
2. "wkład własny" / "udział własny" (kredyt hipoteczny)
3. "udziały w spółce" (corporate, nie nieruchomość)
4. "udział w drodze dojazdowej" (servitude)
5. "miejsce parkingowe — udział" (parking share)
6. "udział w częściach wspólnych" (standard w aktach)

### Podejście NLP:
- **Primary:** Regex + rules (wystarczające, zero overhead)
- **Secondary:** spaCy polish model (jeśli precision za niska)
- **LLM:** zbyt drogie na skalę (100-500 kandydatów/run)
- Challenge: polska morfologia (7 przypadków) + brakujące polskie znaki na OLX

---

## 4. STRUKTURA PROJEKTU (State of Art)

```
udzialy-bot/
├── README.md
├── install.bat                    # Windows installer
├── start_bot.bat                  # Launcher
├── requirements.txt
├── config.yaml                    # Token TG, portale on/off, timeouts
│
├── bot/
│   ├── __init__.py
│   ├── main.py                    # Entry point, dispatcher setup
│   ├── config.py                  # Pydantic settings
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── search.py              # /search, inline filters
│   │   ├── results.py             # Pagination, listing details
│   │   ├── filters.py             # FSM filter configuration
│   │   ├── saved.py               # Saved listings management
│   │   └── settings.py            # User preferences
│   ├── keyboards/
│   │   ├── __init__.py
│   │   ├── inline.py              # Inline keyboards (pagination, filters)
│   │   └── reply.py               # Reply keyboards (main menu)
│   └── middlewares/
│       └── throttle.py            # Anti-flood
│
├── scraper/
│   ├── __init__.py
│   ├── base.py                    # ABC: BaseScraper
│   ├── manager.py                 # Orchestrator (gather all portals)
│   ├── portals/
│   │   ├── __init__.py
│   │   ├── morizon.py             # Tier 1 - httpx
│   │   ├── gratka.py              # Tier 1 - httpx
│   │   ├── domiporta.py           # Tier 1 - httpx
│   │   ├── olx.py                 # Tier 2 - Playwright
│   │   ├── otodom.py              # Tier 2 - Playwright
│   │   ├── nieruchomosci_online.py # Tier 3
│   │   └── allegro.py             # Tier 3 - API
│   └── utils/
│       ├── headers.py             # User-Agent rotation
│       ├── proxy.py               # Proxy support (optional)
│       └── retry.py               # Retry with backoff
│
├── detector/
│   ├── __init__.py
│   ├── scorer.py                  # Share detection scoring
│   ├── keywords.py                # Keyword/regex patterns
│   └── filters.py                 # Post-scrape filtering
│
├── storage/
│   ├── __init__.py
│   ├── database.py                # SQLite schema + migrations
│   ├── models.py                  # Dataclasses/Pydantic models
│   └── queries.py                 # CRUD operations
│
├── geo/
│   ├── __init__.py
│   ├── cities.py                  # Polish cities geocoding cache
│   └── distance.py                # Haversine radius filter
│
└── tests/
    ├── test_scorer.py
    ├── test_scrapers.py
    └── fixtures/
        └── sample_listings.json
```

---

## 5. MODEL DANYCH (SQLite)

```sql
CREATE TABLE listings (
    id INTEGER PRIMARY KEY,
    source_url TEXT UNIQUE NOT NULL,
    portal TEXT NOT NULL,          -- 'morizon', 'olx', etc.
    title TEXT NOT NULL,
    description TEXT,
    price REAL,                    -- PLN, nullable
    share_fraction TEXT,           -- '1/2', '1/4', etc.
    voivodeship TEXT,
    city TEXT,
    latitude REAL,
    longitude REAL,
    confidence_score INTEGER,      -- 0-100
    is_active BOOLEAN DEFAULT 1,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    raw_data TEXT                   -- JSON blob
);

CREATE TABLE search_history (
    id INTEGER PRIMARY KEY,
    query TEXT,
    filters_json TEXT,
    results_count INTEGER,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE saved_listings (
    id INTEGER PRIMARY KEY,
    listing_id INTEGER REFERENCES listings(id),
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE user_filters (
    id INTEGER PRIMARY KEY,
    name TEXT,
    voivodeship TEXT,
    city TEXT,
    radius_km INTEGER,
    min_price REAL,
    max_price REAL,
    min_score INTEGER DEFAULT 50,
    portals_json TEXT              -- ["morizon","olx",...]
);
```

---

## 6. FLOW UŻYTKOWNIKA (Telegram)

```
/start → Menu główne (Reply Keyboard)
    🔍 Szukaj → Uruchamia scraping z aktywnymi filtrami
    ⚙️ Filtry → FSM: województwo → miasto → promień → cena → portale → zapisz
    📋 Zapisane → Lista saved listings z paginacją
    📊 Statystyki → Ile znaleziono, kiedy ostatni scan
    ❓ Pomoc → Instrukcja

Po "Szukaj":
    → "🔄 Szukam... (0/7 portali)" [edit_text updates]
    → "✅ Znaleziono 12 ogłoszeń o udziałach" [inline keyboard: ◀️ 1/3 ▶️]
    → Każdy wynik: Tytuł | Cena | Miasto | Score% | [🔗 Link] [💾 Zapisz]
```

---

## 7. HARMONOGRAM REALIZACJI (2000 PLN)

| Dzień | Zakres | Effort |
|-------|--------|--------|
| 1 | Scaffold + config + DB + scorer + Telegram skeleton | 4h |
| 2 | Tier 1 scrapers (Morizon + Gratka + Domiporta) | 4h |
| 3 | Tier 2 scrapers (OLX + Otodom via Playwright) | 5h |
| 4 | Geo filtering + inline keyboards + pagination | 3h |
| 5 | Saved listings + user filters FSM + polish | 3h |
| 6 | Windows packaging + install.bat + testing | 3h |
| 7 | Buffer / Tier 3 portals if time allows | 2h |

**Total: ~24h dev → przy stawce ~83 PLN/h**

---

## 8. RYZYKA I MITIGACJE

| Ryzyko | Prawdopodobieństwo | Mitigacja |
|--------|-------------------|-----------|
| OLX/Otodom blokuje mimo residential IP | Średnie | Playwright stealth + rate limiting 2-3s/req |
| Zmiana HTML selektorów | Pewne (co kilka mies.) | Modularny scraper, łatwa wymiana selektorów |
| Niska liczba wyników (0.3-0.8% match rate) | Pewne | Pre-filtering queries minimalizuje fałszywe wyniki |
| Playwright na Windows = duży rozmiar | Pewne | ~400MB, ale one-time install |
| Klient nie ogarnie instalacji | Średnie | install.bat fully automated + README z screenshotami |
| Portale zmienią anti-bot | Nisko-średnie | Tier 1 portale (Morizon/Gratka/Domiporta) stabilne |

---

## 9. REKOMENDACJA

**Realistyczny scope za 2000 PLN:**
- 5 portali (Morizon + Gratka + Domiporta + OLX + Otodom)
- Scoring ≥50 z regex rules (bez spaCy/LLM overhead)
- Telegram bot z pełnym flow (search/filters/saved/pagination)
- Windows installer (.bat)
- SQLite local storage
- Geo filtering (haversine, cache miast PL)

**Poza scope (dobrze zakomunikować klientowi):**
- Trojmiasto.pl, Szybko.pl (Cloudflare Turnstile = $$$ captcha solver)
- Allegro (wymaga OAuth2 app registration)
- Nieruchomosci-online (brak keyword search, trzeba scrape all + filter)
- Powiadomienia push (monitoring ciągły vs on-demand)
- Mapa / wizualizacja
