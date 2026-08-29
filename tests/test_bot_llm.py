"""LLM-analysis stage of /search — the path that crashed on the client's machine (v3.2.4):

    TypeError: ListingAnalyzer.analyze() got an unexpected keyword argument 'fraction'

These tests use the REAL ListingAnalyzer signature (an analyzer with no providers,
which returns None without any network) so a kwarg mismatch fails here, plus a fake
analyzer returning a real AnalysisResult to check rendering, and a raising analyzer
to check that AI failure never hides the results.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List

import pytest

import bot.routers.search as search_mod
import bot.routers.results as results_mod
from detector.llm_analyzer import AnalysisResult, ListingAnalyzer
from scraper.manager import ScraperManager
from scraper.pipeline import PipelineResult
from detector.ranking import classify_and_rank

from tests.test_bot_handlers import (  # reuse fakes/fixtures
    FakeMessage, FakeCallback, assert_telegram_safe, fsm, settings, stub_pipeline,
)


def _enable_llm(settings, monkeypatch):
    settings.llm.enabled = True
    settings.llm.api_key = "sk-test"
    settings.llm.provider = "claude"
    settings.llm.model = "claude-haiku-4-5-20251001"


def _fake_result(**over) -> AnalysisResult:
    base = dict(is_real_share=True, confidence=0.9, stars=4, summary="Udział 1/2 od syndyka, okazja.",
                fraction="1/2", property_type="mieszkanie", seller_motivation="syndyk",
                estimated_value_total=150000, price_assessment="poniżej rynku", risks=["współwłaściciel w lokalu"])
    base.update(over)
    return AnalysisResult(**base)


# --- signature contract -----------------------------------------------------

def test_our_kwargs_match_real_analyze_signature():
    params = set(inspect.signature(ListingAnalyzer.analyze).parameters) - {"self"}
    assert {"title", "description", "price", "location", "area"} <= params
    assert "fraction" not in params  # the v3.2.4 crash


@pytest.mark.asyncio
async def test_real_analyzer_without_providers_is_called_with_valid_kwargs(fsm, settings, stub_pipeline, monkeypatch):
    """Real ListingAnalyzer (no providers) → analyze() returns None, but only if kwargs are valid."""
    _enable_llm(settings, monkeypatch)
    real = ListingAnalyzer(providers=[])
    calls: List[Dict[str, Any]] = []
    orig = real.analyze

    async def spy(**kw):
        calls.append(kw)
        return await orig(**kw)  # raises TypeError on a bad kwarg — exactly the client's crash

    real.analyze = spy  # type: ignore[method-assign]
    monkeypatch.setattr("detector.llm_analyzer.create_analyzer_from_config", lambda cfg: real)

    msg = FakeMessage()
    await search_mod.cmd_search(msg, fsm)

    assert calls, "analyzer was never called"
    assert len(calls) == min(15, len(stub_pipeline["display"]))
    assert set(calls[0]) == {"title", "description", "price", "location", "area"}
    assert calls[0]["price"] is None or calls[0]["price"].endswith("PLN")
    # no crash, results rendered, analysis None everywhere
    final = [e for e in msg.log if e["op"] == "edit"][-1]["text"]
    assert "Wyniki" in final
    data = await fsm.get_data()
    assert all(d.get("analysis") is None for d in data["search_results"])
    assert not any("Analiza AI nie powiodła" in e["text"] for e in msg.log)


# --- rendering with a real AnalysisResult -----------------------------------

@pytest.mark.asyncio
async def test_analysis_result_is_rendered_in_list_and_detail(fsm, settings, stub_pipeline, monkeypatch):
    _enable_llm(settings, monkeypatch)

    class FakeAnalyzer:
        stats = {"calls": 0}

        async def analyze(self, title, description, price=None, location=None, area=None):
            self.stats["calls"] += 1
            return _fake_result()

    monkeypatch.setattr("detector.llm_analyzer.create_analyzer_from_config", lambda cfg: FakeAnalyzer())

    msg = FakeMessage()
    await search_mod.cmd_search(msg, fsm)
    final = [e for e in msg.log if e["op"] == "edit"][-1]["text"]
    assert_telegram_safe(final)
    assert "⭐⭐⭐⭐☆" in final and "Udział 1/2 od syndyka" in final

    data = await fsm.get_data()
    analyzed = [d for d in data["search_results"] if d.get("analysis")]
    assert len(analyzed) == 15  # cost cap
    a = analyzed[0]["analysis"]
    assert a["stars"] == 4 and a["fraction"] == "1/2" and a["risks"] == ["współwłaściciel w lokalu"]
    assert a["price_assessment"] == "poniżej rynku"

    # detail view shows AI section incl. risks
    m = FakeMessage()
    cb = FakeCallback(f"listing:detail:{analyzed[0]['id']}", m)
    await results_mod.handle_listing_detail(cb, fsm)
    assert_telegram_safe(m.text)
    assert "Analiza AI" in m.text and "współwłaściciel w lokalu" in m.text and "poniżej rynku" in m.text


@pytest.mark.asyncio
async def test_provider_name_is_passed_to_analyzer_factory(fsm, settings, stub_pipeline, monkeypatch):
    _enable_llm(settings, monkeypatch)
    seen = {}

    def factory(cfg):
        seen.update(cfg)
        return None  # "not configured" → results shown without AI

    monkeypatch.setattr("detector.llm_analyzer.create_analyzer_from_config", factory)
    await search_mod.cmd_search(FakeMessage(), fsm)
    assert seen["providers"][0]["name"] == "anthropic"
    assert seen["providers"][0]["model"] == "claude-haiku-4-5-20251001"


# --- failure isolation ------------------------------------------------------

@pytest.mark.asyncio
async def test_raising_analyzer_does_not_hide_results(fsm, settings, stub_pipeline, monkeypatch):
    _enable_llm(settings, monkeypatch)

    class Boom:
        stats = {}

        async def analyze(self, **kw):
            raise RuntimeError("API 401")

    monkeypatch.setattr("detector.llm_analyzer.create_analyzer_from_config", lambda cfg: Boom())
    msg = FakeMessage()
    await search_mod.cmd_search(msg, fsm)
    final = [e for e in msg.log if e["op"] == "edit"][-1]["text"]
    assert "Wyniki" in final and "Znaleziono" in final
    assert (await fsm.get_data())["_search_running"] is False


@pytest.mark.asyncio
async def test_analysis_stage_exception_degrades_gracefully(fsm, settings, stub_pipeline, monkeypatch):
    """Even if _run_llm_analysis itself blows up (e.g. factory bug), user still gets the list."""
    _enable_llm(settings, monkeypatch)

    async def broken(display):
        raise TypeError("unexpected keyword argument 'fraction'")

    monkeypatch.setattr(search_mod, "_run_llm_analysis", broken)
    msg = FakeMessage()
    await search_mod.cmd_search(msg, fsm)
    texts = [e["text"] for e in msg.log]
    assert any("Analiza AI nie powiodła" in t for t in texts)
    assert "Wyniki" in [e for e in msg.log if e["op"] == "edit"][-1]["text"]
    assert len((await fsm.get_data())["search_results"]) == 44


# --- manager's own (opt-in) LLM pass uses the same valid kwargs ----------------

@pytest.mark.asyncio
async def test_manager_llm_pass_uses_valid_kwargs():
    calls = []

    class Spy:
        stats = {}

        async def analyze(self, title, description, price=None, location=None, area=None):
            calls.append(dict(title=title, description=description, price=price, location=location, area=area))
            return _fake_result()

    m = ScraperManager(llm_enabled=True)
    m._llm_analyzer = Spy()
    listings = [{"title": "udział 1/2 w domu", "raw_description": "spadek", "price": 100000.0,
                 "city": "Gdynia", "voivodeship": "pomorskie", "score": 80, "fraction": "1/2", "area": 60}]
    await m._run_llm_analysis(listings)
    assert calls and calls[0]["price"] == "100,000 PLN" and calls[0]["area"] == "60 m²"
    assert calls[0]["description"].startswith("[udział: 1/2]")
    assert listings[0]["llm_analysis"].stars == 4
