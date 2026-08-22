# DISCOVERY — Strategia Stealth dla Bota Udziałów

## Korekty po feedbacku Mateusza

### OLX + Otodom → Tor + Stealth Layers
- **Residential IP NIE jest potrzebne** — bot na kompie klienta + **Tor SOCKS5**
- Tor daje rotację IP exit nodes (każde request = nowy circuit/IP)
- Łączymy z 8-layer stealth z BeHive drones

### Trojmiasto + Szybko → Stealth Layers (NIE captcha solver)
- Cloudflare Turnstile → przejdziemy bez $$$ captcha solvera
- BeHive udowodnił: nodriver (Layer 5) przechodzi CF Bot Management
- patchright (Layer 6) = stealth Playwright bez CDP leak

---

## ARCHITEKTURA STEALTH (adaptacja z BeHive drones.py)

### Stack stealth dla bota:

```
Layer 1: httpx + Chrome headers          → Morizon, Gratka, Domiporta (wystarczy)
Layer 2: UA rotation pool                 → fallback jeśli L1 fail
Layer 3: curl_cffi (TLS impersonation)    → OLX/Otodom first try
Layer 4: primp (Rust TLS fingerprint)     → OLX/Otodom if cffi fails  
Layer 5: nodriver (CDP headless)          → Trojmiasto/Szybko (CF Bot Mgmt bypass)
Layer 6: patchright (stealth Playwright)  → final escalation for Turnstile
Layer 7: Jina relay                       → content extraction fallback
Layer 8: N/A (archives nie potrzebne)     
```

### Tor integration:
```python
# Tor SOCKS5 proxy for IP rotation
TOR_PROXY = "socks5://127.0.0.1:9050"

# curl_cffi z Tor:
from curl_cffi.requests import Session
with Session(impersonate="chrome131", proxy=TOR_PROXY) as s:
    resp = s.get("https://olx.pl/nieruchomosci/q-udział/")

# httpx z Tor:
import httpx
async with httpx.AsyncClient(proxy=TOR_PROXY) as client:
    resp = await client.get(url)

# nodriver z Tor:
import nodriver as uc
browser = await uc.start(
    browser_args=[f"--proxy-server=socks5://127.0.0.1:9050"]
)

# patchright z Tor:
from patchright.async_api import async_playwright
async with async_playwright() as p:
    browser = await p.chromium.launch(
        proxy={"server": "socks5://127.0.0.1:9050"}
    )
```

### Tor na Windows klienta:
- **tor.exe** portable (standalone, no Tor Browser needed)
- Dodajemy do install.bat: download tor expert bundle + uruchom jako service
- Alternatywa: embed `stem` library do programmatic Tor control
- Circuit renewal per portal (nowy IP co portal): `stem.control.Controller.signal(Signal.NEWNYM)`

---

## ZAKTUALIZOWANA MATRYCA PORTALI

| Portal | Strategia | Tor? | Layer |
|--------|-----------|------|-------|
| **Morizon** | httpx + Chrome UA | Nie (przepuszcza) | 1 |
| **Gratka** | httpx + Chrome UA | Nie (przepuszcza) | 1 |
| **Domiporta** | httpx (zero ochrony) | Nie | 1 |
| **OLX** | curl_cffi/primp + Tor SOCKS5 | ✅ TAK | 3-4 |
| **Otodom** | curl_cffi/primp + Tor SOCKS5 | ✅ TAK | 3-4 |
| **Trojmiasto** | nodriver/patchright + Tor | ✅ TAK | 5-6 |
| **Szybko** | nodriver/patchright + Tor | ✅ TAK | 5-6 |
| **Nieruchomosci-online** | httpx (brak ochrony) | Nie | 1 |
| **Allegro** | REST API (OAuth2) | Nie (oficjalne API) | - |

---

## ZALEŻNOŚCI DO INSTALACJI (requirements.txt, subset stealth)

```
# Core bot
aiogram>=3.10
aiosqlite>=0.19

# Scraping L1-2
httpx[socks]>=0.27
selectolax>=0.3

# Scraping L3
curl_cffi>=0.7

# Scraping L4 (optional, Rust - may require prebuilt wheel)
primp>=1.3

# Scraping L5
nodriver>=0.38

# Scraping L6
patchright>=1.0

# Tor control
stem>=1.8
PySocks>=1.7

# Utils
beautifulsoup4>=4.12
```

---

## FLOW ESKALACJI PER-REQUEST (pseudokod)

```python
async def fetch_with_stealth(url: str, portal_config: PortalConfig) -> str | None:
    """8-layer escalation, adapted from BeHive DroneRecon."""
    
    # Determine starting layer based on portal known profile
    start_layer = portal_config.start_layer  # e.g. OLX starts at 3
    
    tor_proxy = "socks5://127.0.0.1:9050" if portal_config.use_tor else None
    
    # Layer 1: Direct httpx
    if start_layer <= 1:
        body = await try_httpx(url, proxy=tor_proxy)
        if body and not is_blocked(body):
            return body
    
    # Layer 2: UA rotation
    if start_layer <= 2:
        for ua in random.sample(UA_POOL, 3):
            body = await try_httpx(url, ua=ua, proxy=tor_proxy)
            if body and not is_blocked(body):
                return body
    
    # Layer 3: curl_cffi
    if start_layer <= 3:
        body = await try_curl_cffi(url, target="chrome131", proxy=tor_proxy)
        if body and not is_blocked(body):
            return body
    
    # Layer 4: primp
    if start_layer <= 4:
        body = await try_primp(url, target="chrome_131", proxy=tor_proxy)
        if body and not is_blocked(body):
            return body
    
    # Layer 5: nodriver
    if start_layer <= 5:
        body = await try_nodriver(url, proxy=tor_proxy)
        if body and not is_blocked(body):
            return body
    
    # Layer 6: patchright
    if start_layer <= 6:
        body = await try_patchright(url, proxy=tor_proxy)
        if body and not is_blocked(body):
            return body
    
    # Layer 7: Jina
    body = await try_jina(url)
    if body:
        return body
    
    return None  # All layers exhausted
```

---

## KLUCZOWE DECYZJE ARCHITEKTONICZNE

1. **Tor portable na Windows** — `tor.exe` z Expert Bundle (~15MB), auto-start z botem
2. **Circuit renewal** — nowy Tor circuit (= nowy IP) per portal, nie per request (za wolne)
3. **Eskalacja per-portal** — każdy portal ma `start_layer` (Domiporta=1, OLX=3, Trojmiasto=5)
4. **Fallback graceful** — jeśli portal zablokowany po all layers → skip z info do usera
5. **Rate limiting** — 2-3s delay między requestami na tym samym portalu (nawet z Tor)
6. **Retry z nowym IP** — jeśli blocked → `NEWNYM` → retry raz

---

## ROZMIAR INSTALACJI (szacunek)

| Komponent | Rozmiar |
|-----------|---------|
| Python embedded | ~40 MB |
| Tor Expert Bundle | ~15 MB |
| Chromium (nodriver/patchright) | ~280 MB |
| Python packages | ~60 MB |
| **TOTAL** | **~400 MB** |

Alternatywa: skip Layer 5-6 (nodriver/patchright) → ~120 MB total, ale tracimy Trojmiasto/Szybko.

---

## CO DALEJ

Gotowe do fazy PLAN:
- Pełny plan implementacji (task breakdown 200 tasków)
- Architektura finalna
- Harmonogram
- Risk register z mitigacjami per portal
