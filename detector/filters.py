"""Post-scrape filtering functions for property share listings.

Provides filtering by score threshold, geographic location, and price range.
These functions operate on lists of listing dictionaries or objects with
appropriate attributes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Union

from geo.distance import haversine
from geo.cities import get_city_coords


class ListingLike(Protocol):
    """Protocol for objects that behave like a listing."""

    score: int
    latitude: Optional[float]
    longitude: Optional[float]
    price: Optional[float]
    voivodeship: Optional[str]
    city: Optional[str]


ListingItem = Union[Dict[str, Any], Any]


def _get_attr(item: ListingItem, key: str, default: Any = None) -> Any:
    """Get attribute from dict or object.

    Args:
        item: Dictionary or object to get attribute from.
        key: Attribute/key name.
        default: Default value if not found.

    Returns:
        The attribute value or default.
    """
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def filter_by_score(
    listings: List[ListingItem], min_score: int = 50
) -> List[ListingItem]:
    """Filter listings by minimum confidence score.

    Args:
        listings: List of listing dicts or objects.
        min_score: Minimum score threshold (default 50).

    Returns:
        Filtered list of listings with score >= min_score.
    """
    if not listings:
        return []

    return [
        listing
        for listing in listings
        if (_get_attr(listing, "score", 0) or 0) >= min_score
    ]


def filter_by_location(
    listings: List[ListingItem],
    voivodeship: Optional[str] = None,
    city: Optional[str] = None,
    radius_km: Optional[float] = None,
) -> List[ListingItem]:
    """Filter listings by geographic location.

    Can filter by voivodeship name, city name, or radius from city center.
    If city and radius_km are provided, uses haversine distance from city center.
    If only voivodeship is provided, filters by voivodeship string match.

    Args:
        listings: List of listing dicts or objects.
        voivodeship: Voivodeship name to filter by (e.g., 'pomorskie').
        city: City name for radius filtering.
        radius_km: Radius in km from city center (requires city).

    Returns:
        Filtered list of listings matching location criteria.
    """
    if not listings:
        return []

    result = listings

    # Filter by voivodeship (string match, case-insensitive)
    if voivodeship:
        voiv_lower = voivodeship.lower().strip()
        result = [
            listing
            for listing in result
            if (
                (_get_attr(listing, "voivodeship") or "").lower().strip()
                == voiv_lower
            )
        ]

    # Filter by radius from city center
    if city and radius_km is not None:
        coords = get_city_coords(city)
        if coords is not None:
            center_lat, center_lon = coords
            filtered = []
            for listing in result:
                lat = _get_attr(listing, "latitude")
                lon = _get_attr(listing, "longitude")
                if lat is not None and lon is not None:
                    try:
                        dist = haversine(center_lat, center_lon, float(lat), float(lon))
                        if dist <= radius_km:
                            filtered.append(listing)
                    except (TypeError, ValueError):
                        continue
                else:
                    # If no coords on listing, check city name match
                    listing_city = (_get_attr(listing, "city") or "").lower().strip()
                    if listing_city == city.lower().strip():
                        filtered.append(listing)
            result = filtered

    return result


def filter_by_price(
    listings: List[ListingItem],
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> List[ListingItem]:
    """Filter listings by price range.

    Args:
        listings: List of listing dicts or objects.
        min_price: Minimum price in PLN (inclusive, None = no minimum).
        max_price: Maximum price in PLN (inclusive, None = no maximum).

    Returns:
        Filtered list of listings within price range.
    """
    if not listings:
        return []

    if min_price is None and max_price is None:
        return listings

    result = []
    for listing in listings:
        price = _get_attr(listing, "price")
        if price is None:
            # Include listings without price (user may want to review them)
            continue

        try:
            price_val = float(price)
        except (TypeError, ValueError):
            continue

        if min_price is not None and price_val < min_price:
            continue
        if max_price is not None and price_val > max_price:
            continue

        result.append(listing)

    return result
