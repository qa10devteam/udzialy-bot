"""
Morizon.pl scraper - Layer 1 (httpx with Chrome headers).

Search URL: https://www.morizon.pl/nieruchomosci/?q={keywords}
Selectors:
  - .property-card (listing card container)
  - .property-card__title (title)
  - .property-card__price--main (price)
  - .property-card__location (location)
  - .property-card__area (area)
  - .property-card__rooms (rooms)
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://www.morizon.pl"
SEARCH_URL = f"{BASE_URL}/nieruchomosci/"


class MorizonScraper(BaseScraper):
    """Morizon.pl real estate portal scraper."""
    
    def __init__(self, **kwargs):
        super().__init__(stealth_layer=1, use_tor=False, **kwargs)
    
    def get_portal_name(self) -> str:
        return "Morizon"
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search Morizon for listings."""
        results: List[RawListing] = []
        filters = filters or {}
        
        for keyword in keywords:
            url = self._build_search_url(keyword, filters)
            logger.info(f"[Morizon] Searching: {url}")
            
            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[Morizon] No response for keyword: {keyword}")
                continue
            
            listings = self._parse_search_results(html)
            results.extend(listings)
            logger.info(f"[Morizon] Found {len(listings)} listings for '{keyword}'")
        
        return results
    
    def _build_search_url(self, keyword: str, filters: Dict[str, Any]) -> str:
        """Build Morizon search URL with filters."""
        params = [f"q={quote_plus(keyword)}"]
        
        if "price_min" in filters:
            params.append(f"ps[price_from]={filters['price_min']}")
        if "price_max" in filters:
            params.append(f"ps[price_to]={filters['price_max']}")
        if "city" in filters:
            params.append(f"ps[location]={quote_plus(filters['city'])}")
        if "area_min" in filters:
            params.append(f"ps[living_area_from]={filters['area_min']}")
        if "area_max" in filters:
            params.append(f"ps[living_area_to]={filters['area_max']}")
        
        return f"{SEARCH_URL}?{'&'.join(params)}"
    
    def _parse_search_results(self, html: str) -> List[RawListing]:
        """Parse search results page HTML."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("bs4 not available for parsing")
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        listings: List[RawListing] = []
        
        # Find all property cards
        cards = soup.select(".property-card, [data-testid='property-card'], .listing-item")
        
        for card in cards:
            listing = self.parse_listing(str(card))
            if listing:
                listings.append(listing)
        
        return listings
    
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse a single property card HTML."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Title
        title_el = soup.select_one(
            ".property-card__title, .property-card__title a, "
            "[data-testid='listing-title'], h2.listing-title"
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None
        
        # URL
        link_el = soup.select_one(
            ".property-card__title a, a.property-card__link, "
            "[data-testid='listing-link'], a[href*='/oferta/']"
        )
        href = link_el.get("href", "") if link_el else ""
        source_url = urljoin(BASE_URL, href) if href else ""
        if not source_url:
            return None
        
        # Price
        price_el = soup.select_one(
            ".property-card__price--main, .property-card__price, "
            "[data-testid='listing-price'], .listing-price"
        )
        price_text = price_el.get_text(strip=True) if price_el else None
        price = self._parse_price(price_text)
        
        # Location
        location_el = soup.select_one(
            ".property-card__location, [data-testid='listing-location'], "
            ".listing-location"
        )
        location = location_el.get_text(strip=True) if location_el else None
        
        # Area
        area_el = soup.select_one(
            ".property-card__area, [data-testid='listing-area'], "
            ".listing-area"
        )
        area_text = area_el.get_text(strip=True) if area_el else None
        area = self._parse_area(area_text)
        
        # Rooms
        rooms_el = soup.select_one(
            ".property-card__rooms, [data-testid='listing-rooms'], "
            ".listing-rooms"
        )
        rooms_text = rooms_el.get_text(strip=True) if rooms_el else None
        rooms = self._parse_rooms(rooms_text)
        
        # Thumbnail
        img_el = soup.select_one("img.property-card__image, img[data-testid='listing-image']")
        thumbnail = img_el.get("src", None) if img_el else None
        
        # Check if it's a share (udział)
        is_share = self._detect_share(title, price_text or "")
        share_fraction = self._extract_fraction(title)
        
        return RawListing(
            title=title,
            source_url=source_url,
            portal="morizon",
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
        """Extract numeric price from text."""
        if not text:
            return None
        # Remove currency, spaces, "zł", and "PLN"
        cleaned = re.sub(r"[^\d,.]", "", text.replace(" ", ""))
        cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    def _parse_area(self, text: Optional[str]) -> Optional[float]:
        """Extract area in m² from text."""
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
        """Extract room count from text."""
        if not text:
            return None
        match = re.search(r"(\d+)", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None
    
    def _detect_share(self, title: str, description: str) -> bool:
        """Detect if listing is for a property share (udział)."""
        combined = f"{title} {description}".lower()
        share_keywords = [
            "udział", "udzial", "1/2", "1/3", "1/4", "1/6", "1/8",
            "współwłasność", "wspolwlasnosc", "ułamek", "ulamek",
        ]
        return any(kw in combined for kw in share_keywords)
    
    def _extract_fraction(self, text: str) -> Optional[str]:
        """Extract share fraction from text."""
        match = re.search(r"(\d+/\d+)", text)
        return match.group(1) if match else None
