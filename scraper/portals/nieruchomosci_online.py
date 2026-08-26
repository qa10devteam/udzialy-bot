"""
NieruchomosciOnline.pl scraper - Layer 1 (httpx, standard parsing).

Search URL: https://www.nieruchomosci-online.pl/szukaj.html?text={keywords}
Moderate protection, standard HTML parsing works.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nieruchomosci-online.pl"
SEARCH_URL = f"{BASE_URL}/szukaj.html"


class NieruchomosciOnlineScraper(BaseScraper):
    """NieruchomosciOnline.pl scraper."""
    
    def __init__(self, **kwargs):
        super().__init__(stealth_layer=1, use_tor=False, **kwargs)
    
    def get_portal_name(self) -> str:
        return "NieruchomosciOnline"
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search NieruchomosciOnline for listings."""
        results: List[RawListing] = []
        filters = filters or {}
        
        for keyword in keywords:
            url = self._build_search_url(keyword, filters)
            logger.info(f"[NieruchomosciOnline] Searching: {url}")
            
            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[NieruchomosciOnline] No response for keyword: {keyword}")
                continue
            
            listings = self._parse_search_results(html)
            results.extend(listings)
            logger.info(f"[NieruchomosciOnline] Found {len(listings)} listings for '{keyword}'")
        
        return results
    
    def _build_search_url(self, keyword: str, filters: Dict[str, Any]) -> str:
        """Build search URL."""
        params = [f"text={quote_plus(keyword)}"]
        
        if "price_min" in filters:
            params.append(f"3_price_from={filters['price_min']}")
        if "price_max" in filters:
            params.append(f"3_price_to={filters['price_max']}")
        if "city" in filters:
            params.append(f"1_location={quote_plus(filters['city'])}")
        if "area_min" in filters:
            params.append(f"3_area_from={filters['area_min']}")
        if "area_max" in filters:
            params.append(f"3_area_to={filters['area_max']}")
        
        return f"{SEARCH_URL}?{'&'.join(params)}"
    
    def _parse_search_results(self, html: str) -> List[RawListing]:
        """Parse search results."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("bs4 not available")
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        listings: List[RawListing] = []
        
        # NieruchomosciOnline listing selectors (verified 2026-08)
        cards = soup.select("div.tile")
        
        for card in cards:
            listing = self.parse_listing(str(card))
            if listing:
                listings.append(listing)
        
        return listings
    
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse a single listing card."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Title (verified 2026-08: h2.name a)
        title_el = soup.select_one("h2.name a")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None
        
        # URL
        href = title_el.get("href", "") if title_el else ""
        source_url = urljoin(BASE_URL, href) if href else ""
        if not source_url:
            return None
        
        # Price (verified 2026-08: .primary-display span:first-child)
        price_el = soup.select_one(".primary-display span:first-child")
        price_text = price_el.get_text(strip=True) if price_el else None
        price = self._parse_price(price_text)
        
        # Location (verified 2026-08: p.province)
        location_el = soup.select_one("p.province")
        location = location_el.get_text(strip=True) if location_el else None
        
        # Area (verified 2026-08: span.area)
        area = None
        area_el = soup.select_one("span.area")
        if area_el:
            area = self._parse_area(area_el.get_text(strip=True))
        
        # Rooms
        rooms = None
        rooms_el = soup.select_one("span.rooms, [data-param='rooms']")
        if rooms_el:
            rooms = self._parse_rooms(rooms_el.get_text(strip=True))
        
        # Thumbnail
        img_el = soup.select_one("img")
        thumbnail = None
        if img_el:
            thumbnail = img_el.get("data-src") or img_el.get("src")
            if thumbnail and thumbnail.startswith("data:"):
                thumbnail = None
        
        is_share = self._detect_share(title)
        share_fraction = self._extract_fraction(title)
        
        return RawListing(
            title=title,
            source_url=source_url,
            portal="nieruchomosci_online",
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
