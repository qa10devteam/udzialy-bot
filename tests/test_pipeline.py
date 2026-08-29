"""run_search_pipeline tests with a stubbed manager — no network, no browser.

Covers the bot's whole /search data path (scan → rank → display dicts) so a
regression in any stage shows up here instead of in the client's Telegram.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from scraper.manager import ScraperManager, listing_id_for
from scraper.pipeline import (
    DEFAULT_KEYWORDS,
    PipelineResult,
    format_text_report,
    run_search_pipeline,
    select_portals,
    to_display_dict,
)


class StubManager(ScraperManager):
    """search_all returns canned dicts and drives the callback like the real one."""

    def __init__(self, listings: List[Dict[str, Any]], portal_counts: Dict[str, int]):
        super().__init__(portals=list(portal_counts))
        self._listings = listings
        self._portal_counts = portal_counts
        self.received_keywords: List[str] = []
        self.received_filters: Dict[str, Any] = {}

    async def search_all(self, keywords, filters=None, progress_callback=None):
        self.received_keywords = list(keywords)
        self.received_filters = dict(filters or {})
        from scraper.manager import _notify
        for name, count in self._portal_counts.items():
            await _notify(progress_callback, name, "done" if count else "timeout", count)
        return self._score_results(self._deduplicate_by_url(
            [dict(l, id=listing_id_for(l["url"])) for l in self._listings]
        ))


LISTINGS = [
    {"title": "Syndyk sprzeda udział 1/2 w mieszkaniu, Gdynia", "url": "https://olx/1", "price": 60000,
     "city": "Gdynia", "voivodeship": "pomorskie", "source_portal": "olx",
     "raw_description": "Syndyk sprzeda udział 1/2 w lokalu mieszkalnym"},
    {"title": "Udział spadkowy w kamienicy 1/4", "url": "https://morizon/2", "price": 150000,
     "city": "Sopot", "voivodeship": "pomorskie", "source_portal": "morizon",
     "raw_description": "udział w kamienicy, spadek"},
    {"title": "Mieszkanie 3 pokoje, nowe budownictwo", "url": "https://olx/3", "price": 650000,
     "city": "Gdańsk", "voivodeship": "pomorskie", "source_portal": "olx", "raw_description": ""},
    {"title": "Udziały w spółce z o.o. na sprzedaż", "url": "https://olx/4", "price": 10000,
     "city": "Gdańsk", "voivodeship": "", "source_portal": "olx", "raw_description": "udziały w spółce"},
]


@pytest.mark.asyncio
async def test_pipeline_end_to_end_with_stub():
    mgr = StubManager(LISTINGS, {"OLX": 3, "Morizon": 1, "Otodom": 0})
    events: List[tuple] = []

    async def hook(stage, d):
        events.append((stage, d.get("portal")))

    result = await run_search_pipeline(
        filters={"price_max": 200000}, portals=["olx", "morizon", "otodom"],
        deep_fetch=False, progress=hook, manager=mgr,
    )

    assert isinstance(result, PipelineResult)
    assert mgr.received_keywords == DEFAULT_KEYWORDS
    assert mgr.received_filters == {"price_max": 200000}
    assert result.raw_count == 4
    assert result.portal_status["Otodom"] == {"status": "timeout", "count": 0}
    # real shares found, noise (plain flat, company shares) rejected
    found_urls = [d["url"] for d in result.display]
    assert "https://olx/1" in found_urls
    assert "https://morizon/2" in found_urls
    assert "https://olx/3" not in found_urls
    assert "https://olx/4" not in found_urls
    # display dicts carry everything results.py needs, with stable ids
    d0 = result.display[0]
    for key in ("id", "title", "price", "city", "url", "source", "score", "tier", "fraction"):
        assert key in d0
    assert d0["id"] == listing_id_for(d0["url"])
    assert d0["tier"] in ("pewny", "prawdopodobny", "mozliwy")
    assert result.display[0]["score"] >= result.display[-1]["score"] or \
        result.display[0]["tier"] == "pewny"
    # progress hook saw every portal + rank stage
    assert [e for e in events if e[0] == "portal"] == [("portal", "OLX"), ("portal", "Morizon"), ("portal", "Otodom")]
    assert ("rank", None) in events
    # no raw HTML / long descriptions leak into FSM-stored dicts
    assert all(len(d["description"]) <= 1500 for d in result.display)


@pytest.mark.asyncio
async def test_pipeline_empty_scan():
    mgr = StubManager([], {"OLX": 0})
    result = await run_search_pipeline(deep_fetch=False, manager=mgr)
    assert result.raw_count == 0 and result.found == 0 and result.display == []
    assert "Udziały: 0" in format_text_report(result)


@pytest.mark.asyncio
async def test_pipeline_sync_progress_hook_and_report():
    mgr = StubManager(LISTINGS, {"OLX": 4})
    seen = []
    result = await run_search_pipeline(deep_fetch=False, progress=lambda s, d: seen.append(s), manager=mgr)
    assert "portal" in seen and "rank" in seen
    report = format_text_report(result, limit=1)
    assert "Udziały: 2" in report
    assert "https://olx/1" in report or "https://morizon/2" in report
    assert "więcej" in report  # limit=1 of 2


def test_select_portals_intersects_with_manager_capabilities():
    assert select_portals(None) == ScraperManager.MAIN_PORTALS
    assert select_portals(["olx", "gratka", "lento"]) == ["olx"]
    # config with only unsupported portals must not produce an empty scan
    assert select_portals(["gratka"]) == ScraperManager.MAIN_PORTALS


def test_to_display_dict_uses_existing_id():
    from detector.ranking import classify_and_rank
    listing = {"id": "abc", "title": "udział 1/2 w domu", "url": "https://u", "score": 80,
               "raw_description": "", "source_portal": "olx", "price": 1000}
    c = classify_and_rank([listing])[0]
    assert to_display_dict(c)["id"] == "abc"
