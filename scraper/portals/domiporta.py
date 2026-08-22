"""
Domiporta.pl scraper - Layer 1 (httpx with Chrome headers).

VERIFIED working selectors (2026-08-22, 435KB response):
  - article.sneakpeak for card containers (36 per page)
  - h2.sneakpeak__title--bold a for title + href
  - span.sneakpeak__price_value for price
  - .sneakpeak__title--inblock for location (e.g. "mieszkanie Gdynia, Chwarzno")
  - .sneakpeak__details_item--area for area
  - .sneakpeak__description for description text

Search URL: https://www.domiporta.pl/mieszkanie/sprzedam?KeyWords={keyword}&PageNumber={n}
(PageNumber=1 works on Domiporta!)
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://www.domiporta.pl"
SEARCH_URL_TEMPLATE = (
    "https://www.domiporta.pl/mieszkanie/sprzedam?KeyWords={kw}&PageNumber={page}"
)
MAX_PAGES = 2


class DomiportaScraper(BaseScraper):
    """Domiporta.pl real estate portal scraper."""

    def __init__(self, **kwargs):
        super().__init__(stealth_layer=1, use_tor=False, **kwargs)

    def get_portal_name(self) -> str:
        return "Domiporta"

    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[dict]:
        """
        Search Domiporta for property listings.

        Returns:
            List of dicts with: title, price, city, voivodeship, url,
            source_portal, raw_description
        """
        results: List[dict] = []
        filters = filters or {}

        for keyword in keywords:
            for page in range(1, MAX_PAGES + 1):
                url = SEARCH_URL_TEMPLATE.format(
                    kw=quote_plus(keyword), page=page
                )
                logger.info(f"[Domiporta] Fetching: {url}")

                html = await fetch_with_stealth(url, self.get_portal_config())
                if not html:
                    logger.warning(f"[Domiporta] No response for '{keyword}' page {page}")
                    break

                page_results = self._parse_search_results(html)
                if not page_results:
                    logger.info(f"[Domiporta] No results on page {page}, stopping")
                    break

                results.extend(page_results)
                logger.info(
                    f"[Domiporta] Page {page}: {len(page_results)} listings for '{keyword}'"
                )

        return results

    def _parse_search_results(self, html: str) -> List[dict]:
        """Parse search results using VERIFIED selectors."""
        soup = BeautifulSoup(html, "html.parser")
        listings: List[dict] = []

        # Primary: article.sneakpeak (verified 36 per page)
        cards = soup.select("article.sneakpeak")

        for card in cards:
            listing = self._parse_card(card)
            if listing:
                listings.append(listing)

        return listings

    def _parse_card(self, card) -> Optional[dict]:
        """Parse a single article.sneakpeak element."""
        # URL + Title from h2.sneakpeak__title--bold a
        h2 = card.select_one("h2.sneakpeak__title--bold")
        if not h2:
            return None
        
        link = h2.select_one("a")
        if not link:
            # Try the picture link
            link = card.select_one("a.sneakpeak__picture_container")
        
        if not link:
            return None

        href = link.get("href", "")
        if not href:
            return None
        source_url = urljoin(BASE_URL, href)

        title = h2.get_text(strip=True)
        if not title:
            title = link.get_text(strip=True)
        if not title:
            return None

        # Price: span.sneakpeak__price_value
        price_el = card.select_one("span.sneakpeak__price_value")
        price_text = price_el.get_text(strip=True) if price_el else ""
        price = self._parse_price(price_text)

        # Location from .sneakpeak__title--inblock
        # Format: "mieszkanie Gdynia, Chwarzno-Wiczlino, Fort Forest, Niemena"
        loc_el = card.select_one(".sneakpeak__title--inblock")
        location_text = loc_el.get_text(strip=True) if loc_el else ""
        city, voivodeship = self._parse_location(location_text)

        # Description from .sneakpeak__description
        desc_el = card.select_one(".sneakpeak__description")
        raw_description = desc_el.get_text(strip=True) if desc_el else title

        return {
            "title": title,
            "price": price,
            "city": city,
            "voivodeship": voivodeship,
            "url": source_url,
            "source_portal": "domiporta",
            "raw_description": raw_description,
        }

    def _parse_price(self, text: str) -> Optional[float]:
        """Extract numeric price from '1 099 000 zł'."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d]", "", text.replace("\xa0", ""))
        try:
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

    def _parse_location(self, text: str) -> tuple:
        """Parse 'mieszkanie Gdynia, Chwarzno-Wiczlino, ...' -> (city, voivodeship).
        
        Domiporta format: "type City, District, Street"
        The first word is the property type (mieszkanie/dom), skip it.
        """
        if not text:
            return ("", "")
        
        # Remove property type prefix
        text = re.sub(r"^(mieszkanie|dom|lokal|działka)\s+", "", text, flags=re.IGNORECASE)
        
        parts = [p.strip() for p in text.split(",")]
        city = parts[0] if parts else ""
        # Domiporta doesn't show voivodeship in the subtitle
        voivodeship = ""
        return (city, voivodeship)

    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Legacy interface."""
        soup = BeautifulSoup(html, "html.parser")
        result = self._parse_card(soup)
        if not result:
            return None
        return RawListing(
            title=result["title"],
            source_url=result["url"],
            portal="domiporta",
            price=result["price"],
            city=result["city"],
            voivodeship=result["voivodeship"],
        )
