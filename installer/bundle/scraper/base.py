"""Base scraper ABC and RawListing dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class RawListing:
    """Raw listing data from a portal before normalization."""
    
    # Required fields
    title: str
    source_url: str
    portal: str
    
    # Price info
    price: Optional[float] = None
    price_text: Optional[str] = None
    currency: str = "PLN"
    
    # Location
    location: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    voivodeship: Optional[str] = None
    
    # Property details
    area_m2: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    property_type: Optional[str] = None  # mieszkanie, dom, dzialka, lokal
    
    # Udział (share) specific
    share_fraction: Optional[str] = None  # e.g. "1/2", "1/4"
    is_share: bool = False  # True if listing is for udział
    
    # Metadata
    listing_id: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    posted_at: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    
    # Raw data for debugging
    raw_html: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self) -> int:
        return hash(self.source_url)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RawListing):
            return NotImplemented
        return self.source_url == other.source_url


class BaseScraper(ABC):
    """Abstract base class for portal scrapers."""
    
    def __init__(
        self,
        use_tor: bool = False,
        tor_proxy: str = "socks5://127.0.0.1:9050",
        timeout: float = 20.0,
        stealth_layer: int = 1,
    ):
        self.use_tor = use_tor
        self.tor_proxy = tor_proxy
        self.timeout = timeout
        self.stealth_layer = stealth_layer
    
    @abstractmethod
    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[RawListing]:
        """
        Search the portal for listings matching keywords and filters.
        
        Args:
            keywords: Search terms (e.g. ["udział", "1/2"])
            filters: Optional filters (price_min, price_max, city, etc.)
        
        Returns:
            List of raw listings found
        """
        ...
    
    @abstractmethod
    def parse_listing(self, html: str) -> Optional[RawListing]:
        """
        Parse a single listing card HTML into a RawListing.
        
        Args:
            html: HTML fragment of one listing card
        
        Returns:
            Parsed RawListing or None if parsing failed
        """
        ...
    
    @abstractmethod
    def get_portal_name(self) -> str:
        """Return the human-readable portal name."""
        ...
    
    def get_portal_config(self) -> Dict[str, Any]:
        """Return portal-specific configuration for stealth fetch."""
        return {
            "portal_name": self.get_portal_name(),
            "stealth_layer": self.stealth_layer,
            "use_tor": self.use_tor,
            "tor_proxy": self.tor_proxy,
            "timeout": self.timeout,
        }
