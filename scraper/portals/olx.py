"""
OLX.pl scraper - Layer 3-4 (curl_cffi + Tor).

OLX uses Next.js with aggressive bot protection (Cloudflare).
Search URL: https://www.olx.pl/nieruchomosci/q-{keywords}/
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

BASE_URL = "https://www.olx.pl"


class OlxScraper(BaseScraper):
    """OLX.pl real estate scraper (Next.js + CF protected)."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault("use_tor", True)
        super().__init__(stealth_layer=3, **kwargs)
    
    def get_portal_name(self) -> str:
        return "OLX"
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search OLX for listings."""
        results: List[RawListing] = []
        filters = filters or {}
        
        for keyword in keywords:
            url = self._build_search_url(keyword, filters)
            logger.info(f"[OLX] Searching: {url}")
            
            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[OLX] No response for keyword: {keyword}")
                continue
            
            # Try __NEXT_DATA__ extraction first (preferred)
            listings = self._parse_next_data(html)
            if not listings:
                # Fallback to HTML parsing
                listings = self._parse_html_results(html)
            
            results.extend(listings)
            logger.info(f"[OLX] Found {len(listings)} listings for '{keyword}'")
        
        return results
    
    def _build_search_url(self, keyword: str, filters: Dict[str, Any]) -> str:
        """Build OLX search URL."""
        # OLX uses slug-style keywords in URL
        kw_slug = keyword.replace(" ", "-").lower()
        url = f"{BASE_URL}/nieruchomosci/q-{quote_plus(kw_slug)}/"
        
        params = []
        if "price_min" in filters:
            params.append(f"search[filter_float_price:from]={filters['price_min']}")
        if "price_max" in filters:
            params.append(f"search[filter_float_price:to]={filters['price_max']}")
        if "city" in filters:
            # OLX uses city in URL path typically, but also supports param
            params.append(f"search[city_id]={filters['city']}")
        
        if params:
            url += "?" + "&".join(params)
        
        return url
    
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
            logger.warning("[OLX] Failed to parse __NEXT_DATA__ JSON")
            return []
        
        listings: List[RawListing] = []
        
        # Navigate OLX's data structure
        try:
            # OLX Next.js structure: props.pageProps.data.ads
            page_props = data.get("props", {}).get("pageProps", {})
            ads_data = page_props.get("data", {}).get("ads", [])
            
            if not ads_data:
                # Alternative path
                ads_data = page_props.get("ads", {}).get("data", [])
            
            if not ads_data:
                # Try another path for newer OLX versions
                listing_data = page_props.get("listingData", {})
                ads_data = listing_data.get("ads", [])
            
            for ad in ads_data:
                listing = self._parse_ad_json(ad)
                if listing:
                    listings.append(listing)
                    
        except (KeyError, TypeError) as e:
            logger.warning(f"[OLX] Error navigating __NEXT_DATA__: {e}")
        
        return listings
    
    def _parse_ad_json(self, ad: Dict[str, Any]) -> Optional[RawListing]:
        """Parse a single OLX ad from JSON data."""
        try:
            title = ad.get("title", "")
            if not title:
                return None
            
            # URL
            url = ad.get("url", "")
            if url and not url.startswith("http"):
                url = urljoin(BASE_URL, url)
            if not url:
                slug = ad.get("slug", "")
                ad_id = ad.get("id", "")
                if slug and ad_id:
                    url = f"{BASE_URL}/oferta/{slug}-ID{ad_id}.html"
            
            if not url:
                return None
            
            # Price
            price = None
            price_text = None
            price_data = ad.get("price", {})
            if isinstance(price_data, dict):
                price_text = price_data.get("displayValue", price_data.get("regularPrice", {}).get("value"))
                negotiable = price_data.get("negotiable", False)
                try:
                    price_val = price_data.get("regularPrice", {}).get("value")
                    if price_val:
                        price = float(price_val)
                except (ValueError, TypeError):
                    pass
            elif isinstance(price_data, str):
                price_text = price_data
            
            # Location
            location_data = ad.get("location", {})
            location = None
            city = None
            if isinstance(location_data, dict):
                city_data = location_data.get("city", {})
                city = city_data.get("name", "") if isinstance(city_data, dict) else str(city_data)
                region = location_data.get("region", {})
                region_name = region.get("name", "") if isinstance(region, dict) else ""
                location = f"{city}, {region_name}".strip(", ")
            
            # Params (area, rooms, etc.)
            area = None
            rooms = None
            params = ad.get("params", [])
            if isinstance(params, list):
                for param in params:
                    if isinstance(param, dict):
                        key = param.get("key", "")
                        value = param.get("normalizedValue", param.get("value", ""))
                        if key == "m" or key == "area":
                            try:
                                area = float(str(value).replace(",", "."))
                            except ValueError:
                                pass
                        elif key == "rooms" or key == "number_of_rooms":
                            try:
                                rooms = int(value)
                            except (ValueError, TypeError):
                                pass
            
            # Thumbnail
            photos = ad.get("photos", [])
            thumbnail = None
            if photos and isinstance(photos, list):
                first_photo = photos[0] if photos else {}
                if isinstance(first_photo, dict):
                    thumbnail = first_photo.get("link", first_photo.get("url"))
                elif isinstance(first_photo, str):
                    thumbnail = first_photo
            
            # Description snippet
            description = ad.get("description", "")
            
            # Share detection
            combined = f"{title} {description}".lower()
            is_share = self._detect_share(combined)
            share_fraction = self._extract_fraction(f"{title} {description}")
            
            return RawListing(
                title=title,
                source_url=url,
                portal="olx",
                price=price,
                price_text=price_text,
                location=location,
                city=city,
                area_m2=area,
                rooms=rooms,
                thumbnail_url=thumbnail,
                description=description[:500] if description else None,
                listing_id=str(ad.get("id", "")),
                is_share=is_share,
                share_fraction=share_fraction,
            )
            
        except Exception as e:
            logger.warning(f"[OLX] Error parsing ad JSON: {e}")
            return None
    
    def _parse_html_results(self, html: str) -> List[RawListing]:
        """Fallback HTML parsing for OLX."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        listings: List[RawListing] = []
        
        # OLX card selectors
        cards = soup.select(
            "[data-cy='l-card'], .offer-wrapper, "
            "[data-testid='listing-grid'] > div"
        )
        
        for card in cards:
            listing = self.parse_listing(str(card))
            if listing:
                listings.append(listing)
        
        return listings
    
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse a single OLX listing card HTML (fallback)."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Title
        title_el = soup.select_one(
            "[data-cy='ad-card-title'], h6, .offer-wrapper__title"
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None
        
        # URL
        link_el = soup.select_one("a[href*='/oferta/'], a[href*='/d/']")
        href = link_el.get("href", "") if link_el else ""
        source_url = urljoin(BASE_URL, href) if href else ""
        if not source_url:
            return None
        
        # Price
        price_el = soup.select_one(
            "[data-testid='ad-price'], .price, p[data-testid='ad-price']"
        )
        price_text = price_el.get_text(strip=True) if price_el else None
        price = self._parse_price(price_text)
        
        # Location
        loc_el = soup.select_one(
            "[data-testid='location-date'], .breadcrumb, .offer-wrapper__location"
        )
        location = loc_el.get_text(strip=True) if loc_el else None
        
        is_share = self._detect_share(title)
        share_fraction = self._extract_fraction(title)
        
        return RawListing(
            title=title,
            source_url=source_url,
            portal="olx",
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
