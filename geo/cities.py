"""Polish cities geocoding - lookup city coordinates and voivodeships.

Loads city data from a bundled JSON file containing the top 1000 Polish cities
with their coordinates, voivodeship, and population data.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import unicodedata

logger = logging.getLogger(__name__)

# Path to bundled cities data
_DATA_DIR = Path(__file__).parent.parent / "data"
_CITIES_FILE = _DATA_DIR / "cities.json"

# Module-level cache
_cities_data: Optional[List[Dict]] = None
_cities_index: Optional[Dict[str, Dict]] = None

# All 16 Polish voivodeships
VOIVODESHIPS: List[str] = [
    "dolnośląskie",
    "kujawsko-pomorskie",
    "lubelskie",
    "lubuskie",
    "łódzkie",
    "małopolskie",
    "mazowieckie",
    "opolskie",
    "podkarpackie",
    "podlaskie",
    "pomorskie",
    "śląskie",
    "świętokrzyskie",
    "warmińsko-mazurskie",
    "wielkopolskie",
    "zachodniopomorskie",
]


def _normalize_city_name(name: str) -> str:
    """Normalize city name for lookup: lowercase, strip diacritics for matching.

    Args:
        name: City name to normalize.

    Returns:
        Normalized name (lowercase, no leading/trailing whitespace).
    """
    return name.lower().strip()


def _strip_diacritics(text: str) -> str:
    """Strip Polish diacritics for fuzzy matching.

    Args:
        text: Text with potential diacritics.

    Returns:
        Text with diacritics replaced by base characters.
    """
    # Polish-specific replacements
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l",
        "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    }
    result = text.lower()
    for src, dst in replacements.items():
        result = result.replace(src, dst)
    return result


def _load_cities() -> None:
    """Load cities data from JSON file into module cache."""
    global _cities_data, _cities_index

    if _cities_data is not None:
        return

    if not _CITIES_FILE.exists():
        logger.warning(f"Cities data file not found: {_CITIES_FILE}")
        _cities_data = []
        _cities_index = {}
        return

    try:
        with open(_CITIES_FILE, "r", encoding="utf-8") as f:
            _cities_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load cities data: {e}")
        _cities_data = []
        _cities_index = {}
        return

    # Build lookup index (both with and without diacritics)
    _cities_index = {}
    for city in _cities_data:
        name_lower = _normalize_city_name(city["name"])
        _cities_index[name_lower] = city
        # Also index without diacritics for fuzzy matching
        name_ascii = _strip_diacritics(city["name"])
        if name_ascii != name_lower:
            _cities_index[name_ascii] = city

    logger.info(f"Loaded {len(_cities_data)} cities from {_CITIES_FILE}")


def get_city_coords(city_name: str) -> Optional[Tuple[float, float]]:
    """Get coordinates for a Polish city.

    Handles both proper Polish names (with diacritics) and simplified
    ASCII versions (e.g., 'Gdansk' matches 'Gdańsk').

    Args:
        city_name: City name to look up.

    Returns:
        Tuple of (latitude, longitude) or None if city not found.
    """
    _load_cities()

    if not _cities_index:
        return None

    # Try exact match first
    normalized = _normalize_city_name(city_name)
    city = _cities_index.get(normalized)

    if city is None:
        # Try without diacritics
        ascii_name = _strip_diacritics(city_name)
        city = _cities_index.get(ascii_name)

    if city is None:
        return None

    return (city["lat"], city["lon"])


def search_city(query: str) -> List[Dict]:
    """Search for cities matching a query (autocomplete-style).

    Matches city names that start with or contain the query string.
    Returns results sorted by population (largest first).

    Args:
        query: Search query (minimum 2 characters).

    Returns:
        List of matching city dicts (name, lat, lon, voivodeship, population).
        Maximum 10 results.
    """
    _load_cities()

    if not _cities_data or len(query) < 2:
        return []

    query_lower = _normalize_city_name(query)
    query_ascii = _strip_diacritics(query)

    matches = []
    for city in _cities_data:
        name_lower = _normalize_city_name(city["name"])
        name_ascii = _strip_diacritics(city["name"])

        # Check if query matches start of name (with or without diacritics)
        if name_lower.startswith(query_lower) or name_ascii.startswith(query_ascii):
            matches.append(city)
        elif query_lower in name_lower or query_ascii in name_ascii:
            matches.append(city)

    # Sort by population (largest first) and limit results
    matches.sort(key=lambda c: c.get("population", 0), reverse=True)
    return matches[:10]


def get_voivodeships() -> List[str]:
    """Get list of all 16 Polish voivodeships.

    Returns:
        List of voivodeship names in Polish (lowercase).
    """
    return VOIVODESHIPS.copy()


def get_cities_in_voivodeship(voivodeship: str) -> List[Dict]:
    """Get all cities in a specific voivodeship.

    Args:
        voivodeship: Voivodeship name (case-insensitive).

    Returns:
        List of city dicts in that voivodeship, sorted by population.
    """
    _load_cities()

    if not _cities_data:
        return []

    voiv_lower = voivodeship.lower().strip()
    matches = [
        city for city in _cities_data
        if city.get("voivodeship", "").lower() == voiv_lower
    ]

    matches.sort(key=lambda c: c.get("population", 0), reverse=True)
    return matches
