"""
Allegro.pl scraper - REST API with OAuth2 token.

Allegro provides a public REST API for searching listings.
Uses OAuth2 client_credentials flow for authentication.
API docs: https://developer.allegro.pl/
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from scraper.base import BaseScraper, RawListing

logger = logging.getLogger(__name__)

# Allegro API endpoints
ALLEGRO_API_URL = "https://api.allegro.pl"
ALLEGRO_AUTH_URL = "https://allegro.pl/auth/oauth/token"
ALLEGRO_SANDBOX_API_URL = "https://api.allegro.pl.allegrosandbox.pl"
ALLEGRO_SANDBOX_AUTH_URL = "https://allegro.pl.allegrosandbox.pl/auth/oauth/token"


class AllegroScraper(BaseScraper):
    """Allegro.pl REST API scraper with OAuth2 authentication."""
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        sandbox: bool = False,
        **kwargs,
    ):
        super().__init__(stealth_layer=1, use_tor=False, **kwargs)
        self.client_id = client_id or os.environ.get("ALLEGRO_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("ALLEGRO_CLIENT_SECRET", "")
        self.sandbox = sandbox
        self._token: Optional[str] = None
        self._token_expires: float = 0
        
        self.api_url = ALLEGRO_SANDBOX_API_URL if sandbox else ALLEGRO_API_URL
        self.auth_url = ALLEGRO_SANDBOX_AUTH_URL if sandbox else ALLEGRO_AUTH_URL
    
    def get_portal_name(self) -> str:
        return "Allegro"
    
    async def _get_token(self) -> Optional[str]:
        """Get OAuth2 access token using client_credentials flow."""
        if self._token and time.time() < self._token_expires:
            return self._token
        
        if not self.client_id or not self.client_secret:
            logger.error("[Allegro] Missing API credentials (ALLEGRO_CLIENT_ID/ALLEGRO_CLIENT_SECRET)")
            return None
        
        try:
            import httpx
        except ImportError:
            logger.error("[Allegro] httpx not available")
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.auth_url,
                    data={"grant_type": "client_credentials"},
                    auth=(self.client_id, self.client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )
                
                if response.status_code != 200:
                    logger.error(f"[Allegro] Auth failed: {response.status_code} {response.text}")
                    return None
                
                data = response.json()
                self._token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self._token_expires = time.time() + expires_in - 60  # 60s buffer
                
                logger.info("[Allegro] OAuth2 token obtained")
                return self._token
                
        except Exception as e:
            logger.error(f"[Allegro] Auth error: {e}")
            return None
    
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """Search Allegro for real estate listings via REST API."""
        results: List[RawListing] = []
        filters = filters or {}
        
        token = await self._get_token()
        if not token:
            logger.warning("[Allegro] No token, skipping search")
            return results
        
        try:
            import httpx
        except ImportError:
            logger.error("[Allegro] httpx not available")
            return results
        
        for keyword in keywords:
            params = self._build_api_params(keyword, filters)
            logger.info(f"[Allegro] API search: {keyword}")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.api_url}/offers/listing",
                        params=params,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.allegro.public.v1+json",
                        },
                        timeout=self.timeout,
                    )
                    
                    if response.status_code == 401:
                        # Token expired, refresh
                        self._token = None
                        token = await self._get_token()
                        if not token:
                            continue
                        response = await client.get(
                            f"{self.api_url}/offers/listing",
                            params=params,
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Accept": "application/vnd.allegro.public.v1+json",
                            },
                            timeout=self.timeout,
                        )
                    
                    if response.status_code != 200:
                        logger.warning(f"[Allegro] API error: {response.status_code}")
                        continue
                    
                    data = response.json()
                    listings = self._parse_api_response(data)
                    results.extend(listings)
                    logger.info(f"[Allegro] Found {len(listings)} listings for '{keyword}'")
                    
            except Exception as e:
                logger.error(f"[Allegro] Search error: {e}")
                continue
        
        return results
    
    def _build_api_params(self, keyword: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Build Allegro API search parameters."""
        params: Dict[str, Any] = {
            "phrase": keyword,
            "category.id": "100249",  # Nieruchomości category
            "sort": "-relevance",
            "limit": 50,
        }
        
        if "price_min" in filters:
            params["price.from"] = filters["price_min"]
        if "price_max" in filters:
            params["price.to"] = filters["price_max"]
        if "city" in filters:
            params["location.city"] = filters["city"]
        
        return params
    
    def _parse_api_response(self, data: Dict[str, Any]) -> List[RawListing]:
        """Parse Allegro API response into listings."""
        listings: List[RawListing] = []
        
        # Allegro API returns items in different groups
        item_groups = ["promoted", "regular"]
        
        for group in item_groups:
            items = data.get("items", {}).get(group, [])
            for item in items:
                listing = self._parse_api_item(item)
                if listing:
                    listings.append(listing)
        
        # Also check searchMeta for alternative format
        if not listings:
            offers = data.get("offers", data.get("items", []))
            if isinstance(offers, list):
                for item in offers:
                    listing = self._parse_api_item(item)
                    if listing:
                        listings.append(listing)
        
        return listings
    
    def _parse_api_item(self, item: Dict[str, Any]) -> Optional[RawListing]:
        """Parse a single Allegro API item."""
        try:
            title = item.get("name", "")
            if not title:
                return None
            
            # URL
            item_id = item.get("id", "")
            url = f"https://allegro.pl/oferta/{item_id}" if item_id else ""
            if not url:
                return None
            
            # Price
            price = None
            price_text = None
            selling_mode = item.get("sellingMode", {})
            price_data = selling_mode.get("price", selling_mode.get("fixedPrice", {}))
            if isinstance(price_data, dict):
                try:
                    price = float(price_data.get("amount", 0))
                    currency = price_data.get("currency", "PLN")
                    price_text = f"{price} {currency}"
                except (ValueError, TypeError):
                    pass
            
            # Location
            location = None
            delivery = item.get("delivery", {})
            if isinstance(delivery, dict):
                location_data = delivery.get("availableForFree")
            # Try seller location
            seller = item.get("seller", {})
            if isinstance(seller, dict):
                seller_city = seller.get("city")
                if seller_city:
                    location = seller_city
            
            # Thumbnail
            thumbnail = None
            images = item.get("images", [])
            if images and isinstance(images, list):
                first_img = images[0]
                if isinstance(first_img, dict):
                    thumbnail = first_img.get("url")
                elif isinstance(first_img, str):
                    thumbnail = first_img
            
            # Description from parameters
            description_parts = []
            params = item.get("parameters", [])
            if isinstance(params, list):
                for param in params:
                    if isinstance(param, dict):
                        name = param.get("name", "")
                        values = param.get("values", [])
                        if values:
                            description_parts.append(f"{name}: {', '.join(str(v) for v in values)}")
            
            description = "; ".join(description_parts) if description_parts else None
            
            # Share detection
            combined = f"{title} {description or ''}".lower()
            is_share = self._detect_share(combined)
            share_fraction = self._extract_fraction(f"{title} {description or ''}")
            
            return RawListing(
                title=title,
                source_url=url,
                portal="allegro",
                price=price,
                price_text=price_text,
                location=location,
                description=description,
                listing_id=str(item_id),
                thumbnail_url=thumbnail,
                is_share=is_share,
                share_fraction=share_fraction,
            )
            
        except Exception as e:
            logger.warning(f"[Allegro] Error parsing item: {e}")
            return None
    
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse listing - not used for API-based scraper."""
        # Allegro uses REST API, not HTML parsing
        return None
    
    def _detect_share(self, text: str) -> bool:
        text_lower = text.lower()
        share_keywords = [
            "udział", "udzial", "1/2", "1/3", "1/4", "1/6", "1/8",
            "współwłasność", "wspolwlasnosc",
        ]
        return any(kw in text_lower for kw in share_keywords)
    
    def _extract_fraction(self, text: str) -> Optional[str]:
        import re
        match = re.search(r"(\d+/\d+)", text)
        return match.group(1) if match else None
