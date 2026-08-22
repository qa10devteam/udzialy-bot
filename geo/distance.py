"""Haversine distance calculator for geographic coordinates.

Used to filter listings by radius from a center point (e.g., user's city).
No external dependencies - pure math implementation.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Protocol, Union

# Earth's mean radius in kilometers
EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth.

    Uses the Haversine formula for accurate distance calculation on a sphere.

    Args:
        lat1: Latitude of point 1 in decimal degrees.
        lon1: Longitude of point 1 in decimal degrees.
        lat2: Latitude of point 2 in decimal degrees.
        lon2: Longitude of point 2 in decimal degrees.

    Returns:
        Distance in kilometers.

    Raises:
        ValueError: If coordinates are out of valid range.

    Example:
        >>> haversine(54.5189, 18.5305, 54.3520, 18.6466)  # Gdynia to Gdańsk
        19.2  # approximately
    """
    # Validate inputs
    for lat in (lat1, lat2):
        if not -90 <= lat <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    for lon in (lon1, lon2):
        if not -180 <= lon <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {lon}")

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    # Haversine formula
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


ListingItem = Union[Dict[str, Any], Any]


def _get_attr(item: ListingItem, key: str, default: Any = None) -> Any:
    """Get attribute from dict or object."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def filter_by_radius(
    listings: List[ListingItem],
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> List[ListingItem]:
    """Filter listings by distance from a center point.

    Only includes listings that have valid latitude/longitude coordinates
    and are within the specified radius.

    Args:
        listings: List of listing dicts or objects with 'latitude'/'longitude' attrs.
        center_lat: Center point latitude.
        center_lon: Center point longitude.
        radius_km: Maximum distance in kilometers.

    Returns:
        Filtered list of listings within the radius.
        Each item gets an additional 'distance_km' attribute/key.
    """
    if not listings:
        return []

    if radius_km <= 0:
        return []

    result = []
    for listing in listings:
        lat = _get_attr(listing, "latitude")
        lon = _get_attr(listing, "longitude")

        if lat is None or lon is None:
            continue

        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue

        try:
            distance = haversine(center_lat, center_lon, lat_f, lon_f)
        except ValueError:
            continue

        if distance <= radius_km:
            # Attach distance to the listing
            if isinstance(listing, dict):
                listing_copy = listing.copy()
                listing_copy["distance_km"] = round(distance, 2)
                result.append(listing_copy)
            else:
                # For objects, try to set attribute (may fail for frozen dataclasses)
                try:
                    listing.distance_km = round(distance, 2)
                except AttributeError:
                    pass
                result.append(listing)

    # Sort by distance (closest first)
    result.sort(
        key=lambda x: _get_attr(x, "distance_km", float("inf"))
    )

    return result
