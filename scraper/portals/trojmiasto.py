"""
Trojmiasto.pl scraper - Layer 5-6 (nodriver/patchright + Tor).

Trojmiasto uses heavy JS rendering and CF protection.
Requires browser-based scraping for reliable extraction.
Search URL: https://ogloszenia.trojmiasto.pl/nieruchomosci/?q={keywords}
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://ogloszenia.trojmiasto.pl"
SEARCH_URL = f"{BASE_URL}/nieruchomosci/"


class TrojmiastoScraper(BaseScraper):
    """Trojmiasto.pl real estate scraper (JS-heavy, CF protected)."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault("use_tor", True)
        super().__init__(stealth_layer=5, **kwargs)
    
    def get_portal_name(self) -> str:
        return "Trojmiasto"
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search Trojmiasto for listings."""
        results: List[RawListing] = []
        filters = filters or {}
        
        for keyword in keywords:
            url = self._build_search_url(keyword, filters)
            logger.info(f"[Trojmiasto] Searching: {url}")
            
            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[Trojmiasto] No response for keyword: {keyword}")
                continue
            
            listings = self._parse_search_results(html)
            results.extend(listings)
            logger.info(f"[Trojmiasto] Found {len(listings)} listings for '{keyword}'")
        
        return results
    
    def _build_search_url(self, keyword: str, filters: Dict[str, Any]) -> str:
        """Build Trojmiasto search URL."""
        params = [f"q={quote_plus(keyword)}"]
        
        if "price_min" in filters:
            params.append(f"cena_od={filters['price_min']}")
        if "price_max" in filters:
            params.append(f"cena_do={filters['price_max']}")
        if "area_min" in filters:
            params.append(f"powierzchnia_od={filters['area_min']}")
        if "area_max" in filters:
            params.append(f"powierzchnia_do={filters['area_max']}")
        
        return f"{SEARCH_URL}?{'&'.join(params)}"
    
    def _parse_search_results(self, html: str) -> List[RawListing]:
        """Parse Trojmiasto search results."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("bs4 not available")
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        listings: List[RawListing] = []
        
        # Trojmiasto listing card selectors
        cards = soup.select(
            ".list__item, .ogloszenie, .listing-item, "
            "[data-id], article.ogl-list"
        )
        
        for card in cards:
            listing = self.parse_listing(str(card))
            if listing:
                listings.append(listing)
        
        return listings
    
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse a single Trojmiasto listing card."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Title
        title_el = soup.select_one(
            ".list__item__title, .ogl-list__title, "
            "h2 a, .listing-item__title a"
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None
        
        # URL
        link_el = soup.select_one(
            ".list__item__title a, .ogl-list__title a, "
            "a[href*='ogloszenia.trojmiasto.pl'], h2 a[href]"
        )
        href = link_el.get("href", "") if link_el else ""
        source_url = urljoin(BASE_URL, href) if href else ""
        if not source_url:
            return None
        
        # Price
        price_el = soup.select_one(
            ".list__item__price, .ogl-list__price, "
            ".listing-item__price, .price"
        )
        price_text = price_el.get_text(strip=True) if price_el else None
        price = self._parse_price(price_text)
        
        # Location
        location_el = soup.select_one(
            ".list__item__location, .ogl-list__location, "
            ".listing-item__location, .location"
        )
        location = location_el.get_text(strip=True) if location_el else None
        
        # Area
        area_el = soup.select_one(
            ".list__item__details .area, .ogl-list__params span:first-child"
        )
        area_text = area_el.get_text(strip=True) if area_el else None
        area = self._parse_area(area_text)
        
        # Rooms
        rooms_el = soup.select_one(
            ".list__item__details .rooms, .ogl-list__params span:nth-child(2)"
        )
        rooms_text = rooms_el.get_text(strip=True) if rooms_el else None
        rooms = self._parse_rooms(rooms_text)
        
        # Thumbnail
        img_el = soup.select_one("img.list__item__img, img.ogl-list__img, img[data-src]")
        thumbnail = None
        if img_el:
            thumbnail = img_el.get("data-src") or img_el.get("src")
        
        is_share = self._detect_share(title)
        share_fraction = self._extract_fraction(title)
        
        return RawListing(
            title=title,
            source_url=source_url,
            portal="trojmiasto",
            price=price,
            price_text=price_text,
            location=location,
            area_m2=area,
            rooms=rooms,
            thumbnail_url=thumbnail,
            is_share=is_share,
            share_fraction=share_fraction,
        )
    
    def _parse_price(self, text: Optional[str]) -> Optional[float]:
        if not text:
            return None
        cleaned = re.sub(r"[^\d,.]", "", text.replace(" ", "").replace("\xa0", ""))
        cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    def _parse_area(self, text: Optional[str]) -> Optional[float]:
        if not text:
            return None
        match = re.search(r"([\d,.]+)\s*m", text)
        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except ValueError:
                pass
        return None
    
    def _parse_rooms(self, text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else None
    
    def _detect_share(self, title: str) -> bool:
        combined = title.lower()
        share_keywords = [
            "udział", "udzial", "1/2", "1/3", "1/4", "1/6", "1/8",
            "współwłasność", "wspolwlasnosc",
        ]
        return any(kw in combined for kw in share_keywords)
    
    def _extract_fraction(self, text: str) -> Optional[str]:
        match = re.search(r"(\d+/\d+)", text)
        return match.group(1) if match else None
