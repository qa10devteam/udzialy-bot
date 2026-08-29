"""
Search pipeline — the single 3-stage flow shared by the Telegram bot and the CLI.

    STAGE 1  scan        ScraperManager.search_all → raw listings (dicts, deduped, scored)
    STAGE 2  deep fetch  fetch full descriptions for listings with any signal (score > 0)
    STAGE 3  rank        classify_and_rank → tiers (pewny / prawdopodobny / możliwy)

The bot (`bot/routers/search.py`) and `udzialy scan` both call `run_search_pipeline`
so that what the user sees in Telegram is exactly what the CLI prints — one code path,
one set of tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from detector.ranking import ClassifiedListing, classify_and_rank
from detector.scorer import PropertyShareScorer
from scraper.manager import DEFAULT_PORTAL_TIMEOUT, ScraperManager, listing_id_for

logger = logging.getLogger(__name__)

# Keywords sent to every portal search box.
DEFAULT_KEYWORDS: List[str] = ["udział", "udziały", "współwłasność", "1/2", "1/4", "1/3"]

# Minimum score for a listing to be shown as a share (== scorer.SHARE_THRESHOLD).
MIN_SHARE_SCORE = 25

# progress(stage, detail) — stage in {"portal", "deep", "rank"}; sync or async.
ProgressHook = Callable[[str, Dict[str, Any]], Any]


@dataclass
class PipelineResult:
    """Everything a caller needs to render results or print a report."""

    raw_count: int = 0
    candidates_count: int = 0
    noise_count: int = 0
    deep_fetched: int = 0
    classified: List[ClassifiedListing] = field(default_factory=list)
    display: List[Dict[str, Any]] = field(default_factory=list)
    portal_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    portals: List[str] = field(default_factory=list)

    @property
    def found(self) -> int:
        return len(self.classified)


def select_portals(enabled_from_config: Optional[List[str]]) -> List[str]:
    """Intersect config-enabled portal names with the portals the manager can run."""
    if not enabled_from_config:
        return list(ScraperManager.MAIN_PORTALS)
    enabled = {p.lower() for p in enabled_from_config}
    chosen = [p for p in ScraperManager.MAIN_PORTALS if p in enabled]
    return chosen or list(ScraperManager.MAIN_PORTALS)


def to_display_dict(c: ClassifiedListing) -> Dict[str, Any]:
    """Flatten a ClassifiedListing into the dict shape the bot's pagination/save use.

    Keeps the keys results.py already understands (id, title, price, city, url, score,
    source, fraction, area) and adds tier metadata. No raw HTML / long descriptions —
    this dict is stored in FSM state.
    """
    raw = c.raw
    url = raw.get("url", "")
    return {
        "id": raw.get("id") or listing_id_for(url),
        "title": raw.get("title", "")[:120],
        "price": raw.get("price"),
        "city": raw.get("city") or "",
        "voivodeship": raw.get("voivodeship") or "",
        "url": url,
        "source": raw.get("source_portal") or c.portal,
        "score": c.score,
        "tier": c.tier.value,
        "share_source": c.source.value,
        "property_type": c.property_type.value,
        "fraction": c.fraction or "",
        "attractiveness": round(c.attractiveness, 3),
        "area": raw.get("area"),
        "description": (raw.get("full_description") or raw.get("raw_description") or "")[:1500],
    }


async def _emit(hook: Optional[ProgressHook], stage: str, detail: Dict[str, Any]) -> None:
    if hook is None:
        return
    try:
        r = hook(stage, detail)
        if hasattr(r, "__await__"):
            await r
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"progress hook failed: {e}")


async def run_search_pipeline(
    filters: Optional[Dict[str, Any]] = None,
    portals: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    timeout_per_portal: float = DEFAULT_PORTAL_TIMEOUT,
    deep_fetch: bool = True,
    deep_concurrency: int = 5,
    progress: Optional[ProgressHook] = None,
    manager: Optional[ScraperManager] = None,
) -> PipelineResult:
    """Run scan → deep fetch → rank and return a PipelineResult.

    Args:
        filters: price_min / price_max / city / voivodeship / radius_km.
        portals: portal names (subset of ScraperManager.MAIN_PORTALS); default all.
        keywords: search terms; default DEFAULT_KEYWORDS.
        timeout_per_portal: seconds each portal may take (see DEFAULT_PORTAL_TIMEOUT).
        deep_fetch: set False to skip stage 2 (faster, title-only scoring).
        progress: optional hook called with ("portal", {...}) after each portal,
            ("deep", {...}) before deep fetch and ("rank", {...}) before ranking.
        manager: injectable ScraperManager (tests pass a stubbed one).
    """
    filters = filters or {}
    result = PipelineResult(portals=list(portals or ScraperManager.MAIN_PORTALS))

    mgr = manager or ScraperManager(portals=result.portals, timeout_per_portal=timeout_per_portal)

    # ---- STAGE 1: scan -----------------------------------------------------
    async def _portal_cb(portal_name: str, status: str, count: int) -> None:
        result.portal_status[portal_name] = {"status": status, "count": count}
        await _emit(progress, "portal", {"portal": portal_name, "status": status, "count": count,
                                         "done": len(result.portal_status), "total": len(result.portals)})

    raw = await mgr.search_all(
        keywords=keywords or DEFAULT_KEYWORDS,
        filters=filters,
        progress_callback=_portal_cb,
    )
    result.raw_count = len(raw)

    scorer = PropertyShareScorer()
    candidates: List[Dict[str, Any]] = []
    for listing in raw:
        r = scorer.score(listing.get("title", ""), listing.get("raw_description", ""))
        listing["score"] = r.score
        listing["is_share"] = r.is_share
        listing["fraction_detected"] = r.fraction_detected
        if r.score > 0:
            candidates.append(listing)
    result.candidates_count = len(candidates)
    result.noise_count = len(raw) - len(candidates)

    # ---- STAGE 2: deep fetch ----------------------------------------------
    if candidates and deep_fetch:
        await _emit(progress, "deep", {"candidates": len(candidates), "noise": result.noise_count})
        from scraper.deep_parser import deep_fetch_batch, rescore_with_deep_data

        candidates = await deep_fetch_batch(candidates, max_concurrent=deep_concurrency)
        candidates = rescore_with_deep_data(candidates)
        result.deep_fetched = sum(1 for c in candidates if c.get("full_description"))

    # ---- STAGE 3: rank -----------------------------------------------------
    await _emit(progress, "rank", {"candidates": len(candidates)})
    result.classified = classify_and_rank(candidates, min_score=MIN_SHARE_SCORE)
    result.display = [to_display_dict(c) for c in result.classified]

    per_portal = ", ".join(f"{k}={v['count']}" for k, v in result.portal_status.items())
    logger.info(
        f"Pipeline: {result.raw_count} raw → {result.candidates_count} candidates → "
        f"{result.found} shares ({per_portal})"
    )
    return result


def format_text_report(result: PipelineResult, limit: int = 20) -> str:
    """Plain-text report for the CLI (`udzialy scan`)."""
    lines = [
        f"Portale: {', '.join(result.portals)}",
        "Status: " + ", ".join(
            f"{p}={v['status']}({v['count']})" for p, v in result.portal_status.items()
        ),
        f"Surowe ogłoszenia: {result.raw_count} | kandydaci: {result.candidates_count} "
        f"| szum: {result.noise_count} | pobrane opisy: {result.deep_fetched}",
        f"Udziały: {result.found}",
        "",
    ]
    tier_icon = {"pewny": "🔥", "prawdopodobny": "⭐", "mozliwy": "❓"}
    for i, d in enumerate(result.display[:limit], start=1):
        price = f"{d['price']:,.0f} PLN" if d.get("price") else "—"
        frac = f" | udział {d['fraction']}" if d.get("fraction") else ""
        lines.append(f"{i:2d}. {tier_icon.get(d['tier'], '')} [{d['score']}] {d['title'][:70]}")
        lines.append(f"     {price} | {d['city'] or '—'} | {d['source']}{frac}")
        lines.append(f"     {d['url']}")
    if result.found > limit:
        lines.append(f"... i {result.found - limit} więcej")
    return "\n".join(lines)
