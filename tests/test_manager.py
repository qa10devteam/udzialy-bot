"""ScraperManager contract tests — no network.

These pin the three regressions that made every bot search fail in v3.2.3:
  1. progress_callback shape (async / 2-arg / 3-arg) must never affect results
  2. scrapers returning RawListing objects must be normalized to dicts
  3. one failing/slow portal must not take the others down
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import pytest

from scraper.base import BaseScraper, RawListing
from scraper.manager import ScraperManager, normalize_listing, listing_id_for


# --- stubs -----------------------------------------------------------------

class DictScraper(BaseScraper):
    """Returns dicts (OLX/Otodom/Morizon/Domiporta style)."""

    def __init__(self, name: str = "Dicty", items: Optional[List[dict]] = None):
        super().__init__()
        self._name = name
        self._items = items if items is not None else [
            {"title": "Syndyk sprzeda udział 1/2 w mieszkaniu", "url": "https://x/1",
             "price": 50000, "city": "Gdynia", "voivodeship": "pomorskie",
             "source_portal": "olx", "raw_description": "udział 1/2, spadek"},
            {"title": "Mieszkanie 3 pokoje", "url": "https://x/2", "price": 500000,
             "city": "Gdynia", "voivodeship": "", "source_portal": "olx", "raw_description": ""},
        ]

    async def search(self, keywords, filters=None):
        return list(self._items)

    def parse_listing(self, html):  # pragma: no cover
        return None

    def get_portal_name(self):
        return self._name


class RawListingScraper(BaseScraper):
    """Returns RawListing dataclasses (nieruchomosci_online style)."""

    async def search(self, keywords, filters=None):
        return [
            RawListing(
                title="Udział 1/4 w kamienicy",
                source_url="https://y/1",
                portal="nieruchomosci_online",
                price=120000,
                city="Sopot",
                description="sprzedaż udziału 1/4 w kamienicy, spadek",
                area_m2=80,
                share_fraction="1/4",
            )
        ]

    def parse_listing(self, html):  # pragma: no cover
        return None

    def get_portal_name(self):
        return "NieruchomosciOnline"


class BrokenScraper(BaseScraper):
    async def search(self, keywords, filters=None):
        raise RuntimeError("boom")

    def parse_listing(self, html):  # pragma: no cover
        return None

    def get_portal_name(self):
        return "Broken"


class SlowScraper(BaseScraper):
    async def search(self, keywords, filters=None):
        await asyncio.sleep(5)
        return [{"title": "late", "url": "https://z/1"}]

    def parse_listing(self, html):  # pragma: no cover
        return None

    def get_portal_name(self):
        return "Slow"


def make_manager(*scrapers: BaseScraper, timeout: float = 2.0) -> ScraperManager:
    m = ScraperManager(portals=[s.get_portal_name() for s in scrapers], timeout_per_portal=timeout)
    m._instantiate_scrapers = lambda: list(scrapers)  # type: ignore[method-assign]
    return m


# --- callback contract -----------------------------------------------------

@pytest.mark.asyncio
async def test_bot_style_async_two_arg_callback_does_not_break_results():
    """The exact callback shape bot/routers/search.py used in v3.2.3."""
    seen: List[tuple] = []

    async def progress_callback(portal_name: str, status: str) -> None:
        seen.append((portal_name, status))

    m = make_manager(DictScraper())
    results = await m.search_all(["udział"], {}, progress_callback=progress_callback)

    assert len(results) == 2
    assert seen == [("Dicty", "done")]


@pytest.mark.asyncio
async def test_three_arg_sync_callback_receives_count():
    seen: Dict[str, Any] = {}

    def cb(name, status, count):
        seen[name] = (status, count)

    m = make_manager(DictScraper())
    results = await m.search_all(["udział"], {}, progress_callback=cb)
    assert len(results) == 2
    assert seen == {"Dicty": ("done", 2)}


@pytest.mark.asyncio
async def test_three_arg_async_callback_is_awaited():
    seen: List[int] = []

    async def cb(name, status, count):
        await asyncio.sleep(0)
        seen.append(count)

    m = make_manager(DictScraper())
    await m.search_all(["udział"], {}, progress_callback=cb)
    assert seen == [2]


@pytest.mark.asyncio
async def test_raising_callback_never_discards_results():
    def cb(name, status, count):
        raise ValueError("callback bug")

    m = make_manager(DictScraper())
    results = await m.search_all(["udział"], {}, progress_callback=cb)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_no_callback_still_works():
    m = make_manager(DictScraper())
    assert len(await m.search_all(["udział"], {})) == 2


# --- RawListing normalization ---------------------------------------------

def test_normalize_rawlisting_maps_to_canonical_keys():
    rl = RawListing(title="T", source_url="https://u", portal="nieruchomosci_online",
                    price=1.0, city="C", description="D", area_m2=10, share_fraction="1/2")
    d = normalize_listing(rl)
    assert d is not None
    assert d["url"] == "https://u"
    assert d["source_portal"] == "nieruchomosci_online"
    assert d["raw_description"] == "D"
    assert d["area"] == 10
    assert d["fraction"] == "1/2"
    assert d["id"] == listing_id_for("https://u")


def test_normalize_dict_keeps_extra_keys_and_adds_id():
    d = normalize_listing({"title": "x", "url": "https://q", "extra": 1})
    assert d["extra"] == 1
    assert d["id"] == listing_id_for("https://q")
    assert d["raw_description"] == "x"  # falls back to title


def test_normalize_garbage_returns_none():
    assert normalize_listing(42) is None
    assert normalize_listing("str") is None


@pytest.mark.asyncio
async def test_mixed_dict_and_rawlisting_portals_dedup_and_score():
    m = make_manager(DictScraper(), RawListingScraper())
    results = await m.search_all(["udział"], {})
    assert len(results) == 3
    assert all(isinstance(r, dict) for r in results)
    urls = {r["url"] for r in results}
    assert urls == {"https://x/1", "https://x/2", "https://y/1"}
    # scored by manager, sorted DESC
    assert results[0]["score"] >= results[-1]["score"]
    assert all("is_share" in r for r in results)
    kamienica = next(r for r in results if r["url"] == "https://y/1")
    assert kamienica["is_share"] is True


# --- isolation of failures ------------------------------------------------

@pytest.mark.asyncio
async def test_broken_portal_is_isolated():
    seen = {}
    m = make_manager(DictScraper(), BrokenScraper())
    results = await m.search_all(["udział"], {}, progress_callback=lambda n, s, c: seen.__setitem__(n, s))
    assert len(results) == 2
    assert seen["Broken"] == "error"
    assert seen["Dicty"] == "done"


@pytest.mark.asyncio
async def test_slow_portal_times_out_but_others_survive():
    seen = {}
    m = make_manager(DictScraper(), SlowScraper(), timeout=0.2)
    results = await m.search_all(["udział"], {}, progress_callback=lambda n, s, c: seen.__setitem__(n, (s, c)))
    assert len(results) == 2
    assert seen["Slow"] == ("timeout", 0)


def test_default_timeout_is_big_enough_for_browser_portals():
    # Otodom (patchright, 3 pages) measured at ~46s; OLX via Tor ~30-45s.
    assert ScraperManager().timeout_per_portal >= 60


@pytest.mark.asyncio
async def test_dedup_by_url_across_portals():
    a = DictScraper("A", [{"title": "udział 1/2", "url": "https://same"}])
    b = DictScraper("B", [{"title": "udział 1/2", "url": "https://same"}])
    m = make_manager(a, b)
    assert len(await m.search_all(["udział"], {})) == 1
