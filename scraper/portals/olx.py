"""
OLX.pl scraper - Layer 3 (curl_cffi + Tor SOCKS5).

VERIFIED working approach (2026-08-22, 3.7MB via curl_cffi+Tor):
  - NO __NEXT_DATA__ available! Must use HTML parsing.
  - [data-testid=ad-card-title] a for title links
  - /d/oferta/ links in href
  - .css-u2ayx9 for title links (class-based fallback)
  - Price from sibling elements near title

Search URL: https://www.olx.pl/nieruchomosci/q-{keyword}/?page={n}
Config: start_layer=3, use_tor=True, tor_proxy=socks5://127.0.0.1:9050
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://www.olx.pl"
SEARCH_URL_TEMPLATE = "https://www.olx.pl/nieruchomosci/q-{kw}/?page={page}"
MAX_PAGES = 2


class OlxScraper(BaseScraper):
    """OLX.pl real estate scraper (curl_cffi + Tor, HTML parsing)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("use_tor", False)  # Tor unnecessary for OLX (proven: curl_cffi works direct)
        kwargs.setdefault("tor_proxy", "socks5://127.0.0.1:9050")
        super().__init__(stealth_layer=3, **kwargs)

    def get_portal_name(self) -> str:
        return "OLX"

    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[dict]:
        """
        Search OLX for property share listings.

        Uses curl_cffi with TLS impersonation through Tor SOCKS5.
        NO __NEXT_DATA__ - pure HTML parsing with verified selectors.

        Args:
            keywords: List of search terms
            filters: Optional filters dict

        Returns:
            List of dicts with: title, price, city, voivodeship, url,
            source_portal, raw_description
        """
        results: List[dict] = []
        filters = filters or {}

        for keyword in keywords:
            for page in range(1, MAX_PAGES + 1):
                # OLX uses slug-style keywords in URL path
                kw_slug = keyword.replace(" ", "-")
                url = SEARCH_URL_TEMPLATE.format(
                    kw=quote_plus(kw_slug), page=page
                )
                logger.info(f"[OLX] Fetching: {url}")

                html = await fetch_with_stealth(url, self.get_portal_config())
                if not html:
                    logger.warning(f"[OLX] No response for '{keyword}' page {page}")
                    break

                page_results = self._parse_html_results(html)
                if not page_results:
                    logger.info(f"[OLX] No results on page {page}, stopping pagination")
                    break

                results.extend(page_results)
                logger.info(
                    f"[OLX] Page {page}: {len(page_results)} listings for '{keyword}'"
                )

        return results

    def _parse_html_results(self, html: str) -> List[dict]:
        """Parse OLX HTML results using verified selectors."""
        soup = BeautifulSoup(html, "html.parser")
        listings: List[dict] = []

        # Strategy 1: [data-testid=ad-card-title] a — verified primary selector
        title_links = soup.select("[data-testid='ad-card-title'] a")
        
        if title_links:
            for link in title_links:
                listing = self._parse_from_title_link(link, soup)
                if listing:
                    listings.append(listing)
            return listings

        # Strategy 2: Find all /d/oferta/ links (direct URL pattern)
        offer_links = soup.select("a[href*='/d/oferta/']")
        seen_urls = set()
        
        for link in offer_links:
            href = link.get("href", "")
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            listing = self._parse_from_offer_link(link, soup)
            if listing:
                listings.append(listing)

        if listings:
            return listings

        # Strategy 3: .css-u2ayx9 class links (fallback)
        css_links = soup.select("a.css-u2ayx9")
        for link in css_links:
            listing = self._parse_from_title_link(link, soup)
            if listing:
                listings.append(listing)

        return listings

    def _parse_from_title_link(self, link, soup) -> Optional[dict]:
        """Parse listing from a title link element."""
        href = link.get("href", "")
        if not href or "/d/oferta/" not in href:
            # Skip non-offer links
            if not href:
                return None
        
        source_url = urljoin(BASE_URL, href)
        title = link.get_text(strip=True)
        if not title:
            return None

        # Navigate up to find the card container for price/location
        card = link.find_parent("div", {"data-testid": True})
        if not card:
            card = link.find_parent("div", recursive=True)
            # Go up to a reasonable container
            for _ in range(5):
                if card and card.parent:
                    parent = card.parent
                    if parent.name == "div" and len(parent.get_text()) > len(title) + 20:
                        card = parent
                        break
                    card = parent

        price = None
        city = ""
        voivodeship = ""
        raw_description = title

        if card:
            # Price: look for price-like elements
            price_el = card.select_one("[data-testid='ad-price']")
            if not price_el:
                # Find text that looks like price (contains "zł")
                for el in card.find_all(string=re.compile(r"\d.*zł|PLN", re.IGNORECASE)):
                    price_text = el.strip()
                    price = self._parse_price(price_text)
                    if price:
                        break
            else:
                price = self._parse_price(price_el.get_text(strip=True))

            # Location: look for location-like elements
            location_el = card.select_one("[data-testid='location-date']")
            if location_el:
                location_text = location_el.get_text(strip=True)
                # OLX format: "Warszawa, Mokotów - Dzisiaj 14:30"
                location_part = location_text.split(" - ")[0] if " - " in location_text else location_text
                city, voivodeship = self._parse_location(location_part)

            # Raw description - all card text
            raw_description = card.get_text(" ", strip=True)[:300]

        return {
            "title": title,
            "price": price,
            "city": city,
            "voivodeship": voivodeship,
            "url": source_url,
            "source_portal": "olx",
            "raw_description": raw_description,
        }

    def _parse_from_offer_link(self, link, soup) -> Optional[dict]:
        """Parse listing from an /d/oferta/ link."""
        href = link.get("href", "")
        if not href:
            return None

        source_url = urljoin(BASE_URL, href)
        title = link.get_text(strip=True)
        
        # Sometimes these are image links, skip if no text
        if not title or len(title) < 5:
            return None

        return {
            "title": title,
            "price": None,
            "city": "",
            "voivodeship": "",
            "url": source_url,
            "source_portal": "olx",
            "raw_description": title,
        }

    def _parse_price(self, text: str) -> Optional[float]:
        """Extract numeric price from text. Handles: 150 000, 150.000, 150,000 PLN."""
        if not text:
            return None
        # Remove "do negocjacji", "PLN", "zł" etc
        text = text.replace("do negocjacji", "").replace("PLN", "").replace("zł", "")
        # Remove non-digit chars except comma and dot
        cleaned = re.sub(r"[^\d,.]", "", text.replace("\xa0", "").replace(" ", ""))
        cleaned = cleaned.replace(",", ".")
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")
        elif "." in cleaned and len(cleaned.split(".")[-1]) == 3:
            cleaned = cleaned.replace(".", "")
        try:
            val = float(cleaned) if cleaned else None
            # Sanity check - property prices should be > 1000
            if val and val < 100:
                return None
            return val
        except (ValueError, TypeError):
            return None

    def _parse_location(self, text: str) -> tuple:
        """Parse location text into (city, voivodeship)."""
        if not text:
            return ("", "")
        parts = [p.strip() for p in text.split(",")]
        city = parts[0] if parts else ""
        voivodeship = parts[-1] if len(parts) > 1 else ""
        return (city, voivodeship)

    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse a single listing card HTML into RawListing (legacy interface)."""
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("[data-testid='ad-card-title'] a, a[href*='/d/oferta/']")
        if not links:
            return None
        result = self._parse_from_title_link(links[0], soup)
        if not result:
            return None
        return RawListing(
            title=result["title"],
            source_url=result["url"],
            portal="olx",
            price=result["price"],
            location=f"{result['city']}, {result['voivodeship']}",
            city=result["city"],
            voivodeship=result["voivodeship"],
            description=result["raw_description"],
        )
