"""
ScraperManager - Orchestrator for parallel portal scraping.

Coordinates all portal scrapers, handles deduplication,
progress callbacks, and timeout management.
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

from scraper.base import BaseScraper, RawListing
from scraper.tor_manager import TorManager

logger = logging.getLogger(__name__)

# Type for progress callback: (portal_name, status_message) -> None
ProgressCallback = Callable[[str, str], Coroutine[Any, Any, None]]


class ScraperManager:
    """
    Orchestrates parallel portal scraping with deduplication.
    
    Usage:
        manager = ScraperManager()
        results = await manager.search_all(
            keywords=["udział", "1/2 nieruchomości"],
            filters={"price_max": 200000},
            progress_callback=send_telegram_update,
        )
    """
    
    def __init__(
        self,
        scrapers: Optional[List[BaseScraper]] = None,
        tor_manager: Optional[TorManager] = None,
        default_timeout: float = 20.0,
        max_concurrent: int = 5,
    ):
        self.scrapers: List[BaseScraper] = scrapers or []
        self.tor_manager = tor_manager or TorManager()
        self.default_timeout = default_timeout
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    def register_scraper(self, scraper: BaseScraper) -> None:
        """Register a portal scraper."""
        self.scrapers.append(scraper)
        logger.info(f"Registered scraper: {scraper.get_portal_name()}")
    
    def register_all_portals(self) -> None:
        """Register all available portal scrapers with default configs."""
        from scraper.portals.morizon import MorizonScraper
        from scraper.portals.gratka import GratkaScraper
        from scraper.portals.domiporta import DomiportaScraper
        from scraper.portals.olx import OlxScraper
        from scraper.portals.otodom import OtodomScraper
        from scraper.portals.trojmiasto import TrojmiastoScraper
        from scraper.portals.szybko import SzybkoScraper
        from scraper.portals.nieruchomosci_online import NieruchomosciOnlineScraper
        from scraper.portals.allegro import AllegroScraper
        
        self.scrapers = [
            MorizonScraper(),
            GratkaScraper(),
            DomiportaScraper(),
            OlxScraper(use_tor=True),
            OtodomScraper(use_tor=True),
            TrojmiastoScraper(use_tor=True),
            SzybkoScraper(use_tor=True),
            NieruchomosciOnlineScraper(),
            AllegroScraper(),
        ]
        logger.info(f"Registered {len(self.scrapers)} portal scrapers")
    
    async def search_all(
        self,
        keywords: List[str],
        filters: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        timeout: Optional[float] = None,
    ) -> List[RawListing]:
        """
        Search all registered portals in parallel.
        
        Args:
            keywords: Search terms
            filters: Optional filters (price_min, price_max, city, etc.)
            progress_callback: Async callback(portal_name, status) for Telegram updates
            timeout: Per-portal timeout override
        
        Returns:
            Deduplicated list of RawListing from all portals
        """
        if not self.scrapers:
            logger.warning("No scrapers registered!")
            return []
        
        portal_timeout = timeout or self.default_timeout
        
        # Notify start
        if progress_callback:
            portal_names = [s.get_portal_name() for s in self.scrapers]
            await progress_callback(
                "manager",
                f"🔍 Szukam na {len(self.scrapers)} portalach: {', '.join(portal_names)}"
            )
        
        # Create tasks for parallel execution
        tasks = [
            self._search_portal(scraper, keywords, filters, portal_timeout, progress_callback)
            for scraper in self.scrapers
        ]
        
        # Execute in parallel with gather
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect all listings
        all_listings: List[RawListing] = []
        successful_portals = 0
        failed_portals = 0
        
        for i, result in enumerate(results):
            portal_name = self.scrapers[i].get_portal_name()
            
            if isinstance(result, Exception):
                failed_portals += 1
                logger.error(f"Portal {portal_name} failed: {result}")
                if progress_callback:
                    await progress_callback(portal_name, f"❌ {portal_name}: błąd - {str(result)[:50]}")
            elif isinstance(result, list):
                successful_portals += 1
                all_listings.extend(result)
                if progress_callback:
                    await progress_callback(portal_name, f"✅ {portal_name}: {len(result)} wyników")
            else:
                failed_portals += 1
                logger.warning(f"Portal {portal_name} returned unexpected: {type(result)}")
        
        # Deduplicate by source_url
        deduplicated = self._deduplicate(all_listings)
        
        # Final summary
        if progress_callback:
            await progress_callback(
                "manager",
                f"📊 Gotowe: {len(deduplicated)} unikalnych wyników "
                f"z {successful_portals}/{len(self.scrapers)} portali"
            )
        
        logger.info(
            f"Search complete: {len(deduplicated)} unique listings from "
            f"{successful_portals} portals ({failed_portals} failed)"
        )
        
        return deduplicated
    
    async def _search_portal(
        self,
        scraper: BaseScraper,
        keywords: List[str],
        filters: Optional[Dict[str, Any]],
        timeout: float,
        progress_callback: Optional[ProgressCallback],
    ) -> List[RawListing]:
        """Search a single portal with timeout and semaphore."""
        portal_name = scraper.get_portal_name()
        
        async with self._semaphore:
            # New Tor circuit for portals that use Tor
            if scraper.use_tor and self.tor_manager:
                await self.tor_manager.new_circuit_for_portal(portal_name)
            
            if progress_callback:
                await progress_callback(portal_name, f"🔄 {portal_name}: szukam...")
            
            try:
                result = await asyncio.wait_for(
                    scraper.search(keywords, filters),
                    timeout=timeout,
                )
                return result
            except asyncio.TimeoutError:
                logger.warning(f"Portal {portal_name} timed out after {timeout}s")
                if progress_callback:
                    await progress_callback(portal_name, f"⏰ {portal_name}: timeout")
                return []
            except Exception as e:
                logger.error(f"Portal {portal_name} error: {e}")
                raise
    
    def _deduplicate(self, listings: List[RawListing]) -> List[RawListing]:
        """Deduplicate listings by source_url."""
        seen_urls: set = set()
        unique: List[RawListing] = []
        
        for listing in listings:
            if listing.source_url not in seen_urls:
                seen_urls.add(listing.source_url)
                unique.append(listing)
        
        duplicates_removed = len(listings) - len(unique)
        if duplicates_removed > 0:
            logger.info(f"Deduplication: removed {duplicates_removed} duplicates")
        
        return unique
    
    async def search_portal(
        self,
        portal_name: str,
        keywords: List[str],
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RawListing]:
        """Search a single portal by name."""
        for scraper in self.scrapers:
            if scraper.get_portal_name().lower() == portal_name.lower():
                return await scraper.search(keywords, filters)
        
        raise ValueError(f"Portal not found: {portal_name}")
    
    def get_portal_names(self) -> List[str]:
        """Get list of registered portal names."""
        return [s.get_portal_name() for s in self.scrapers]
