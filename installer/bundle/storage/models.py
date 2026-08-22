"""Pydantic models for storage layer data validation and serialization.

All models use strict validation and are designed for SQLite storage
with JSON serialization for complex fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Listing(BaseModel):
    """A property listing scraped from a real estate portal.

    Attributes:
        id: Unique identifier (source_id format, e.g., 'olx_12345').
        source: Portal source ('olx', 'otodom', 'gratka').
        url: Direct URL to the listing.
        title: Listing title.
        description: Full description text.
        price: Price in PLN (None if not specified).
        price_per_m2: Calculated price per square meter.
        area: Property area in m².
        rooms: Number of rooms.
        city: City name.
        voivodeship: Voivodeship (province) name.
        district: District/neighborhood name.
        latitude: GPS latitude.
        longitude: GPS longitude.
        score: Share detection score (0-100).
        is_share: Whether listing is likely a property share.
        fraction: Detected ownership fraction (e.g., '1/2').
        matched_keywords: Keywords that matched during scoring.
        seller_name: Seller's display name.
        seller_phone: Seller's phone number.
        images: List of image URLs.
        first_seen_at: When listing was first discovered.
        last_seen_at: When listing was last confirmed active.
        is_active: Whether listing is still live.
    """

    id: str
    source: str
    url: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    price_per_m2: Optional[float] = None
    area: Optional[float] = None
    rooms: Optional[int] = None
    city: Optional[str] = None
    voivodeship: Optional[str] = None
    district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    score: int = 0
    is_share: bool = False
    fraction: Optional[str] = None
    matched_keywords: List[str] = Field(default_factory=list)
    seller_name: Optional[str] = None
    seller_phone: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    raw_data: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate source is a known portal."""
        valid_sources = {"olx", "otodom", "gratka", "morizon", "domiporta", "manual"}
        if v.lower() not in valid_sources:
            raise ValueError(f"Unknown source: {v}. Must be one of {valid_sources}")
        return v.lower()

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        """Ensure score is within 0-100 range."""
        return max(0, min(100, v))


class SavedListing(BaseModel):
    """A user-saved/bookmarked listing.

    Attributes:
        id: Auto-increment ID.
        listing_id: Reference to listings.id.
        notes: User's notes about this listing.
        priority: 0=normal, 1=high, 2=urgent.
        status: Workflow status.
        saved_at: When user saved it.
        listing: Optional joined listing data.
    """

    id: Optional[int] = None
    listing_id: str
    notes: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=2)
    status: str = "new"
    saved_at: Optional[datetime] = None
    listing: Optional[Listing] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is a known workflow state."""
        valid_statuses = {"new", "contacted", "visited", "rejected", "purchased"}
        if v.lower() not in valid_statuses:
            raise ValueError(
                f"Unknown status: {v}. Must be one of {valid_statuses}"
            )
        return v.lower()


class UserFilter(BaseModel):
    """A saved search filter configuration.

    Users can save multiple filter presets for different search criteria.

    Attributes:
        id: Auto-increment ID.
        name: User-friendly filter name (e.g., 'Gdynia okolice').
        voivodeship: Filter by voivodeship.
        city: Center city for radius search.
        radius_km: Search radius from city center.
        min_price: Minimum price in PLN.
        max_price: Maximum price in PLN.
        min_area: Minimum area in m².
        max_area: Maximum area in m².
        min_score: Minimum detection score (default 50).
        sources: Which portals to search.
        is_active: Whether filter is actively used.
        notify_enabled: Whether to send notifications for new matches.
    """

    id: Optional[int] = None
    name: str
    voivodeship: Optional[str] = None
    city: Optional[str] = None
    radius_km: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    min_score: int = 50
    sources: List[str] = Field(default_factory=lambda: ["olx", "otodom"])
    is_active: bool = True
    notify_enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SearchResult(BaseModel):
    """Record of a search execution.

    Attributes:
        id: Auto-increment ID.
        query: Search query string used.
        source: Portal searched.
        results_count: Total results found.
        new_listings_count: New listings not previously seen.
        searched_at: When the search was executed.
    """

    id: Optional[int] = None
    query: str
    source: str
    results_count: int = 0
    new_listings_count: int = 0
    searched_at: Optional[datetime] = None
