"""
Deep listing parser — fetches FULL listing page and extracts rich data.

Called for candidates that pass Stage 1 (score > 0 from title/snippet).
Extracts:
  - Full description (2000+ chars vs 100 in list view)
  - KW (Księga Wieczysta) number
  - Exact address / district
  - Area in m²
  - Floor / total floors
  - Fraction details from description
  - Photos count
  - Seller type (syndyk/osoba/biuro)

Portal-specific parsers extract structured data from each portal's HTML.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from scraper.stealth import fetch_with_stealth

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Portal-specific full-page parsers
# ---------------------------------------------------------------------------

def _parse_olx_detail(html: str) -> Dict[str, Any]:
    """Extract data from OLX listing detail page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    
    # Full description
    desc_el = soup.select_one("[data-cy='ad_description'] div, .css-1t507yq")
    if desc_el:
        data["full_description"] = desc_el.get_text(" ", strip=True)
    
    # Parameters table
    params = {}
    for row in soup.select("li.css-ox1rxj, [data-testid='ad-params'] li"):
        text = row.get_text(" ", strip=True)
        if ":" in text:
            k, v = text.split(":", 1)
            params[k.strip().lower()] = v.strip()
    data["params"] = params
    
    # Price
    price_el = soup.select_one("[data-testid='ad-price-container'] h3, .css-90xrc0")
    if price_el:
        data["price_text"] = price_el.get_text(strip=True)
    
    return data


def _parse_otodom_detail(html: str) -> Dict[str, Any]:
    """Extract from Otodom (Next.js JSON)."""
    import json
    data = {}
    m = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            next_data = json.loads(m.group(1))
            ad = next_data.get("props", {}).get("pageProps", {}).get("ad", {})
            if ad:
                data["full_description"] = ad.get("description", "")
                data["area"] = ad.get("areaInSquareMeters") or ad.get("areaInM2")
                data["rooms"] = ad.get("roomsNumber")
                data["floor"] = ad.get("floor")
                data["building_floors"] = ad.get("buildingFloorsNum")
                loc = ad.get("location", {})
                if loc:
                    addr = loc.get("address", {})
                    data["city"] = addr.get("city", {}).get("name", "")
                    data["district"] = addr.get("district", {}).get("name", "")
                    data["street"] = addr.get("street", {}).get("name", "")
                data["seller_type"] = ad.get("advertiserType", "")
                data["photos_count"] = len(ad.get("images", []))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return data


def _parse_morizon_detail(html: str) -> Dict[str, Any]:
    """Extract from Morizon detail page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    
    desc_el = soup.select_one(".description__text, .property-description, [itemprop='description']")
    if desc_el:
        data["full_description"] = desc_el.get_text(" ", strip=True)
    
    # Parameters
    for row in soup.select(".property-params tr, .param-list li, .params__item"):
        text = row.get_text(" ", strip=True)
        if "Powierzchnia" in text:
            m = re.search(r'([\d,.]+)\s*m', text)
            if m: data["area"] = float(m.group(1).replace(",", "."))
        elif "Piętro" in text:
            m = re.search(r'(\d+)', text)
            if m: data["floor"] = int(m.group(1))
    
    return data


def _parse_generic_detail(html: str) -> Dict[str, Any]:
    """Generic parser for Domiporta/Gratka/etc."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    
    # Try common description selectors
    for selector in [".description", ".offer-description", "[itemprop='description']",
                     ".text-description", ".ad-description", ".css-1bi2g79"]:
        el = soup.select_one(selector)
        if el and len(el.get_text()) > 100:
            data["full_description"] = el.get_text(" ", strip=True)
            break
    
    # If no selector worked, get largest text block
    if "full_description" not in data:
        paragraphs = soup.find_all("p")
        if paragraphs:
            longest = max(paragraphs, key=lambda p: len(p.get_text()))
            if len(longest.get_text()) > 100:
                data["full_description"] = longest.get_text(" ", strip=True)
    
    return data


# ---------------------------------------------------------------------------
# KW (Księga Wieczysta) extraction
# ---------------------------------------------------------------------------

_RE_KW = re.compile(
    r'(?:KW|księg[aię]\s*wieczysta|ksi[eę]g[aię]\s*wiecz)\s*(?:nr|numer|:)?\s*'
    r'([A-Z]{2}\d[A-Z]?/\d{8}/\d)',
    re.IGNORECASE
)

def _extract_kw(text: str) -> Optional[str]:
    """Extract KW number from text."""
    m = _RE_KW.search(text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Main deep fetch pipeline
# ---------------------------------------------------------------------------

PORTAL_PARSERS = {
    "olx": (_parse_olx_detail, {"stealth_layer": 3, "use_tor": False, "timeout": 15}),
    "otodom": (_parse_otodom_detail, {"stealth_layer": 6, "use_tor": False, "timeout": 30}),
    "morizon": (_parse_morizon_detail, {"stealth_layer": 1, "use_tor": False, "timeout": 15}),
    "domiporta": (_parse_generic_detail, {"stealth_layer": 1, "use_tor": False, "timeout": 15}),
    "gratka": (_parse_generic_detail, {"stealth_layer": 3, "use_tor": False, "timeout": 15}),
    "nieruchomosci_online": (_parse_generic_detail, {"stealth_layer": 1, "use_tor": False, "timeout": 15}),
}

MAX_CONCURRENT_FETCHES = 5


async def deep_fetch_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch full listing page and extract rich data.
    
    Mutates the listing dict — adds:
      - full_description
      - kw_number
      - deep_score (re-scored with full text)
      - enriched metadata (area, floor, seller_type, etc.)
    """
    url = listing.get("url", "")
    portal = listing.get("source_portal", "").lower()
    
    if not url:
        return listing
    
    parser_fn, portal_config = PORTAL_PARSERS.get(portal, (_parse_generic_detail, {"stealth_layer": 1, "use_tor": False, "timeout": 15}))
    portal_config = {**portal_config, "portal_name": portal.title()}
    
    try:
        html = await fetch_with_stealth(url, portal_config)
        if not html:
            return listing
        
        # Parse detail page
        detail = parser_fn(html)
        
        # Merge extracted data
        if full_desc := detail.get("full_description"):
            listing["full_description"] = full_desc[:3000]
            
            # Extract KW
            kw = _extract_kw(full_desc)
            if kw:
                listing["kw_number"] = kw
        
        # Merge other fields (don't overwrite existing)
        for key in ["area", "floor", "building_floors", "rooms", "district",
                    "street", "seller_type", "photos_count"]:
            if key in detail and detail[key] and key not in listing:
                listing[key] = detail[key]
        
        listing["_deep_fetched"] = True
        
    except Exception as e:
        logger.debug(f"Deep fetch failed for {url}: {e}")
    
    return listing


async def deep_fetch_batch(
    listings: List[Dict[str, Any]],
    max_concurrent: int = MAX_CONCURRENT_FETCHES,
) -> List[Dict[str, Any]]:
    """
    Deep fetch a batch of listings in parallel (limited concurrency).
    
    Args:
        listings: Candidate listings to enrich
        max_concurrent: Max simultaneous HTTP requests
    
    Returns:
        Same listings, mutated with deep-fetched data
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _fetch_one(listing):
        async with semaphore:
            result = await deep_fetch_listing(listing)
            await asyncio.sleep(0.5)  # Rate limit: max 2 req/s per portal
            return result
    
    tasks = [_fetch_one(l) for l in listings]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Replace exceptions with original listings
    enriched = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            enriched.append(listings[i])
        else:
            enriched.append(result)
    
    logger.info(
        f"Deep fetch complete: {sum(1 for l in enriched if l.get('_deep_fetched'))}/"
        f"{len(listings)} successfully enriched"
    )
    
    return enriched


def rescore_with_deep_data(listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Re-score listings using full description (after deep fetch).
    
    Listings that gained full_description get re-scored — this can:
    - PROMOTE: listing with "udział" hidden in description → score goes UP
    - DEMOTE: listing where "udział" was in wrong context → score goes DOWN
    """
    from detector.scorer import PropertyShareScorer
    scorer = PropertyShareScorer()
    
    for listing in listings:
        full_desc = listing.get("full_description", "")
        if not full_desc:
            continue
        
        title = listing.get("title", "")
        # Re-score with full description
        result = scorer.score(title, full_desc)
        
        # Only update if score changed significantly
        old_score = listing.get("score", 0)
        new_score = result.score
        
        if abs(new_score - old_score) >= 5:
            listing["score"] = new_score
            listing["is_share"] = result.is_share
            listing["fraction_detected"] = result.fraction_detected
            listing["_rescore_delta"] = new_score - old_score
    
    return listings
