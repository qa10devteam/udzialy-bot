"""
Gratka.pl scraper - Layer 1 (httpx with Chrome headers).

VERIFIED working selectors (2026-08-22, 860KB Nuxt SSR response):
  - a.property-card for card links (37 per page) — same framework as Morizon!
  - .property-card__title for title
  - .property-card__price--main for price
  - .property-card__location for location

Search URL: https://gratka.pl/nieruchomosci/mieszkania?fraza={keyword}
Pagination: &page=2, &page=3, etc. (page=1 causes 404!)
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://gratka.pl"
MAX_PAGES = 2


class GratkaScraper(BaseScraper):
    """Gratka.pl real estate portal scraper."""

    def __init__(self, **kwargs):
        super().__init__(stealth_layer=1, use_tor=False, **kwargs)

    def get_portal_name(self) -> str:
        return "Gratka"

    def _build_url(self, keyword: str, page: int) -> str:
        """Build search URL. page=1 uses no page param (Gratka 404s on page=1)."""
        base = f"https://gratka.pl/nieruchomosci/mieszkania?fraza={quote_plus(keyword)}"
        if page > 1:
            return f"{base}&page={page}"
        return base

    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[dict]:
        """
        Search Gratka for property listings.

        Returns:
            List of dicts with: title, price, city, voivodeship, url,
            source_portal, raw_description
        """
        results: List[dict] = []
        filters = filters or {}

        for keyword in keywords:
            for page in range(1, MAX_PAGES + 1):
                url = self._build_url(keyword, page)
                logger.info(f"[Gratka] Fetching: {url}")

                html = await fetch_with_stealth(url, self.get_portal_config())
                if not html:
                    logger.warning(f"[Gratka] No response for '{keyword}' page {page}")
                    break

                page_results = self._parse_search_results(html)
                if not page_results:
                    logger.info(f"[Gratka] No results on page {page}, stopping")
                    break

                results.extend(page_results)
                logger.info(
                    f"[Gratka] Page {page}: {len(page_results)} listings for '{keyword}'"
                )

        return results

    def _parse_search_results(self, html: str) -> List[dict]:
        """Parse search results using VERIFIED selectors."""
        soup = BeautifulSoup(html, "html.parser")
        listings: List[dict] = []

        # Primary: a.property-card (verified 37 per page — same framework as Morizon)
        cards = soup.select("a.property-card")
        if not cards:
            cards = soup.select("[data-cy='card']")

        for card in cards:
            listing = self._parse_card(card)
            if listing:
                listings.append(listing)

        return listings

    def _parse_card(self, card) -> Optional[dict]:
        """Parse a single a.property-card element."""
        # URL from href
        href = card.get("href", "")
        if not href:
            return None
        source_url = urljoin(BASE_URL, href)

        # Title: .property-card__title
        title_el = card.select_one(".property-card__title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        # Price: .property-card__price--main
        price_el = card.select_one(".property-card__price--main")
        price_text = price_el.get_text(strip=True) if price_el else ""
        price = self._parse_price(price_text)

        # Location: .property-card__location
        location_el = card.select_one(".property-card__location")
        location_text = location_el.get_text(strip=True) if location_el else ""
        city, voivodeship = self._parse_location(location_text)

        # Description
        desc_el = card.select_one(".property-card__property-description, .property-card__property-details")
        raw_description = desc_el.get_text(strip=True) if desc_el else title

        return {
            "title": title,
            "price": price,
            "city": city,
            "voivodeship": voivodeship,
            "url": source_url,
            "source_portal": "gratka",
            "raw_description": raw_description,
        }

    def _parse_price(self, text: str) -> Optional[float]:
        """Extract numeric price from '970 000 zł'."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d]", "", text.replace("\xa0", ""))
        try:
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

    def _parse_location(self, text: str) -> tuple:
        """Parse 'Ustroń, cieszyński, śląskie' -> (city, voivodeship)."""
        if not text:
            return ("", "")
        parts = [p.strip() for p in text.split(",")]
        if len(parts) >= 3:
            city = parts[0]
            voivodeship = parts[-1]
        elif len(parts) == 2:
            city = parts[0]
            voivodeship = parts[1]
        else:
            city = parts[0]
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
            portal="gratka",
            price=result["price"],
            city=result["city"],
            voivodeship=result["voivodeship"],
        )
