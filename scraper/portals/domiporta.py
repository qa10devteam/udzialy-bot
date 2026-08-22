"""
Domiporta.pl scraper - Layer 1 (httpx with Chrome headers).

Search URL: https://www.domiporta.pl/nieruchomosci/szukaj?KeyWords={keywords}
Selectors:
  - article.sneakpeak (listing card container)
  - h2.sneakpeak__title--bold (title)
  - span.sneakpeak__price_value (price)
  - .sneakpeak__details_item (details: area, rooms)
  - .sneakpeak__location (location)
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://www.domiporta.pl"
SEARCH_URL = f"{BASE_URL}/nieruchomosci/szukaj"


class DomiportaScraper(BaseScraper):
    """Domiporta.pl real estate portal scraper."""
    
    def __init__(self, **kwargs):
        super().__init__(stealth_layer=1, use_tor=False, **kwargs)
    
    def get_portal_name(self) -> str:
        return "Domiporta"
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search Domiporta for listings."""
        results: List[RawListing] = []
        filters = filters or {}
        
        for keyword in keywords:
            url = self._build_search_url(keyword, filters)
            logger.info(f"[Domiporta] Searching: {url}")
            
            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[Domiporta] No response for keyword: {keyword}")
                continue
            
            listings = self._parse_search_results(html)
            results.extend(listings)
            logger.info(f"[Domiporta] Found {len(listings)} listings for '{keyword}'")
        
        return results
    
    def _build_search_url(self, keyword: str, filters: Dict[str, Any]) -> str:
        """Build Domiporta search URL."""
        params = [f"KeyWords={quote_plus(keyword)}"]
        
        if "price_min" in filters:
            params.append(f"Price.From={filters['price_min']}")
        if "price_max" in filters:
            params.append(f"Price.To={filters['price_max']}")
        if "city" in filters:
            params.append(f"Location={quote_plus(filters['city'])}")
        if "area_min" in filters:
            params.append(f"Surface.From={filters['area_min']}")
        if "area_max" in filters:
            params.append(f"Surface.To={filters['area_max']}")
        
        return f"{SEARCH_URL}?{'&'.join(params)}"
    
    def _parse_search_results(self, html: str) -> List[RawListing]:
        """Parse search results page."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("bs4 not available")
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        listings: List[RawListing] = []
        
        # Domiporta uses article.sneakpeak for listing cards
        cards = soup.select(
            "article.sneakpeak, .sneakpeak, "
            "[data-testid='search-result'], .listing-item"
        )
        
        for card in cards:
            listing = self.parse_listing(str(card))
            if listing:
                listings.append(listing)
        
        return listings
    
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse a single sneakpeak article card."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Title - h2.sneakpeak__title--bold
        title_el = soup.select_one(
            "h2.sneakpeak__title--bold, h2.sneakpeak__title, "
            ".sneakpeak__title a, .listing-item__title"
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None
        
        # URL
        link_el = soup.select_one(
            "a.sneakpeak__title, a.sneakpeak__link, "
            "h2.sneakpeak__title--bold a, a[href*='/nieruchomosci/']"
        )
        if not link_el:
            link_el = soup.select_one("a[href]")
        href = link_el.get("href", "") if link_el else ""
        source_url = urljoin(BASE_URL, href) if href else ""
        if not source_url:
            return None
        
        # Price - span.sneakpeak__price_value
        price_el = soup.select_one(
            "span.sneakpeak__price_value, .sneakpeak__price, "
            ".listing-item__price, [data-testid='price']"
        )
        price_text = price_el.get_text(strip=True) if price_el else None
        price = self._parse_price(price_text)
        
        # Location - .sneakpeak__location
        location_el = soup.select_one(
            ".sneakpeak__location, .sneakpeak__address, "
            ".listing-item__location"
        )
        location = location_el.get_text(strip=True) if location_el else None
        
        # Area and rooms from details
        area = None
        rooms = None
        details = soup.select(
            ".sneakpeak__details_item, .sneakpeak__param, "
            ".listing-item__params li"
        )
        for detail in details:
            text = detail.get_text(strip=True).lower()
            if "m²" in text or "m2" in text or "powierzchnia" in text:
                area = self._parse_area(text)
            elif "poko" in text or "room" in text:
                rooms = self._parse_rooms(text)
        
        # Thumbnail
        img_el = soup.select_one("img.sneakpeak__img, img.sneakpeak__photo")
        thumbnail = img_el.get("src", None) or img_el.get("data-src", None) if img_el else None
        
        # Share detection
        is_share = self._detect_share(title)
        share_fraction = self._extract_fraction(title)
        
        return RawListing(
            title=title,
            source_url=source_url,
            portal="domiporta",
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
