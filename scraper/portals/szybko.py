"""
Szybko.pl scraper - Layer 5-6 (nodriver/patchright + Tor).

Szybko.pl uses JS rendering with anti-bot measures.
Search URL: https://www.szybko.pl/szukaj?q={keywords}&type=nieruchomosci
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://www.szybko.pl"
SEARCH_URL = f"{BASE_URL}/szukaj"


class SzybkoScraper(BaseScraper):
    """Szybko.pl real estate scraper (JS-heavy, requires browser)."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault("use_tor", True)
        super().__init__(stealth_layer=5, **kwargs)
    
    def get_portal_name(self) -> str:
        return "Szybko"
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search Szybko.pl for listings."""
        results: List[RawListing] = []
        filters = filters or {}
        
        for keyword in keywords:
            url = self._build_search_url(keyword, filters)
            logger.info(f"[Szybko] Searching: {url}")
            
            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[Szybko] No response for keyword: {keyword}")
                continue
            
            listings = self._parse_search_results(html)
            results.extend(listings)
            logger.info(f"[Szybko] Found {len(listings)} listings for '{keyword}'")
        
        return results
    
    def _build_search_url(self, keyword: str, filters: Dict[str, Any]) -> str:
        """Build Szybko search URL."""
        params = [
            f"q={quote_plus(keyword)}",
            "type=nieruchomosci",
        ]
        
        if "price_min" in filters:
            params.append(f"price_from={filters['price_min']}")
        if "price_max" in filters:
            params.append(f"price_to={filters['price_max']}")
        if "city" in filters:
            params.append(f"city={quote_plus(filters['city'])}")
        if "area_min" in filters:
            params.append(f"area_from={filters['area_min']}")
        if "area_max" in filters:
            params.append(f"area_to={filters['area_max']}")
        
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
        
        # Szybko listing cards
        cards = soup.select(
            ".offer-card, .search-result-item, "
            "[data-offer-id], .listing-card, article.offer"
        )
        
        for card in cards:
            listing = self.parse_listing(str(card))
            if listing:
                listings.append(listing)
        
        return listings
    
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse a single Szybko listing card."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Title
        title_el = soup.select_one(
            ".offer-card__title, .listing-card__title, "
            "h2.offer-title, a.offer-link"
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None
        
        # URL
        link_el = soup.select_one(
            "a.offer-card__link, a.listing-card__link, "
            "a[href*='/oferta/'], a[href*='/ogloszenie/']"
        )
        href = link_el.get("href", "") if link_el else ""
        source_url = urljoin(BASE_URL, href) if href else ""
        if not source_url:
            return None
        
        # Price
        price_el = soup.select_one(
            ".offer-card__price, .listing-card__price, "
            ".offer-price, .price-value"
        )
        price_text = price_el.get_text(strip=True) if price_el else None
        price = self._parse_price(price_text)
        
        # Location
        location_el = soup.select_one(
            ".offer-card__location, .listing-card__location, "
            ".offer-location"
        )
        location = location_el.get_text(strip=True) if location_el else None
        
        # Area
        area_el = soup.select_one(
            ".offer-card__area, .listing-card__params .area, "
            ".offer-area"
        )
        area_text = area_el.get_text(strip=True) if area_el else None
        area = self._parse_area(area_text)
        
        # Rooms
        rooms_el = soup.select_one(
            ".offer-card__rooms, .listing-card__params .rooms, "
            ".offer-rooms"
        )
        rooms_text = rooms_el.get_text(strip=True) if rooms_el else None
        rooms = self._parse_rooms(rooms_text)
        
        # Thumbnail
        img_el = soup.select_one("img.offer-card__img, img.listing-card__img")
        thumbnail = None
        if img_el:
            thumbnail = img_el.get("data-src") or img_el.get("src")
        
        is_share = self._detect_share(title)
        share_fraction = self._extract_fraction(title)
        
        return RawListing(
            title=title,
            source_url=source_url,
            portal="szybko",
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
