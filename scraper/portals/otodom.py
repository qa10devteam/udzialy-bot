"""
Otodom.pl scraper - Layer 5 (nodriver CDP, no Tor).

VERIFIED: Otodom works with nodriver from datacenter IPs without Tor.
Tor exit nodes are BLOCKED by CloudFront — use_tor=False is mandatory.
Otodom strips 'description' search param server-side, so we fetch
broad results and filter locally with PropertyShareScorer.

Data: __NEXT_DATA__ JSON → props.pageProps.data.searchAds (list of ads).
URL pattern: https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska?page={n}
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from scraper.base import BaseScraper, RawListing
from scraper.stealth import fetch_with_stealth
from detector.scorer import PropertyShareScorer

logger = logging.getLogger(__name__)

BASE_URL = "https://www.otodom.pl"
SEARCH_URL_TEMPLATE = (
    "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska?page={page}"
)
MAX_PAGES = 2


class OtodomScraper(BaseScraper):
    """Otodom.pl scraper using nodriver (Layer 5) without Tor.

    Otodom strips description search server-side, so we fetch general
    listing pages and filter locally using PropertyShareScorer.
    """

    def __init__(self, **kwargs):
        # Layer 5 = nodriver, no Tor (CF blocks Tor exit nodes)
        kwargs.setdefault("use_tor", False)
        kwargs.setdefault("timeout", 30.0)
        super().__init__(stealth_layer=5, **kwargs)
        self.scorer = PropertyShareScorer()

    def get_portal_name(self) -> str:
        return "Otodom"

    def get_portal_config(self) -> Dict[str, Any]:
        """Override to ensure no Tor and layer 5."""
        return {
            "portal_name": self.get_portal_name(),
            "stealth_layer": 5,
            "use_tor": False,
            "timeout": 30,
        }

    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[dict]:
        """
        Search Otodom for property share listings.

        Fetches pages 1-2 of general listings, then filters locally
        using scorer against provided keywords.

        Args:
            keywords: List of search terms (used for local filtering)
            filters: Optional filters dict

        Returns:
            List of dicts with: title, price, city, voivodeship, url,
            source_portal, raw_description
        """
        results: List[dict] = []
        filters = filters or {}

        for page in range(1, MAX_PAGES + 1):
            url = SEARCH_URL_TEMPLATE.format(page=page)
            logger.info(f"[Otodom] Fetching page {page}: {url}")

            html = await fetch_with_stealth(url, self.get_portal_config())
            if not html:
                logger.warning(f"[Otodom] No response for page {page}")
                break

            page_results, total_pages = self._parse_next_data(html)
            if not page_results:
                logger.info(f"[Otodom] No results on page {page}, stopping")
                break

            results.extend(page_results)
            logger.info(
                f"[Otodom] Page {page}/{total_pages}: "
                f"{len(page_results)} listings extracted"
            )

            # Don't exceed available pages
            if page >= total_pages:
                break

        # Filter locally using scorer against keywords
        if keywords:
            filtered = self._filter_by_keywords(results, keywords)
            logger.info(
                f"[Otodom] Filtered {len(results)} -> {len(filtered)} "
                f"matching keywords: {keywords}"
            )
            return filtered

        return results

    def _parse_next_data(self, html: str) -> tuple:
        """
        Extract listings from __NEXT_DATA__ JSON.

        Returns:
            Tuple of (list_of_dicts, total_pages)
        """
        match = re.search(
            r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not match:
            logger.warning("[Otodom] __NEXT_DATA__ not found in HTML")
            return [], 0

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"[Otodom] Failed to parse __NEXT_DATA__: {e}")
            return [], 0

        listings: List[dict] = []
        total_pages = 0

        try:
            page_props = data["props"]["pageProps"]["data"]
            search_ads = page_props.get("searchAds", [])

            # Get pagination info
            pagination = page_props.get("pagination", {})
            total_pages = pagination.get("totalPages", 1)

            if isinstance(search_ads, dict):
                # Sometimes searchAds is a dict with items key
                items = search_ads.get("items", search_ads.get("ads", []))
            elif isinstance(search_ads, list):
                items = search_ads
            else:
                items = []

            for item in items:
                listing = self._parse_item(item)
                if listing:
                    listings.append(listing)

        except (KeyError, TypeError, AttributeError) as e:
            logger.warning(f"[Otodom] Error navigating __NEXT_DATA__: {e}")

        return listings, total_pages

    def _parse_item(self, item: Dict[str, Any]) -> Optional[dict]:
        """Parse a single Otodom listing from JSON into result dict."""
        try:
            title = item.get("title", "")
            if not title:
                return None

            # URL from slug
            slug = item.get("slug", "")
            if not slug:
                return None
            url = f"{BASE_URL}/pl/oferta/{slug}"

            # Price
            price = None
            total_price = item.get("totalPrice", {})
            if isinstance(total_price, dict):
                price = total_price.get("value")
            elif isinstance(total_price, (int, float)):
                price = float(total_price)

            # Location
            city = None
            voivodeship = None
            location_data = item.get("location", {})
            if isinstance(location_data, dict):
                address = location_data.get("address", {})
                if isinstance(address, dict):
                    city_data = address.get("city", {})
                    city = (
                        city_data.get("name", "")
                        if isinstance(city_data, dict)
                        else str(city_data)
                    )
                    province_data = address.get("province", {})
                    voivodeship = (
                        province_data.get("name", "")
                        if isinstance(province_data, dict)
                        else str(province_data) if province_data else None
                    )

            # Area and rooms
            area = item.get("areaInM2", item.get("area"))
            rooms = item.get("roomsNumber", item.get("rooms"))

            # Description (may be absent in list view)
            description = item.get("description", "") or title

            return {
                "title": title,
                "price": price,
                "city": city or "",
                "voivodeship": voivodeship or "",
                "url": url,
                "source_portal": "otodom",
                "raw_description": description,
                "area": area,
                "rooms": rooms,
            }

        except Exception as e:
            logger.warning(f"[Otodom] Error parsing item: {e}")
            return None

    def _filter_by_keywords(
        self, listings: List[dict], keywords: List[str]
    ) -> List[dict]:
        """Filter listings locally using PropertyShareScorer.

        Otodom strips search keywords server-side, so we must filter
        the broad results ourselves.
        """
        filtered: List[dict] = []

        for listing in listings:
            title = listing.get("title", "")
            description = listing.get("raw_description", "")

            # Score with PropertyShareScorer
            result = self.scorer.score(title, description)
            if result.is_share:
                filtered.append(listing)
                continue

            # Also check direct keyword match in title
            title_lower = title.lower()
            for kw in keywords:
                if kw.lower() in title_lower:
                    filtered.append(listing)
                    break

        return filtered

    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Parse a single listing HTML (legacy interface, not used)."""
        return None
