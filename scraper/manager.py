"""
ScraperManager - Orchestrator for parallel portal scraping.

Coordinates all portal scrapers, handles deduplication,
progress callbacks, timeout management, share scoring, and LLM analysis.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from scraper.base import BaseScraper
from detector.scorer import PropertyShareScorer

logger = logging.getLogger(__name__)

# Type for progress callback: (portal_name, status, count) -> None
ProgressCallback = Callable[[str, str, int], Any]

# Minimum score threshold for LLM analysis (only analyze pre-filtered shares)
LLM_ANALYSIS_SCORE_THRESHOLD = 25


class ScraperManager:
    """
    Orchestrates parallel portal scraping with deduplication, scoring, and LLM analysis.

    Usage:
        manager = ScraperManager()
        results = await manager.search_all(
            keywords=["udział w nieruchomości", "sprzedam udział"],
            filters={"price_max": 200000},
            progress_callback=lambda name, status, count: print(f"{name}: {status} ({count})"),
        )
    """

    # Main verified portals (Gratka removed: same Ringier Axel Springer DB as Morizon)
    # otodom uses nodriver Layer 5, no Tor
    # szybko/trojmiasto removed: CF blocked from datacenter, not bypassable
    MAIN_PORTALS = ["otodom", "morizon", "domiporta", "olx", "nieruchomosci_online"]

    def __init__(
        self,
        portals: Optional[List[str]] = None,
        timeout_per_portal: float = 20.0,
    ):
        """
        Initialize the ScraperManager.

        Args:
            portals: List of portal names to enable. Defaults to MAIN_PORTALS.
            timeout_per_portal: Per-portal asyncio timeout in seconds.
        """
        self.enabled_portals = portals or self.MAIN_PORTALS
        self.timeout_per_portal = timeout_per_portal
        self._last_search_time: float = 0
        self._min_search_interval: float = 30.0  # Min 30s between full scans
        self.scorer = PropertyShareScorer()
        self._llm_analyzer = None

    def _get_llm_analyzer(self):
        """Lazily initialize the LLM analyzer from config."""
        if self._llm_analyzer is None:
            try:
                from detector.llm_analyzer import create_analyzer_from_config
                import yaml
                from pathlib import Path

                # Find config.yaml
                config_path = Path(__file__).resolve().parent.parent / "config.yaml"
                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f) or {}
                    llm_config = config.get("llm", {})
                    self._llm_analyzer = create_analyzer_from_config(llm_config)
                else:
                    self._llm_analyzer = False  # Sentinel: config not found
            except Exception as e:
                logger.warning(f"Failed to initialize LLM analyzer: {e}")
                self._llm_analyzer = False  # Sentinel: init failed

        # Return None if sentinel (False means "tried and failed")
        return self._llm_analyzer if self._llm_analyzer else None

    def _instantiate_scrapers(self) -> List[BaseScraper]:
        """Instantiate all enabled portal scrapers."""
        scrapers: List[BaseScraper] = []

        for portal_name in self.enabled_portals:
            if portal_name == "morizon":
                from scraper.portals.morizon import MorizonScraper
                scrapers.append(MorizonScraper())

            elif portal_name == "domiporta":
                from scraper.portals.domiporta import DomiportaScraper
                scrapers.append(DomiportaScraper())
            elif portal_name == "otodom":
                from scraper.portals.otodom import OtodomScraper
                scrapers.append(OtodomScraper())
            elif portal_name == "olx":
                from scraper.portals.olx import OlxScraper
                scrapers.append(OlxScraper(use_tor=True))
            elif portal_name == "nieruchomosci_online":
                from scraper.portals.nieruchomosci_online import NieruchomosciOnlineScraper
                scrapers.append(NieruchomosciOnlineScraper())
            else:
                logger.warning(f"Unknown portal: {portal_name}, skipping")

        return scrapers

    async def search_all(
        self,
        keywords: List[str],
        filters: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[dict]:
        """
        Search all enabled portals in parallel.

        Args:
            keywords: Search terms (from detector.keywords.SEARCH_QUERIES)
            filters: Optional filters (price_min, price_max, city)
            progress_callback: Called as progress_callback(portal_name, status, count)
                after each portal finishes.

        Returns:
            List of result dicts sorted by share score DESC.
            Each dict has: title, price, city, voivodeship, url,
            source_portal, raw_description, score, is_share, llm_analysis (optional)
        """
        scrapers = self._instantiate_scrapers()
        if not scrapers:
            logger.warning("No scrapers instantiated!")
            return []

        filters = filters or {}

        # Create tasks for parallel execution with per-portal timeout
        async def _run_portal(scraper: BaseScraper) -> tuple:
            """Run a single portal scraper with timeout."""
            portal_name = scraper.get_portal_name()
            try:
                results = await asyncio.wait_for(
                    scraper.search(keywords, filters),
                    timeout=self.timeout_per_portal,
                )
                if progress_callback:
                    progress_callback(portal_name, "done", len(results))
                return (portal_name, results, None)
            except asyncio.TimeoutError:
                logger.warning(f"Portal {portal_name} timed out after {self.timeout_per_portal}s")
                if progress_callback:
                    progress_callback(portal_name, "timeout", 0)
                return (portal_name, [], "timeout")
            except Exception as e:
                logger.error(f"Portal {portal_name} error: {e}")
                if progress_callback:
                    progress_callback(portal_name, "error", 0)
                return (portal_name, [], str(e))

        # Execute all portals in parallel
        tasks = [_run_portal(scraper) for scraper in scrapers]
        results = await asyncio.gather(*tasks)

        # Collect all listings
        all_listings: List[dict] = []
        for portal_name, listings, error in results:
            if listings:
                all_listings.extend(listings)
                logger.info(f"Portal {portal_name}: {len(listings)} results")
            elif error:
                logger.warning(f"Portal {portal_name}: {error}")

        # Deduplicate by URL
        deduplicated = self._deduplicate_by_url(all_listings)
        logger.info(
            f"Total: {len(all_listings)} raw -> {len(deduplicated)} after dedup"
        )

        # Score each result with PropertyShareScorer
        scored = self._score_results(deduplicated)

        # Run LLM analysis on high-scoring listings
        await self._run_llm_analysis(scored)

        # Sort by score DESC
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)

        return scored

    def _deduplicate_by_url(self, listings: List[dict]) -> List[dict]:
        """Deduplicate listings by URL."""
        seen_urls: set = set()
        unique: List[dict] = []

        for listing in listings:
            url = listing.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(listing)

        removed = len(listings) - len(unique)
        if removed > 0:
            logger.info(f"Deduplication: removed {removed} duplicates")

        return unique

    def _score_results(self, listings: List[dict]) -> List[dict]:
        """Score each listing with PropertyShareScorer."""
        for listing in listings:
            title = listing.get("title", "")
            description = listing.get("raw_description", "")
            
            scoring_result = self.scorer.score(title, description)
            listing["score"] = scoring_result.score
            listing["is_share"] = scoring_result.is_share

        return listings

    async def _run_llm_analysis(self, listings: List[dict]) -> None:
        """Run LLM analysis on listings that pass the score threshold.

        Only analyzes listings with score >= LLM_ANALYSIS_SCORE_THRESHOLD.
        Runs analyses in parallel (limited by analyzer's semaphore).
        Attaches AnalysisResult to each listing dict under 'llm_analysis' key.
        """
        analyzer = self._get_llm_analyzer()
        if not analyzer:
            logger.debug("LLM analyzer not available, skipping analysis")
            return

        # Filter to only high-scoring listings
        candidates = [
            listing for listing in listings
            if listing.get("score", 0) >= LLM_ANALYSIS_SCORE_THRESHOLD
        ]

        if not candidates:
            return

        logger.info(f"Running LLM analysis on {len(candidates)} listings (score >= {LLM_ANALYSIS_SCORE_THRESHOLD})")

        async def _analyze_one(listing: dict) -> None:
            """Analyze a single listing and attach result."""
            title = listing.get("title", "")
            description = listing.get("raw_description", "")
            price = listing.get("price")
            city = listing.get("city", "")
            voivodeship = listing.get("voivodeship", "")
            location = f"{city}, {voivodeship}" if city else voivodeship
            fraction = listing.get("fraction", "")

            result = await analyzer.analyze(
                title=title,
                description=description,
                price=price,
                location=location or None,
                fraction=fraction or None,
            )

            if result:
                listing["llm_analysis"] = result

        # Run all analyses in parallel (semaphore inside analyzer limits concurrency)
        tasks = [_analyze_one(listing) for listing in candidates]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Log stats
        analyzed_count = sum(1 for l in candidates if "llm_analysis" in l)
        logger.info(
            f"LLM analysis complete: {analyzed_count}/{len(candidates)} successful. "
            f"Stats: {analyzer.stats}"
        )

    # --- Legacy interface compatibility ---

    def register_scraper(self, scraper: BaseScraper) -> None:
        """Register a portal scraper (legacy interface)."""
        pass

    def register_all_portals(self) -> None:
        """Register all available portal scrapers (legacy interface)."""
        self.enabled_portals = self.MAIN_PORTALS

    def get_portal_names(self) -> List[str]:
        """Get list of enabled portal names."""
        return list(self.enabled_portals)
