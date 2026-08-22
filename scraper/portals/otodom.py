"""
Otodom.pl scraper - Layer 3-4 (curl_cffi + Tor).

Otodom uses Next.js with Cloudflare protection.
Search URL: https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska?description={keywords}
Data extraction: __NEXT_DATA__ JSON embedded in page.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

BASE_URL = "https://www.otodom.pl"


class OtodomScraper(BaseScraper):
    """Otodom.pl real estate scraper (Next.js + CF protected)."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault("use_tor", True)
        super().__init__(stealth_layer=3, **kwargs)
    
    def get_portal_name(self) -> str:
        return "Otodom"
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search Otodom for listings."""
        results: List[RawListing] = []
        filters = filters or {}
        
        for keyword in keywords:
            url = self._build_search_url(keyword, filters)
            logger.info(f"[Otodom] Searching: {url}")
            
            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[Otodom] No response for keyword: {keyword}")
                continue
            
            # Try __NEXT_DATA__ first
            listings = self._parse_next_data(html)
            if not listings:
                listings = self._parse_html_results(html)
            
            results.extend(listings)
            logger.info(f"[Otodom] Found {len(listings)} listings for '{keyword}'")
        
        return results
    
    def _build_search_url(self, keyword: str, filters: Dict[str, Any]) -> str:
        """Build Otodom search URL with description search."""
        # Base search path
        property_type = filters.get("property_type", "mieszkanie")
        transaction = filters.get("transaction", "sprzedaz")
        location = filters.get("location", "cala-polska")
        
        url = f"{BASE_URL}/pl/wyniki/{transaction}/{property_type}/{location}"
        
        params = [f"description={quote_plus(keyword)}"]
        
        if "price_min" in filters:
            params.append(f"priceMin={filters['price_min']}")
        if "price_max" in filters:
            params.append(f"priceMax={filters['price_max']}")
        if "area_min" in filters:
            params.append(f"areaMin={filters['area_min']}")
        if "area_max" in filters:
            params.append(f"areaMax={filters['area_max']}")
        if "rooms_min" in filters:
            params.append(f"roomsNumber=%5B{filters['rooms_min']}%5D")
        
        return f"{url}?{'&'.join(params)}"
    
    def _parse_next_data(self, html: str) -> List[RawListing]:
        """Extract listings from __NEXT_DATA__ JSON."""
        match = re.search(
            r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not match:
            return []
        
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning("[Otodom] Failed to parse __NEXT_DATA__")
            return []
        
        listings: List[RawListing] = []
        
        try:
            # Otodom Next.js structure
            page_props = data.get("props", {}).get("pageProps", {})
            
            # Try multiple paths for the listing data
            search_data = (
                page_props.get("data", {}).get("searchAds", {}) or
                page_props.get("searchAds", {}) or
                page_props.get("data", {}).get("ads", {})
            )
            
            items = search_data.get("items", [])
            if not items:
                items = search_data.get("ads", [])
            
            for item in items:
                listing = self._parse_item_json(item)
                if listing:
                    listings.append(listing)
                    
        except (KeyError, TypeError, AttributeError) as e:
            logger.warning(f"[Otodom] Error navigating __NEXT_DATA__: {e}")
        
        return listings
    
    def _parse_item_json(self, item: Dict[str, Any]) -> Optional[RawListing]:
        """Parse a single Otodom listing from JSON."""
        try:
            title = item.get("title", "")
            if not title:
                return None
            
            # URL
            slug = item.get("slug", "")
            item_id = item.get("id", "")
            url = f"{BASE_URL}/pl/oferta/{slug}" if slug else ""
            if not url and item_id:
                url = f"{BASE_URL}/pl/oferta/{item_id}"
            if not url:
                return None
            
            # Price
            price = None
            price_text = None
            total_price = item.get("totalPrice", {})
            if isinstance(total_price, dict):
                price = total_price.get("value")
                currency = total_price.get("currency", "PLN")
                if price:
                    price_text = f"{price} {currency}"
            elif isinstance(total_price, (int, float)):
                price = float(total_price)
                price_text = f"{price} PLN"
            
            # Location
            location_data = item.get("location", {})
            location_parts = []
            if isinstance(location_data, dict):
                address = location_data.get("address", {})
                if isinstance(address, dict):
                    city = address.get("city", {})
                    city_name = city.get("name", "") if isinstance(city, dict) else str(city)
                    district = address.get("district", {})
                    district_name = district.get("name", "") if isinstance(district, dict) else ""
                    if city_name:
                        location_parts.append(city_name)
                    if district_name:
                        location_parts.append(district_name)
            
            location = ", ".join(location_parts) if location_parts else None
            city = location_parts[0] if location_parts else None
            
            # Area
            area = item.get("areaInM2", item.get("area"))
            if area:
                try:
                    area = float(area)
                except (ValueError, TypeError):
                    area = None
            
            # Rooms
            rooms = item.get("roomsNumber", item.get("rooms"))
            if rooms:
                try:
                    rooms = int(rooms)
                except (ValueError, TypeError):
                    rooms = None
            
            # Floor
            floor = item.get("floor")
            if floor:
                try:
                    floor = int(floor)
                except (ValueError, TypeError):
                    floor = None
            
            # Thumbnail
            images = item.get("images", [])
            thumbnail = None
            if images and isinstance(images, list):
                first_img = images[0] if images else {}
                if isinstance(first_img, dict):
                    thumbnail = first_img.get("medium", first_img.get("small", first_img.get("url")))
                elif isinstance(first_img, str):
                    thumbnail = first_img
            
            # Description
            description = item.get("description", "")
            
            # Share detection
            combined = f"{title} {description}".lower()
            is_share = self._detect_share(combined)
            share_fraction = self._extract_fraction(f"{title} {description}")
            
            return RawListing(
                title=title,
                source_url=url,
                portal="otodom",
                price=price,
                price_text=price_text,
                location=location,
                city=city,
                area_m2=area,
                rooms=rooms,
                floor=floor,
                thumbnail_url=thumbnail,
                description=description[:500] if description else None,
                listing_id=str(item_id),
                is_share=is_share,
                share_fraction=share_fraction,
            )
            
        except Exception as e:
            logger.warning(f"[Otodom] Error parsing item: {e}")
            return None
    
    def _parse_html_results(self, html: str) -> List[RawListing]:
        """Fallback HTML parsing for Otodom."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        listings: List[RawListing] = []
        
        cards = soup.select(
            "[data-cy='listing-item'], [data-testid='listing-card'], "
            "article[data-cy='listing-item-link']"
        )
        
        for card in cards:
            listing = self.parse_listing(str(card))
            if listing:
                listings.append(listing)
        
        return listings
    
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse single Otodom listing card HTML (fallback)."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Title
        title_el = soup.select_one(
            "[data-cy='listing-item-title'], h3, "
            "[data-testid='listing-card-title']"
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None
        
        # URL
        link_el = soup.select_one("a[href*='/oferta/']")
        href = link_el.get("href", "") if link_el else ""
        source_url = urljoin(BASE_URL, href) if href else ""
        if not source_url:
            return None
        
        # Price
        price_el = soup.select_one(
            "[data-cy='listing-item-price'], [data-testid='listing-card-price']"
        )
        price_text = price_el.get_text(strip=True) if price_el else None
        price = self._parse_price(price_text)
        
        # Location
        loc_el = soup.select_one(
            "[data-testid='listing-card-location'], .listing-item__location"
        )
        location = loc_el.get_text(strip=True) if loc_el else None
        
        is_share = self._detect_share(title)
        share_fraction = self._extract_fraction(title)
        
        return RawListing(
            title=title,
            source_url=source_url,
            portal="otodom",
            price=price,
            price_text=price_text,
            location=location,
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
    
    def _detect_share(self, text: str) -> bool:
        text_lower = text.lower()
        share_keywords = [
            "udział", "udzial", "1/2", "1/3", "1/4", "1/6", "1/8",
            "współwłasność", "wspolwlasnosc",
        ]
        return any(kw in text_lower for kw in share_keywords)
    
    def _extract_fraction(self, text: str) -> Optional[str]:
        match = re.search(r"(\d+/\d+)", text)
        return match.group(1) if match else None
