"""Tests for haversine distance calculator.

Tests use known distances between Polish cities for verification.
Distances verified against Google Maps / online calculators.
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import pytest
from geo.distance import haversine, filter_by_radius


class TestHaversine:
    """Test haversine distance calculations with known city pairs."""

    def test_gdynia_to_gdansk(self) -> None:
        """Gdynia to Gdańsk - approximately 19-20 km."""
        # Gdynia: 54.5189, 18.5305
        # Gdańsk: 54.3520, 18.6466
        dist = haversine(54.5189, 18.5305, 54.3520, 18.6466)
        assert 18.0 <= dist <= 21.0, f"Expected ~19-20 km, got {dist:.1f} km"

    def test_gdynia_to_sopot(self) -> None:
        """Gdynia to Sopot - approximately 8-9 km."""
        dist = haversine(54.5189, 18.5305, 54.4418, 18.5601)
        assert 7.0 <= dist <= 10.0, f"Expected ~8-9 km, got {dist:.1f} km"

    def test_warszawa_to_krakow(self) -> None:
        """Warszawa to Kraków - approximately 252-255 km."""
        dist = haversine(52.2297, 21.0122, 50.0647, 19.9450)
        assert 245.0 <= dist <= 260.0, f"Expected ~252 km, got {dist:.1f} km"

    def test_warszawa_to_gdansk(self) -> None:
        """Warszawa to Gdańsk - approximately 283-290 km."""
        dist = haversine(52.2297, 21.0122, 54.3520, 18.6466)
        assert 278.0 <= dist <= 295.0, f"Expected ~284 km, got {dist:.1f} km"

    def test_same_point_zero_distance(self) -> None:
        """Same coordinates should give 0 distance."""
        dist = haversine(54.5189, 18.5305, 54.5189, 18.5305)
        assert dist == 0.0

    def test_antipodal_points(self) -> None:
        """Points on opposite sides of Earth - approximately 20015 km (half circumference)."""
        dist = haversine(0.0, 0.0, 0.0, 180.0)
        assert 20000 <= dist <= 20100

    def test_north_pole_to_south_pole(self) -> None:
        """North to South pole - approximately 20015 km."""
        dist = haversine(90.0, 0.0, -90.0, 0.0)
        assert 20000 <= dist <= 20100

    def test_symmetry(self) -> None:
        """Distance from A to B should equal distance from B to A."""
        dist_ab = haversine(54.5189, 18.5305, 52.2297, 21.0122)
        dist_ba = haversine(52.2297, 21.0122, 54.5189, 18.5305)
        assert abs(dist_ab - dist_ba) < 0.001

    def test_invalid_latitude_raises(self) -> None:
        """Latitude out of range should raise ValueError."""
        with pytest.raises(ValueError, match="Latitude"):
            haversine(91.0, 0.0, 0.0, 0.0)

        with pytest.raises(ValueError, match="Latitude"):
            haversine(0.0, 0.0, -91.0, 0.0)

    def test_invalid_longitude_raises(self) -> None:
        """Longitude out of range should raise ValueError."""
        with pytest.raises(ValueError, match="Longitude"):
            haversine(0.0, 181.0, 0.0, 0.0)

        with pytest.raises(ValueError, match="Longitude"):
            haversine(0.0, 0.0, 0.0, -181.0)


class TestFilterByRadius:
    """Test radius-based listing filtering."""

    def test_filter_within_radius(self) -> None:
        """Listings within radius should be returned."""
        listings = [
            {"id": "1", "latitude": 54.3520, "longitude": 18.6466},  # Gdańsk (~19 km)
            {"id": "2", "latitude": 54.4418, "longitude": 18.5601},  # Sopot (~9 km)
            {"id": "3", "latitude": 52.2297, "longitude": 21.0122},  # Warszawa (~300 km)
        ]

        # Filter 30 km from Gdynia
        result = filter_by_radius(listings, 54.5189, 18.5305, 30.0)
        ids = [r["id"] for r in result]
        assert "1" in ids  # Gdańsk is within 30 km
        assert "2" in ids  # Sopot is within 30 km
        assert "3" not in ids  # Warszawa is too far

    def test_filter_sorted_by_distance(self) -> None:
        """Results should be sorted by distance (closest first)."""
        listings = [
            {"id": "gdansk", "latitude": 54.3520, "longitude": 18.6466},  # ~19 km
            {"id": "sopot", "latitude": 54.4418, "longitude": 18.5601},  # ~9 km
        ]

        result = filter_by_radius(listings, 54.5189, 18.5305, 30.0)
        assert result[0]["id"] == "sopot"  # Closer
        assert result[1]["id"] == "gdansk"  # Further

    def test_filter_empty_list(self) -> None:
        """Empty input returns empty output."""
        result = filter_by_radius([], 54.5189, 18.5305, 30.0)
        assert result == []

    def test_filter_no_coords(self) -> None:
        """Listings without coordinates are excluded."""
        listings = [
            {"id": "1", "latitude": None, "longitude": None},
            {"id": "2", "latitude": 54.4418, "longitude": 18.5601},
        ]

        result = filter_by_radius(listings, 54.5189, 18.5305, 30.0)
        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_filter_zero_radius(self) -> None:
        """Zero radius returns empty (only exact point would match)."""
        listings = [{"id": "1", "latitude": 54.5189, "longitude": 18.5305}]
        result = filter_by_radius(listings, 54.5189, 18.5305, 0.0)
        assert result == []

    def test_distance_km_added(self) -> None:
        """Filtered results should have distance_km attached."""
        listings = [
            {"id": "sopot", "latitude": 54.4418, "longitude": 18.5601},
        ]

        result = filter_by_radius(listings, 54.5189, 18.5305, 30.0)
        assert "distance_km" in result[0]
        assert 7.0 <= result[0]["distance_km"] <= 10.0
