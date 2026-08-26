"""
Smart results ranking and filtering for property share listings.

Pipeline: raw listings → score → classify → rank → tier → present

Tiers:
  🔥 PEWNY (score 75+) — syndyk+fraction, multiple signals
  ⭐ PRAWDOPODOBNY (50-74) — strong indicators without full confirmation
  ❓ MOŻLIWY (25-49) — single weak signal, needs manual review

Filters (post-scoring):
  - source: syndyk | spadek | licytacja | rozwód | inne
  - property_type: mieszkanie | dom | działka | garaż | inne
  - fraction_size: duży (≥1/2) | średni (1/3-1/4) | mały (<1/4)
  - price_bracket: do_30k | 30_100k | 100_300k | powyżej_300k
  - city / voivodeship (from scraper data)

Ranking within tier:
  1. Fraction clarity (known fraction > unknown)
  2. Price attractiveness (lower = more interesting for buyer)
  3. Recency (newer listings first)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class Tier(str, Enum):
    PEWNY = "pewny"           # 75+ score
    PRAWDOPODOBNY = "prawdopodobny"  # 50-74
    MOZLIWY = "mozliwy"       # 25-49


class Source(str, Enum):
    SYNDYK = "syndyk"
    SPADEK = "spadek"
    LICYTACJA = "licytacja"
    ROZWOD = "rozwód"
    INNE = "inne"


class PropertyType(str, Enum):
    MIESZKANIE = "mieszkanie"
    DOM = "dom"
    DZIALKA = "działka"
    GARAZ = "garaż"
    INNE = "inne"


class FractionSize(str, Enum):
    DUZY = "duży"        # >= 1/2
    SREDNI = "średni"    # 1/3 - 1/4
    MALY = "mały"        # < 1/4


class PriceBracket(str, Enum):
    MICRO = "do_30k"
    SMALL = "30_100k"
    MEDIUM = "100_300k"
    PREMIUM = "powyżej_300k"


@dataclass
class ClassifiedListing:
    """A listing enriched with classification metadata."""
    raw: Dict[str, Any]
    score: int
    tier: Tier
    source: Source
    property_type: PropertyType
    fraction: Optional[str] = None
    fraction_size: Optional[FractionSize] = None
    price_bracket: Optional[PriceBracket] = None
    attractiveness: float = 0.0  # 0-1, higher = better deal

    @property
    def title(self) -> str:
        return self.raw.get("title", "")

    @property
    def price(self) -> Optional[float]:
        return self.raw.get("price")

    @property
    def url(self) -> str:
        return self.raw.get("url", "")

    @property
    def city(self) -> str:
        return self.raw.get("city", "")

    @property
    def portal(self) -> str:
        return self.raw.get("source_portal", "")


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

_RE_SYNDYK = re.compile(r'syndyk|upad[łl]o[śs]|masa upad', re.I)
_RE_SPADEK = re.compile(r'spadek|spadku|dziedzicz|odziedzicz', re.I)
_RE_LICYTACJA = re.compile(r'licytac|komorni|egzekuc', re.I)
_RE_ROZWOD = re.compile(r'rozw[oó]d|podzia[łl]\s*maj[aą]tk', re.I)

_RE_MIESZKANIE = re.compile(r'mieszkan|lokal\s*mieszk', re.I)
_RE_DOM = re.compile(r'\bdom\b|\bdomu\b|zabudow', re.I)
_RE_DZIALKA = re.compile(r'dzia[łl]k|grunt', re.I)
_RE_GARAZ = re.compile(r'gara[żz]|hal[aie]\s*gara', re.I)


def _classify_source(text: str) -> Source:
    if _RE_SYNDYK.search(text): return Source.SYNDYK
    if _RE_SPADEK.search(text): return Source.SPADEK
    if _RE_LICYTACJA.search(text): return Source.LICYTACJA
    if _RE_ROZWOD.search(text): return Source.ROZWOD
    return Source.INNE


def _classify_property_type(text: str) -> PropertyType:
    if _RE_MIESZKANIE.search(text): return PropertyType.MIESZKANIE
    if _RE_DOM.search(text): return PropertyType.DOM
    if _RE_DZIALKA.search(text): return PropertyType.DZIALKA
    if _RE_GARAZ.search(text): return PropertyType.GARAZ
    return PropertyType.INNE


def _classify_fraction_size(fraction: Optional[str]) -> Optional[FractionSize]:
    if not fraction:
        return None
    m = re.match(r'(\d+)/(\d+)', fraction)
    if not m:
        return None
    num, den = int(m.group(1)), int(m.group(2))
    if den == 0:
        return None
    ratio = num / den
    if ratio >= 0.5:
        return FractionSize.DUZY
    elif ratio >= 0.25:
        return FractionSize.SREDNI
    else:
        return FractionSize.MALY


def _classify_price_bracket(price: Optional[float]) -> Optional[PriceBracket]:
    if not price or price < 1000:
        return None
    if price < 30_000:
        return PriceBracket.MICRO
    elif price < 100_000:
        return PriceBracket.SMALL
    elif price < 300_000:
        return PriceBracket.MEDIUM
    else:
        return PriceBracket.PREMIUM


def _calculate_attractiveness(listing: Dict, score: int, fraction: Optional[str]) -> float:
    """
    Attractiveness score 0-1. Higher = better opportunity for buyer.
    
    Factors:
    - Lower price = more attractive
    - Known fraction = more transparent
    - Higher share score = more certain
    - Syndyk source = often below market
    """
    attractiveness = 0.0
    price = listing.get("price")
    
    # Price factor (lower = better, capped at 500k)
    if price and price > 1000:
        price_factor = max(0, 1.0 - (price / 500_000))
        attractiveness += price_factor * 0.35
    
    # Score certainty factor
    attractiveness += (score / 100) * 0.30
    
    # Known fraction bonus
    if fraction:
        attractiveness += 0.15
        # Larger fraction = more attractive (1/2 > 1/12)
        m = re.match(r'(\d+)/(\d+)', fraction)
        if m:
            ratio = int(m.group(1)) / int(m.group(2))
            attractiveness += ratio * 0.10
    
    # Syndyk bonus (usually below market price)
    text = (listing.get("title", "") + " " + listing.get("raw_description", "")).lower()
    if "syndyk" in text:
        attractiveness += 0.10
    
    return min(1.0, attractiveness)


# ---------------------------------------------------------------------------
# Main classification + ranking pipeline
# ---------------------------------------------------------------------------

def classify_and_rank(
    scored_listings: List[Dict[str, Any]],
    min_score: int = 25,
) -> List[ClassifiedListing]:
    """
    Classify scored listings into tiers with metadata.
    
    Args:
        scored_listings: Listings with 'score' and 'is_share' keys (from ScraperManager)
        min_score: Minimum score to include (default: 25 = is_share threshold)
    
    Returns:
        List of ClassifiedListings sorted by tier (🔥>⭐>❓) then attractiveness DESC
    """
    classified: List[ClassifiedListing] = []
    
    for listing in scored_listings:
        score = listing.get("score", 0)
        if score < min_score:
            continue
        
        # Determine tier
        if score >= 75:
            tier = Tier.PEWNY
        elif score >= 50:
            tier = Tier.PRAWDOPODOBNY
        else:
            tier = Tier.MOZLIWY
        
        # Classify metadata from text
        text = (listing.get("title", "") + " " + listing.get("raw_description", "")).lower()
        source = _classify_source(text)
        prop_type = _classify_property_type(listing.get("title", ""))
        
        # Fraction from scorer
        fraction = listing.get("fraction_detected") or _extract_fraction(text)
        fraction_size = _classify_fraction_size(fraction)
        
        # Price bracket
        price_bracket = _classify_price_bracket(listing.get("price"))
        
        # Attractiveness
        attractiveness = _calculate_attractiveness(listing, score, fraction)
        
        classified.append(ClassifiedListing(
            raw=listing,
            score=score,
            tier=tier,
            source=source,
            property_type=prop_type,
            fraction=fraction,
            fraction_size=fraction_size,
            price_bracket=price_bracket,
            attractiveness=attractiveness,
        ))
    
    # Sort: tier priority (PEWNY first), then attractiveness DESC
    tier_order = {Tier.PEWNY: 0, Tier.PRAWDOPODOBNY: 1, Tier.MOZLIWY: 2}
    classified.sort(key=lambda x: (tier_order[x.tier], -x.attractiveness))
    
    return classified


def _extract_fraction(text: str) -> Optional[str]:
    """Extract fraction from text if present."""
    m = re.search(r'\b(\d+)\s*/\s*(\d+)\b', text)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if den >= 2 and num < den and num > 0:
            return f"{num}/{den}"
    # Also handle ½ ⅓ ¼ unicode fractions
    fraction_map = {'½': '1/2', '⅓': '1/3', '¼': '1/4', '¾': '3/4', '⅔': '2/3'}
    for char, frac in fraction_map.items():
        if char in text:
            return frac
    return None


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_classified(
    listings: List[ClassifiedListing],
    source: Optional[Source] = None,
    property_type: Optional[PropertyType] = None,
    fraction_size: Optional[FractionSize] = None,
    price_bracket: Optional[PriceBracket] = None,
    city: Optional[str] = None,
    voivodeship: Optional[str] = None,
    min_tier: Optional[Tier] = None,
) -> List[ClassifiedListing]:
    """Filter classified listings by criteria."""
    result = listings
    
    if min_tier:
        tier_order = {Tier.PEWNY: 0, Tier.PRAWDOPODOBNY: 1, Tier.MOZLIWY: 2}
        max_tier_val = tier_order[min_tier]
        result = [l for l in result if tier_order[l.tier] <= max_tier_val]
    
    if source:
        result = [l for l in result if l.source == source]
    
    if property_type:
        result = [l for l in result if l.property_type == property_type]
    
    if fraction_size:
        result = [l for l in result if l.fraction_size == fraction_size]
    
    if price_bracket:
        result = [l for l in result if l.price_bracket == price_bracket]
    
    if city:
        city_lower = city.lower()
        result = [l for l in result if city_lower in l.city.lower()]
    
    if voivodeship:
        voiv_lower = voivodeship.lower()
        result = [l for l in result if voiv_lower in l.raw.get("voivodeship", "").lower()]
    
    return result


# ---------------------------------------------------------------------------
# Presentation formatting
# ---------------------------------------------------------------------------

def format_summary(classified: List[ClassifiedListing]) -> str:
    """Format a summary for Telegram message."""
    if not classified:
        return "📭 Nie znaleziono udziałów spełniających kryteria."
    
    pewny = [l for l in classified if l.tier == Tier.PEWNY]
    prawdopodobny = [l for l in classified if l.tier == Tier.PRAWDOPODOBNY]
    mozliwy = [l for l in classified if l.tier == Tier.MOZLIWY]
    
    lines = [f"📊 <b>Znaleziono {len(classified)} udziałów:</b>\n"]
    
    if pewny:
        lines.append(f"🔥 Pewne: <b>{len(pewny)}</b>")
    if prawdopodobny:
        lines.append(f"⭐ Prawdopodobne: <b>{len(prawdopodobny)}</b>")
    if mozliwy:
        lines.append(f"❓ Możliwe: <b>{len(mozliwy)}</b>")
    
    # Price range of real shares
    prices = [l.price for l in classified if l.price and l.price > 1000]
    if prices:
        lines.append(f"\n💰 Ceny: {min(prices):,.0f} – {max(prices):,.0f} PLN")
    
    # Sources breakdown
    from collections import Counter
    sources = Counter(l.source.value for l in classified)
    if sources:
        src_parts = [f"{v}× {k}" for k, v in sources.most_common(3)]
        lines.append(f"📋 Źródła: {', '.join(src_parts)}")
    
    return "\n".join(lines)


def format_listing_card(listing: ClassifiedListing, index: int = 1) -> str:
    """Format a single listing for Telegram display."""
    tier_icon = {"pewny": "🔥", "prawdopodobny": "⭐", "mozliwy": "❓"}
    icon = tier_icon.get(listing.tier.value, "")
    
    from html import escape
    safe_title = escape(listing.title[:60])
    parts = [f"{icon} <b>{index}. {safe_title}</b>"]
    
    if listing.price:
        try:
            parts.append(f"💰 {float(listing.price):,.0f} PLN")
        except (ValueError, TypeError):
            parts.append(f"💰 {listing.price} PLN")
    
    if listing.fraction:
        parts.append(f"📐 Udział: {listing.fraction}")
    
    meta = []
    if listing.city:
        meta.append(listing.city)
    if listing.source != Source.INNE:
        meta.append(listing.source.value)
    if listing.property_type != PropertyType.INNE:
        meta.append(listing.property_type.value)
    if meta:
        parts.append(f"📍 {' • '.join(meta)}")
    
    parts.append(f"🔗 <a href=\"{listing.url}\">Otwórz ogłoszenie</a> (live)")
    
    return "\n".join(parts)


def format_results_page(
    listings: List[ClassifiedListing],
    page: int = 0,
    page_size: int = 5,
) -> Tuple[str, int]:
    """
    Format a page of results.
    
    Returns: (formatted_text, total_pages)
    """
    total_pages = max(1, (len(listings) + page_size - 1) // page_size)
    start = page * page_size
    end = start + page_size
    page_items = listings[start:end]
    
    if not page_items:
        return "📭 Brak wyników na tej stronie.", total_pages
    
    lines = [f"📋 <b>Wyniki ({page+1}/{total_pages})</b>\n"]
    
    for i, listing in enumerate(page_items, start=start + 1):
        lines.append(format_listing_card(listing, i))
        lines.append("")  # spacing
    
    text = "\n".join(lines)
    # Telegram message limit is 4096 chars
    if len(text) > 4000:
        text = text[:3950] + "\n\n… (skrócono, użyj ▶ aby zobaczyć więcej)"
    return text, total_pages
