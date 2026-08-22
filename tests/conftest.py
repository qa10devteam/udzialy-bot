"""Pytest fixtures for udzialy-bot tests."""

from __future__ import annotations

import os
import tempfile
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detector.scorer import PropertyShareScorer
from storage.database import DatabaseManager


@pytest.fixture
def scorer() -> PropertyShareScorer:
    """Provide a fresh PropertyShareScorer instance."""
    return PropertyShareScorer()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[DatabaseManager, None]:
    """Provide an initialized in-memory-like temp database.

    Uses a temp file (not :memory:) because aiosqlite needs a path.
    Cleans up after test.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    db_manager = DatabaseManager(tmp.name)
    await db_manager.initialize()

    yield db_manager

    await db_manager.close()
    try:
        os.unlink(tmp.name)
        # Also remove WAL and SHM files if they exist
        os.unlink(tmp.name + "-wal")
    except OSError:
        pass
    try:
        os.unlink(tmp.name + "-shm")
    except OSError:
        pass


@pytest.fixture
def sample_listing_data() -> dict:
    """Sample listing data for testing."""
    return {
        "id": "olx_test_123",
        "source": "olx",
        "url": "https://www.olx.pl/oferta/test-123",
        "title": "Sprzedaż udziału 1/2 w mieszkaniu - Gdynia",
        "description": (
            "Sprzedam udział 1/2 w mieszkaniu 3-pokojowym w Gdyni. "
            "Mieszkanie po spadku, współwłasność z bratem. "
            "Księga wieczysta GD1G/00123456/7. "
            "Powierzchnia całkowita 65m2, udział dotyczy 32.5m2."
        ),
        "price": 95000.0,
        "area": 65.0,
        "city": "Gdynia",
        "voivodeship": "pomorskie",
        "latitude": 54.5189,
        "longitude": 18.5305,
    }


@pytest.fixture
def sample_listings() -> list:
    """List of sample listings for filter testing."""
    return [
        {
            "id": "olx_1",
            "title": "Udział 1/2 w mieszkaniu Gdynia",
            "score": 75,
            "price": 95000,
            "city": "Gdynia",
            "voivodeship": "pomorskie",
            "latitude": 54.5189,
            "longitude": 18.5305,
        },
        {
            "id": "olx_2",
            "title": "Mieszkanie 2-pokojowe Gdańsk",
            "score": 20,
            "price": 450000,
            "city": "Gdańsk",
            "voivodeship": "pomorskie",
            "latitude": 54.3520,
            "longitude": 18.6466,
        },
        {
            "id": "olx_3",
            "title": "Udział w kamienicy Sopot",
            "score": 60,
            "price": 150000,
            "city": "Sopot",
            "voivodeship": "pomorskie",
            "latitude": 54.4418,
            "longitude": 18.5601,
        },
        {
            "id": "otodom_1",
            "title": "Udział spadkowy Warszawa",
            "score": 82,
            "price": 200000,
            "city": "Warszawa",
            "voivodeship": "mazowieckie",
            "latitude": 52.2297,
            "longitude": 21.0122,
        },
    ]
