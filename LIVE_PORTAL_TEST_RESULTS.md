# LIVE Portal Scraping Test Results

**Date:** 2026-08-22
**Test Method:** Raw HTTP requests (httpx for Tier1, curl_cffi for Tier2)
**Purpose:** Verify scraping feasibility before implementing full scraper logic

---

## Summary Table

| Portal | HTTP Status | Content Delivered | Keyword Filter Works | Listings Parsed | Scraping Method |
|--------|------------|-------------------|---------------------|-----------------|-----------------|
| **Morizon** | ✅ 200 | ✅ Full HTML (830KB) | ❌ `?q=udział` ignored | ✅ 74 offers | httpx + Chrome UA |
| **Gratka** | ✅ 200 | ✅ Full HTML (845KB) | ❌ `?fraza=udział` ignored | ✅ 32 listings | httpx + Chrome UA |
| **Domiporta** | ✅ 200 | ✅ Full HTML (435KB) | ⚠️ Partial (1 match) | ✅ 76 listings | httpx + Chrome UA |
| **OLX** | ✅ 200 | ✅ Full HTML (3.7MB) | ✅ 18/52 cards relevant | ✅ 52 cards | curl_cffi chrome131 + Tor |
| **Otodom** | ⚠️ 200 (direct) / ❌ 403 (Tor) | ✅ via curl_cffi direct | ❌ description param stripped | ✅ 37 items via JSON | curl_cffi chrome131 (NO Tor) |

---

## Detailed Results Per Portal

### 1. MORIZON ✅ WORKS (Tier 1 - httpx)

**URL:** `https://www.morizon.pl/mieszkania/?q=udział`
**Status:** HTTP 200
**Body Size:** 830,221 bytes
**Blocked:** NO (Cloudflare reference is just a CDN script, not a challenge)

**Content Verification:**
- Page title: "Mieszkania na sprzedaż Polska | Morizon.pl"
- 96,990 total listings returned
- 74 offer links (`a[href*="/oferta/"]`)
- 186 price references (zł)
- JSON-LD structured data present (Product, BreadcrumbList)

**Search Filter Issue:** ⚠️ The `?q=udział` parameter is **completely ignored** server-side.
- Canonical URL: `https://www.morizon.pl/mieszkania/` (no search param)
- Zero occurrences of "udział" in page content
- Returns generic all-listings page

**Sample Extracted Listings:**
```
Title: mieszkanie 61.5 m² Targówek, metro, możliwy kredyt
Price: 860 000 zł
URL: https://www.morizon.pl/oferta/sprzedaz-mieszkanie-warszawa-targowek-smolenska-61m2-mzn2047326476

Title: Mieszkanie BEZPOŚREDNIO, 3 pokoje, 49,11 m2 Warszawa
Price: 950 000 zł
URL: https://www.morizon.pl/oferta/sprzedaz-mieszkanie-warszawa-srodmiescie-aleja-solidarnosci-49m2-mzn2047...

Title: Luksusowe z tarasem 20 m² + miejsce postojowe
Price: 670 000 zł
URL: https://www.morizon.pl/oferta/sprzedaz-mieszkanie-limanowski-mszana-dolna-38m2-mzn2047711372
```

**Parsing Method:** BeautifulSoup → `a[href*="/oferta/"]` + regex price extraction
**Verdict:** ✅ Scraping works perfectly. Need to find correct search/filter URL (may need API or different parameter name).

---

### 2. GRATKA ✅ WORKS (Tier 1 - httpx)

**URL:** `https://gratka.pl/nieruchomosci/mieszkania?fraza=udział`
**Status:** HTTP 200
**Body Size:** 845,023 bytes
**Blocked:** NO (Cloudflare reference is just a partner link in footer)

**Content Verification:**
- Page title: "Mieszkania na sprzedaż | Ogłoszenia | Gratka"
- 72 direct listing links (`a[href*="/nieruchomosci/mieszkanie"]`)
- 193 price references (zł)

**Search Filter Issue:** ⚠️ The `?fraza=udział` parameter is **completely ignored**.
- Canonical URL: `https://gratka.pl/nieruchomosci/mieszkania` (no fraza param)
- Zero occurrences of "udział" in page content
- Returns generic listings page

**Sample Extracted Listings:**
```
Title: Jeżyce - duże mieszkanie - dla miłośników kamienic 101 m²
Price: 1 250 000 zł
URL: https://gratka.pl/nieruchomosci/mieszkanie-poznan-jezyce-jana-kochanowskiego/ob/48543099

Title: Luksusowe z tarasem 20 m² + miejsce postojowe 38 m²
Price: 670 000 zł
URL: https://gratka.pl/nieruchomosci/mieszkanie-limanowski-mszana-dolna/ob/48069209

Title: DO ZAMIESZKANIA W OS. KALINOWYM 36 m²
Price: 515 000 zł
URL: https://gratka.pl/nieruchomosci/mieszkanie-krakow-bienczyce-kalinowe/ob/40144717
```

**Parsing Method:** BeautifulSoup → `a[href*="/nieruchomosci/mieszkanie"][href*="/ob/"]` + regex
**Verdict:** ✅ Scraping works. Search parameter needs investigation — may require different URL pattern or API endpoint.

---

### 3. DOMIPORTA ✅ WORKS (Tier 1 - httpx)

**URL:** `https://www.domiporta.pl/mieszkanie/sprzedam?KeyWords=udział`
**Status:** HTTP 200
**Body Size:** 434,770 bytes
**Blocked:** NO (reCAPTCHA exists but for "alert subscription" widget, NOT blocking page content)

**Content Verification:**
- Page title: "Mieszkania na sprzedaż - Domiporta.pl"
- "Znaleziono 805 ogłoszeń"
- 76 listing links (`a[href*="/nieruchomosci/sprzedam-mieszkanie"]`)
- 81 price references (zł)
- 4 occurrences of "udział" in page

**Search Filter:** ⚠️ Partially works — found 1 listing explicitly mentioning "udział":
```
Title: Polecam udział w 2-pokojowym mieszkaniu na Mokotowie
URL: https://www.domiporta.pl/nieruchomosci/sprzedam-mieszkanie-dwupokojowe-warszawa-mokotow-jadzwingow-36m2/156379122
```
- Canonical URL strips the KeyWords param but results DO include some udział content
- Most results are generic (805 total, only 1 with explicit "udział")

**Sample Extracted Listings:**
```
Title: Polecam dwupoziomowe 4 pokoje z tarasem i parkingiem w Gdyni
Price: 1 099 000 zł (72 m², 4 pokoje)
URL: https://www.domiporta.pl/nieruchomosci/sprzedam-mieszkanie-czteropokojowe-gdynia-chwarzno-wiczlino...

Title: Przestronne 119 m² z kominkiem i 3 sypialniami polecam
Price: ~460 000 zł (119 m²)
URL: https://www.domiporta.pl/nieruchomosci/sprzedam-mieszkanie-czteropokojowe-walbrzych-119m2/1565...

Title: Polecam udział w 2-pokojowym mieszkaniu na Mokotowie
Price: (in listing)
URL: https://www.domiporta.pl/nieruchomosci/sprzedam-mieszkanie-dwupokojowe-warszawa-mokotow-jadzwingow-36m2/156379122
```

**Parsing Method:** BeautifulSoup → `a[href*="/nieruchomosci/sprzedam-mieszkanie"]` + text extraction
**Verdict:** ✅ Scraping works well. KeyWords param has weak filtering but content is accessible.

---

### 4. OLX ✅ WORKS EXCELLENTLY (Tier 2 - curl_cffi + Tor)

**URL:** `https://www.olx.pl/nieruchomosci/q-udział/`
**Status:** HTTP 200
**Body Size:** 3,755,354 bytes (3.7MB)
**Blocked:** NO (captcha keyword in script metadata, not actual block)
**Proxy:** socks5://127.0.0.1:9050 (Tor) ✅ Works

**Content Verification:**
- Page title: "udział w Twojej okolicy? Sprawdź kategorię Nieruchomości"
- 268 occurrences of "udział" — SEARCH ACTUALLY FILTERS!
- 52 listing cards (`[data-cy="l-card"]`)
- 104 offer links
- 427 price references (zł)

**Search Filter:** ✅ WORKS PERFECTLY — OLX path-based search (`/q-udział/`) actually filters results.
- 18 out of 52 cards explicitly contain "udział" in title/text
- Rest are related (nieruchomości category context)

**Sample Extracted Listings (RELEVANT):**
```
Title: Syndyk sprzeda prawo własności ½ udziałów w nieruchomości lokalowej o funkcji mi...
Price: 82 400 zł
URL: https://www.olx.pl/d/oferta/syndyk-sprzeda-prawo-wlasnosci-udzialow-w-nieruchomosci-lokalowej-o-fu...

Title: Syndyk sprzeda udział 1/12 Tyczyn
Price: 2 936,80 zł
URL: https://www.olx.pl/d/oferta/syndyk-sprzeda-udzial-1-12-tyczyn-CID3-ID1aNQ1s.html

Title: Rezerwacja  Kuzawa – Dom Z Czerwonej Cegły, Rzeka Udział 1/2
Price: 116 000 zł
URL: https://www.olx.pl/d/oferta/...

Title: Zelewo - działki z WZ Udział w drodze w cenie!
Price: 200 550 zł
URL: https://www.olx.pl/d/oferta/...
```

**Parsing Method:** BeautifulSoup → `[data-cy="l-card"]` → h4/h6 (title), `[data-testid="ad-price"]` (price), `a[href*="/d/oferta/"]` (URL)
**Verdict:** ✅ BEST portal for scraping. curl_cffi+Tor works flawlessly. Rich, relevant results with udział/syndyk content.

---

### 5. OTODOM ⚠️ PARTIALLY WORKS (Tier 2 - curl_cffi, NO Tor)

**URL:** `https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska?search%5Bdescription%5D=udział`
**Status:**
- ❌ HTTP 403 via Tor proxy (CloudFront WAF blocks Tor exit nodes)
- ✅ HTTP 200 via curl_cffi direct (no proxy)
**Body Size:** 1,305,672 bytes (when not blocked)
**Blocked:** YES with Tor → CloudFront 403 ("Request blocked. Generated by cloudfront")

**Content Verification (direct connection):**
- Page title: "Mieszkania na sprzedaż: w całej Polsce | Otodom.pl"
- 37 listing items in `__NEXT_DATA__` JSON
- Rich structured data (price, area, rooms, slug, location)
- Next.js app with server-side rendering

**Search Filter Issue:** ⚠️ `search[description]=udział` parameter is **stripped server-side**.
- `filteringQueryParams` shows: `{'page': 1, 'limit': 36, 'market': 'ALL', 'ownerTypeSingleSelect': 'ALL', 'locations': []}`
- No description/freetext filter applied
- Returns generic listings (none mention "udział" in titles)
- Tested `?q=`, `?search[freetext]=`, `?search[description]=` — all ignored

**Sample Extracted Listings (generic, not filtered):**
```
Title: PARKING W CENIE|2 pokoje od wschodu|Ostania sztuka!|Bezpośrednio
Price: {'value': 338728, 'currency': 'PLN'}
URL: https://www.otodom.pl/pl/oferta/parking-w-cenie-2-pokoje-od-wschodu-ostania-sztuka-bezposrednio-ID4CKh6-68339692

Title: 3 pokoje, 1 łazienka, balkon, garaż do wprowadzenia!
Price: {'value': 1282500, 'currency': 'PLN'}
URL: https://www.otodom.pl/pl/oferta/3-pokoje-1-lazienka-balkon-garaz-do-wprowadzenia-ID4CKh1-68339687

Title: ✓✓ 48m2, 2-str. 3 pok., BALKON z WIDOKIEM, piw. 1,5m2 I BEZ PROWIZJI ✓
Price: {'value': 623856, 'currency': 'PLN'}
URL: https://www.otodom.pl/pl/oferta/48m2-2-str-3-pok-balkon-z-widokiem-piw-1-5m2-i-bez-prowizji-ID4AHyg-67852568
```

**Parsing Method:** `__NEXT_DATA__` JSON → `props.pageProps.data.searchAds.items[]` (structured: title, totalPrice, slug, id, location, area, rooms)
**Verdict:** ⚠️ Scraping structure works perfectly via JSON, but:
1. **Tor is blocked** — must use direct IP or residential proxies
2. **Description search param ignored** — needs investigation (possibly JS-only filter, GraphQL API, or different URL format)

---

## Key Findings & Recommendations

### What Works ✅
1. **All 5 portals return HTTP 200** (Otodom only without Tor)
2. **All portals deliver full listing HTML/JSON** — no actual content blocking
3. **OLX is the best source** — search works, many udział/syndyk results, Tor OK
4. **Structured parsing is straightforward** — CSS selectors, JSON-LD, __NEXT_DATA__

### Issues Found ⚠️

| Issue | Portals Affected | Severity | Suggested Fix |
|-------|-----------------|----------|---------------|
| Search/keyword parameter ignored | Morizon, Gratka, Otodom | HIGH | Need to find correct API/URL for text search; may need to scrape ALL listings and filter client-side, or find hidden API endpoints |
| Tor exit nodes blocked | Otodom | MEDIUM | Use curl_cffi WITHOUT Tor for Otodom; or use residential proxy |
| "captcha" false positive in detection | OLX, Domiporta | LOW | Don't flag based on keyword alone — check for actual block indicators (short page, no listings, specific challenge HTML) |

### Stealth Layer Recommendations

| Portal | Current Approach | Works? | Upgrade Needed |
|--------|-----------------|--------|----------------|
| Morizon | httpx + Chrome UA | ✅ Yes | None for access; need search API |
| Gratka | httpx + Chrome UA | ✅ Yes | None for access; need search API |
| Domiporta | httpx + Chrome UA | ✅ Yes | None |
| OLX | curl_cffi + Tor | ✅ Yes | None — working perfectly |
| Otodom | curl_cffi (direct) | ✅ Yes | Remove Tor for this portal; investigate GraphQL/description search endpoint |

### Next Steps
1. **OLX** — Ready for production scraping. Implement parser using `[data-cy="l-card"]` selectors.
2. **Otodom** — Ready for scraping via `__NEXT_DATA__` JSON. Must NOT use Tor. Need to find description search mechanism (likely internal API or browser JS interaction).
3. **Domiporta** — Ready for scraping. KeyWords param partially works.
4. **Morizon/Gratka** — Ready for HTML scraping but **search filtering needs separate investigation** (possibly SPA-only search, or need to scrape ALL pages and filter locally for "udział" keywords).
5. **All portals** — Consider scraping all listings and doing LOCAL keyword matching (`udział`, `syndyk`, `upadłość`, `licytacja`) rather than relying on portal search functionality.
