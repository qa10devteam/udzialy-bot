"""
udzialy-bot scraper package.

8-layer stealth escalation system for Polish real estate portal scraping.
Adapted from BeHive drone architecture.

Layers:
  1. httpx + Chrome headers
  2. UA rotation (12+ real UAs)
  3. curl_cffi TLS impersonation (chrome131)
  4. primp Rust TLS (chrome_131)
  5. nodriver headless CDP
  6. patchright stealth Playwright
  7. Jina relay (r.jina.ai)
  8. skip/report

Portals: Morizon, Gratka, Domiporta, OLX, Otodom, Trojmiasto, Szybko,
         NieruchomosciOnline, Allegro
"""

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth
from scraper.manager import ScraperManager
from scraper.tor_manager import TorManager

__all__ = [
    "BaseScraper",
    "RawListing",
    "fetch_with_stealth",
    "ScraperManager",
    "TorManager",
]

__version__ = "1.0.0"
