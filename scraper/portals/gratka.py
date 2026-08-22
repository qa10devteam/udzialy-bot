"""
Gratka.pl scraper - Layer 1 (httpx with Chrome headers).

Search URL: https://gratka.pl/nieruchomosci?fraza={keywords}
Uses similar parsing approach to Morizon.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://gratka.pl"
SEARCH_URL = f"{BASE_URL}/nieruchomosci"


class GratkaScraper(BaseScraper):
    """Gratka.pl real estate portal scraper."""
    
    def __init__(self, **kwargs):
        super().__init__(stealth_layer=1, use_tor=False, **kwargs)
    
    def get_portal_name(self) -> str:
        return "Gratka"
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search Gratka for listings."""
        results: List[RawListing] = []
        filters = filters or {}
        
        for keyword in keywords:
            url = self._build_search_url(keyword, filters)
            logger.info(f"[Gratka] Searching: {url}")
            
            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[Gratka] No response for keyword: {keyword}")
                continue
            
            listings = self._parse_search_results(html)
            results.extend(listings)
            logger.info(f"[Gratka] Found {len(listings)} listings for '{keyword}'")
        
        return results
    
    def _build_search_url(self, keyword: str, filters: Dict[str, Any]) -> str:
        """Build Gratka search URL with filters."""
        params = [f"fraza={quote_plus(keyword)}"]
        
        if "price_min" in filters:
            params.append(f"cena-calkowita:min={filters['price_min']}")
        if "price_max" in filters:
            params.append(f"cena-calkowita:max={filters['price_max']}")
        if "city" in filters:
            params.append(f"lokalizacja={quote_plus(filters['city'])}")
        if "area_min" in filters:
            params.append(f"powierzchnia:min={filters['area_min']}")
        if "area_max" in filters:
            params.append(f"powierzchnia:max={filters['area_max']}")
        
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
        
        # Gratka listing cards
        cards = soup.select(
            "article.listing__item, .listing__item, "
            "[data-cy='listing-item'], .teaserUnified"
        )
        
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
        
        # Title
        title_el = soup.select_one(
            ".listing__item__title, .teaserUnified__title, "
            "[data-cy='listing-item-title'], h2 a"
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None
        
        # URL
        link_el = soup.select_one(
            "a.listing__item__link, a.teaserUnified__anchor, "
            "[data-cy='listing-item-link'], a[href*='/nieruchomosci/']"
        )
        href = link_el.get("href", "") if link_el else ""
        source_url = urljoin(BASE_URL, href) if href else ""
        if not source_url:
            return None
        
        # Price
        price_el = soup.select_one(
            ".listing__item__price, .teaserUnified__price, "
            "[data-cy='listing-item-price'], .listing-price"
        )
        price_text = price_el.get_text(strip=True) if price_el else None
        price = self._parse_price(price_text)
        
        # Location
        location_el = soup.select_one(
            ".listing__item__location, .teaserUnified__location, "
            "[data-cy='listing-item-location']"
        )
        location = location_el.get_text(strip=True) if location_el else None
        
        # Area
        area_el = soup.select_one(
            ".listing__item__area, .teaserUnified__params li:first-child, "
            "[data-cy='listing-item-area']"
        )
        area_text = area_el.get_text(strip=True) if area_el else None
        area = self._parse_area(area_text)
        
        # Rooms
        rooms_el = soup.select_one(
            ".listing__item__rooms, .teaserUnified__params li:nth-child(2), "
            "[data-cy='listing-item-rooms']"
        )
        rooms_text = rooms_el.get_text(strip=True) if rooms_el else None
        rooms = self._parse_rooms(rooms_text)
        
        # Thumbnail
        img_el = soup.select_one("img.listing__item__image, img.teaserUnified__img")
        thumbnail = img_el.get("src", None) if img_el else None
        
        # Share detection
        is_share = self._detect_share(title)
        share_fraction = self._extract_fraction(title)
        
        return RawListing(
            title=title,
            source_url=source_url,
            portal="gratka",
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
        cleaned = re.sub(r"[^\d,.]", "", text.replace(" ", ""))
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
