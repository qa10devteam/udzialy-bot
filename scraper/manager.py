"""
ScraperManager - Orchestrator for parallel portal scraping.

Coordinates all portal scrapers, handles deduplication,
progress callbacks, timeout management, share scoring, and LLM analysis.
"""

import asyncio
import dataclasses
import hashlib
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

from scraper.base import BaseScraper, RawListing
from detector.scorer import PropertyShareScorer

logger = logging.getLogger(__name__)

# Type for progress callback: (portal_name, status, count) -> None
# Sync or async; legacy 2-arg (portal_name, status) callbacks are also accepted.
ProgressCallback = Callable[..., Any]

# Minimum score threshold for LLM analysis (only analyze pre-filtered shares)
LLM_ANALYSIS_SCORE_THRESHOLD = 25

# Per-portal timeout. Otodom (browser layer, 3 pages) needs ~45-50s, OLX via Tor
# with 6 keywords x 2 pages needs ~30-45s. 20s silently dropped both (bug #3).
DEFAULT_PORTAL_TIMEOUT = 90.0


def listing_id_for(url: str) -> str:
    """Stable short id derived from the listing URL (used by save/detail buttons)."""
    return hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:12]


def normalize_listing(listing: Any) -> Optional[Dict[str, Any]]:
    """Coerce any scraper output (dict or RawListing) into the canonical dict shape.

    Canonical keys: id, title, price, city, voivodeship, url, source_portal,
    raw_description, area, fraction. Extra keys on dicts are preserved.
    Returns None for objects that cannot be interpreted as a listing.
    """
    if isinstance(listing, dict):
        d = dict(listing)
    elif isinstance(listing, RawListing) or dataclasses.is_dataclass(listing):
        raw = dataclasses.asdict(listing)
        d = {
            "title": raw.get("title") or "",
            "price": raw.get("price"),
            "city": raw.get("city") or raw.get("location") or "",
            "voivodeship": raw.get("voivodeship") or "",
            "url": raw.get("source_url") or raw.get("url") or "",
            "source_portal": raw.get("portal") or raw.get("source_portal") or "",
            "raw_description": raw.get("description") or raw.get("title") or "",
            "area": raw.get("area_m2"),
            "fraction": raw.get("share_fraction") or "",
        }
    elif hasattr(listing, "__dict__"):
        d = dict(vars(listing))
        d.setdefault("url", d.get("source_url", ""))
        d.setdefault("source_portal", d.get("portal", ""))
    else:
        return None

    d.setdefault("title", "")
    d.setdefault("url", "")
    d.setdefault("source_portal", d.get("source", ""))
    d.setdefault("raw_description", d.get("description") or d.get("title") or "")
    d.setdefault("city", "")
    d.setdefault("voivodeship", "")
    if not d.get("id"):
        d["id"] = listing_id_for(d["url"] or d["title"])
    return d


def _accepts_three_args(callback: Callable[..., Any]) -> bool:
    """True if callback can take (portal, status, count); False for legacy 2-arg form."""
    try:
        params = list(inspect.signature(callback).parameters.values())
    except (TypeError, ValueError):
        return True
    positional = [
        p for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(p.kind == p.VAR_POSITIONAL for p in params)
    return has_varargs or len(positional) >= 3


async def _notify(callback: Optional[ProgressCallback], portal_name: str, status: str, count: int) -> None:
    """Invoke a progress callback safely.

    Accepts sync or async callables with 3 args (portal, status, count) or the
    legacy 2-arg form (portal, status). A failing callback must never affect
    scraping results — it is logged and ignored.
    """
    if callback is None:
        return
    try:
        result = (
            callback(portal_name, status, count)
            if _accepts_three_args(callback)
            else callback(portal_name, status)
        )
        if inspect.isawaitable(result):
            await result
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"progress_callback failed for {portal_name}: {e}")


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
        timeout_per_portal: float = DEFAULT_PORTAL_TIMEOUT,
        llm_enabled: bool = False,
    ):
        """
        Initialize the ScraperManager.

        Args:
            portals: List of portal names to enable. Defaults to MAIN_PORTALS.
            timeout_per_portal: Per-portal asyncio timeout in seconds.
            llm_enabled: Run the manager's own LLM pass on high-scoring listings.
                Off by default — the bot runs its own analysis on the ranked list.
        """
        self.enabled_portals = portals or self.MAIN_PORTALS
        self.timeout_per_portal = timeout_per_portal
        self.llm_enabled = llm_enabled
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
            """Run a single portal scraper with timeout.

            The progress callback is invoked OUTSIDE the scraping try-block so a
            misbehaving callback can never turn a successful scrape into an error.
            """
            portal_name = scraper.get_portal_name()
            status, results, error = "done", [], None
            try:
                results = await asyncio.wait_for(
                    scraper.search(keywords, filters),
                    timeout=self.timeout_per_portal,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Portal {portal_name} timed out after {self.timeout_per_portal}s")
                status, error = "timeout", "timeout"
            except Exception as e:
                logger.error(f"Portal {portal_name} error: {e}")
                status, error = "error", str(e)

            normalized: List[dict] = []
            for item in results or []:
                d = normalize_listing(item)
                if d is None:
                    logger.warning(f"Portal {portal_name}: skipping unparseable item {type(item).__name__}")
                    continue
                if not d.get("source_portal"):
                    d["source_portal"] = portal_name.lower()
                normalized.append(d)

            await _notify(progress_callback, portal_name, status, len(normalized))
            return (portal_name, normalized, error)

        # Execute all portals in parallel
        tasks = [_run_portal(scraper) for scraper in scrapers]
        results = await asyncio.gather(*tasks)

        # Collect all listings
        all_listings: List[dict] = []
        failed_portals: List[str] = []
        for portal_name, listings, error in results:
            if listings:
                all_listings.extend(listings)
                logger.info(f"Portal {portal_name}: {len(listings)} results")
            elif error:
                failed_portals.append(f"{portal_name} ({error})")
                logger.warning(f"Portal {portal_name}: {error}")

        if failed_portals and not all_listings:
            logger.error(
                f"ALL portals failed: {failed_portals}. "
                "Check: internet connection, firewall, antivirus blocking python.exe"
            )
        elif failed_portals:
            logger.info(f"Partial success. Failed portals: {failed_portals}")

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
        if not self.llm_enabled:
            return
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
