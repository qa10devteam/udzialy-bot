"""Telegram handler tests — real aiogram FSMContext, fake Message, stubbed pipeline.

Exercises the exact code the Telegram gateway calls: /search → page 1 render →
pagination → 💾 save → detail → error path → search lock. Uses the real
display-dict shape produced by scraper.pipeline so message length / HTML / keyboard
constraints are checked against realistic data.
"""

from __future__ import annotations

import html.parser
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

import bot.routers.search as search_mod
import bot.routers.results as results_mod
import bot.routers.ai_chat as ai_chat_mod
from bot.config import Settings, reset_settings
from scraper.pipeline import PipelineResult, to_display_dict
from detector.ranking import classify_and_rank

TELEGRAM_MAX = 4096


# --- fakes ---------------------------------------------------------------

class FakeUser:
    def __init__(self, uid: int = 42):
        self.id = uid


class FakeChat:
    id = 42


class FakeBot:
    async def send_chat_action(self, *a, **k):
        pass


class FakeMessage:
    """Records every answer()/edit_text() so tests can assert what the user saw."""

    def __init__(self, text: str = "/search", user_id: int = 42, log: Optional[List] = None):
        self.text = text
        self.from_user = FakeUser(user_id)
        self.chat = FakeChat()
        self.bot = FakeBot()
        self.log: List[Dict[str, Any]] = log if log is not None else []
        self.reply_markup = None

    async def answer(self, text: str, reply_markup=None, **kw):
        m = FakeMessage(text, self.from_user.id, self.log)
        m.reply_markup = reply_markup
        self.log.append({"op": "answer", "text": text, "markup": reply_markup})
        return m

    async def edit_text(self, text: str, reply_markup=None, **kw):
        self.text = text
        self.reply_markup = reply_markup
        self.log.append({"op": "edit", "text": text, "markup": reply_markup})
        return self


class FakeCallback:
    def __init__(self, data: str, message: FakeMessage, user_id: int = 42):
        self.data = data
        self.message = message
        self.from_user = FakeUser(user_id)
        self.answers: List[tuple] = []

    async def answer(self, text: str = "", show_alert: bool = False, **kw):
        self.answers.append((text, show_alert))


class TagChecker(html.parser.HTMLParser):
    """Telegram rejects unbalanced <b>/<i>/<a> — parse-mode=HTML."""

    def __init__(self):
        super().__init__()
        self.stack: List[str] = []
        self.errors: List[str] = []

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unbalanced </{tag}> (stack={self.stack})")
        else:
            self.stack.pop()


def assert_telegram_safe(text: str) -> None:
    assert len(text) <= TELEGRAM_MAX, f"message too long: {len(text)} > {TELEGRAM_MAX}"
    c = TagChecker()
    c.feed(text)
    assert not c.errors and not c.stack, f"bad HTML: {c.errors or c.stack}"


# --- fixtures -------------------------------------------------------------

def _sample_display(n: int = 44) -> List[Dict[str, Any]]:
    """Realistic display dicts: real titles/urls from a live scan if available, else synthetic."""
    candidates = [
        Path(os.environ.get("UDZIALY_SCAN_JSON", "")),
        Path("/home/ubuntu/.claude/jobs/8a7f964a/tmp/scan_result.json"),
    ]
    for p in candidates:
        if p and p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            if data:
                return data[:n]
    raw = []
    for i in range(n):
        raw.append({
            "id": f"id{i:03d}",
            "title": f"Syndyk sprzeda udział 1/2 w mieszkaniu nr {i} — bardzo długi tytuł ogłoszenia z portalu",
            "url": f"https://www.olx.pl/d/oferta/syndyk-sprzeda-udzial-1-2-{i}-CID3-ID1bFtC8.html?search_reason=search%7Corganic",
            "price": 19250.0 + i * 1000,
            "city": "Gdynia" if i % 2 else "",
            "voivodeship": "pomorskie",
            "source_portal": "olx",
            "raw_description": "Syndyk sprzeda udział 1/2 w lokalu mieszkalnym, spadek",
            "score": 98,
        })
    return [to_display_dict(c) for c in classify_and_rank(raw)]


@pytest.fixture
def fsm() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


@pytest.fixture
def settings(monkeypatch, tmp_path):
    """Settings with owner_id=42, LLM off, temp DB — patched into every router module."""
    reset_settings()
    s = Settings(telegram={"token": "123:ABC", "owner_id": 42},
                 database={"path": str(tmp_path / "udzialy.db")})
    for mod in (search_mod, results_mod, ai_chat_mod):
        monkeypatch.setattr(mod, "get_settings", lambda *a, **k: s)
    monkeypatch.setattr(search_mod, "PROJECT_ROOT", tmp_path)
    yield s
    reset_settings()


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Replace run_search_pipeline with a stub returning realistic display dicts."""
    display = _sample_display()
    calls: Dict[str, Any] = {"n": 0, "progress_stages": []}

    async def fake_pipeline(filters=None, portals=None, timeout_per_portal=90, deep_fetch=True,
                            deep_concurrency=5, progress=None, manager=None):
        calls["n"] += 1
        calls["filters"] = filters
        calls["portals"] = portals
        calls["timeout"] = timeout_per_portal
        if progress:
            for i, p in enumerate(portals or [], 1):
                await progress("portal", {"portal": p, "status": "done", "count": 100,
                                          "done": i, "total": len(portals)})
            await progress("deep", {"candidates": 63, "noise": 474})
            await progress("rank", {"candidates": 63})
        r = PipelineResult(raw_count=537, candidates_count=63, noise_count=474,
                           deep_fetched=31, display=list(display),
                           portal_status={p: {"status": "done", "count": 100} for p in (portals or [])},
                           portals=list(portals or []))
        r.classified = classify_and_rank([
            {"title": d["title"], "raw_description": d.get("description", ""), "score": d["score"],
             "url": d["url"], "price": d["price"], "source_portal": d["source"], "id": d["id"]}
            for d in display
        ])
        return r

    import scraper.pipeline as pl
    monkeypatch.setattr(pl, "run_search_pipeline", fake_pipeline)
    calls["display"] = display
    return calls


# --- /search --------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_renders_page_one_and_stores_results(fsm, settings, stub_pipeline):
    msg = FakeMessage("/search")
    await search_mod.cmd_search(msg, fsm)

    edits = [e for e in msg.log if e["op"] == "edit"]
    assert edits, "progress message was never edited"
    final = edits[-1]
    assert_telegram_safe(final["text"])
    assert "Znaleziono 44 udziałów" in final["text"] or "Znaleziono" in final["text"]
    assert "Wyniki" in final["text"]
    assert final["markup"] is not None
    rows = final["markup"].inline_keyboard
    # 5 listing rows (🔗 Link + 💾 Zapisz) + navigation row
    assert len(rows) == 6
    assert rows[0][1].text == "💾 Zapisz"
    assert rows[0][1].callback_data.startswith("listing:save:")
    assert rows[-1][-1].callback_data == "page:1"

    data = await fsm.get_data()
    assert len(data["search_results"]) == 44
    assert data["search_page"] == 0
    assert data["_search_running"] is False
    # progress edits happened for each portal and the deep stage
    texts = " ".join(e["text"] for e in edits)
    assert "Deep scan" in texts and "Postęp:" in texts
    # settings flow through to the pipeline
    assert stub_pipeline["timeout"] == float(settings.scraping.portal_timeout)
    assert set(stub_pipeline["portals"]) <= {"otodom", "morizon", "domiporta", "olx", "nieruchomosci_online"}


@pytest.mark.asyncio
async def test_search_passes_filters_from_fsm(fsm, settings, stub_pipeline):
    await fsm.update_data(filter_city="Gdynia", filter_price_max=200000, filter_radius=50)
    await search_mod.cmd_search(FakeMessage(), fsm)
    assert stub_pipeline["filters"] == {"city": "Gdynia", "radius_km": 50, "price_max": 200000}


@pytest.mark.asyncio
async def test_search_button_and_ai_tool_use_same_path(fsm, settings, stub_pipeline):
    await search_mod.cmd_search(FakeMessage("🔍 Szukaj"), fsm)
    assert stub_pipeline["n"] == 1
    # AI tool call path (ai_chat.execute_tool → cmd_search)
    out = await ai_chat_mod.execute_tool("search_listings", {}, FakeMessage("szukaj w Gdyni"), fsm)
    assert out == "Uruchomiłem wyszukiwanie."
    assert stub_pipeline["n"] == 2


@pytest.mark.asyncio
async def test_non_owner_is_ignored(fsm, settings, stub_pipeline):
    msg = FakeMessage("/search", user_id=999)
    await search_mod.cmd_search(msg, fsm)
    assert msg.log == []
    assert stub_pipeline["n"] == 0


@pytest.mark.asyncio
async def test_search_with_filters_button_checks_callback_user(fsm, settings, stub_pipeline):
    # callback.message.from_user is the BOT (id 1) — must still run for the owner
    bot_msg = FakeMessage("filters summary", user_id=1)
    cb = FakeCallback("search_with_filters", bot_msg, user_id=42)
    await search_mod.handle_search_with_filters(cb, fsm)
    assert stub_pipeline["n"] == 1
    # ...and must NOT run for a stranger
    cb2 = FakeCallback("search_with_filters", bot_msg, user_id=999)
    await search_mod.handle_search_with_filters(cb2, fsm)
    assert stub_pipeline["n"] == 1


# --- lock -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_lock_released_after_pipeline_error(fsm, settings, monkeypatch):
    import scraper.pipeline as pl

    async def boom(**kw):
        raise RuntimeError("portal exploded")

    monkeypatch.setattr(pl, "run_search_pipeline", boom)
    msg = FakeMessage()
    await search_mod.cmd_search(msg, fsm)
    final = [e for e in msg.log if e["op"] == "edit"][-1]["text"]
    assert "Błąd wyszukiwania" in final and "portal exploded" in final
    assert (await fsm.get_data())["_search_running"] is False
    # second search is NOT blocked by a stale lock
    msg2 = FakeMessage()
    await search_mod.cmd_search(msg2, fsm)
    assert not any("już trwa" in e["text"] for e in msg2.log)


@pytest.mark.asyncio
async def test_lock_released_after_empty_result(fsm, settings, monkeypatch):
    import scraper.pipeline as pl

    async def empty(**kw):
        return PipelineResult(raw_count=0, portals=list(kw.get("portals") or []),
                              portal_status={"OLX": {"status": "timeout", "count": 0}})

    monkeypatch.setattr(pl, "run_search_pipeline", empty)
    msg = FakeMessage()
    await search_mod.cmd_search(msg, fsm)
    final = [e for e in msg.log if e["op"] == "edit"][-1]["text"]
    assert "Brak wyników" in final and "OLX" in final
    assert (await fsm.get_data())["_search_running"] is False


@pytest.mark.asyncio
async def test_concurrent_search_is_rejected_while_running(fsm, settings):
    await fsm.update_data(_search_running=True)
    msg = FakeMessage()
    await search_mod.cmd_search(msg, fsm)
    assert any("już trwa" in e["text"] for e in msg.log)


@pytest.mark.asyncio
async def test_cancel_releases_lock(fsm, settings):
    await fsm.update_data(_search_running=True)
    cb = FakeCallback("search_cancel", FakeMessage())
    await search_mod.handle_search_cancel(cb, fsm)
    assert (await fsm.get_data())["_search_running"] is False


# --- pagination / save / detail (results.py) ------------------------------

@pytest.mark.asyncio
async def test_pagination_uses_the_same_ranked_list(fsm, settings, stub_pipeline):
    await search_mod.cmd_search(FakeMessage(), fsm)
    display = (await fsm.get_data())["search_results"]

    msg = FakeMessage()
    cb = FakeCallback("page:1", msg)
    await results_mod.handle_page_change(cb, fsm)
    text = msg.text
    assert_telegram_safe(text)
    assert "str. 2/9" in text
    # items 6-10 of the ranked list, in order
    assert display[5]["title"][:40] in text
    assert display[10]["title"][:40] not in text
    rows = msg.reply_markup.inline_keyboard
    assert rows[0][1].callback_data == f"listing:save:{display[5]['id']}"
    assert (await fsm.get_data())["search_page"] == 1

    # last page clamps
    cb = FakeCallback("page:99", msg)
    await results_mod.handle_page_change(cb, fsm)
    assert "str. 9/9" in msg.text


@pytest.mark.asyncio
async def test_save_and_detail_find_listing_by_id(fsm, settings, stub_pipeline):
    await search_mod.cmd_search(FakeMessage(), fsm)
    display = (await fsm.get_data())["search_results"]
    target = display[2]

    cb = FakeCallback(f"listing:save:{target['id']}", FakeMessage())
    await results_mod.handle_listing_save(cb, fsm)
    assert cb.answers and "Zapisano" in cb.answers[-1][0], cb.answers
    assert "nie znalezione" not in cb.answers[-1][0]

    # persisted with real data (FK to listings satisfied) — /saved will show it
    from storage.database import DatabaseManager
    db = DatabaseManager(settings.database.path)
    await db.initialize()
    row = await db.fetchone(
        "SELECT l.title, l.url, l.price FROM saved_listings s JOIN listings l ON l.id = s.listing_id "
        "WHERE s.listing_id = ?", (target["id"],))
    await db.close()
    assert row is not None and row["url"] == target["url"]

    # saving twice does not duplicate
    cb = FakeCallback(f"listing:save:{target['id']}", FakeMessage())
    await results_mod.handle_listing_save(cb, fsm)
    db = DatabaseManager(settings.database.path)
    await db.initialize()
    cnt = await db.fetchone("SELECT COUNT(*) AS n FROM saved_listings WHERE listing_id = ?", (target["id"],))
    await db.close()
    assert cnt["n"] == 1

    # detail view
    msg = FakeMessage()
    cb = FakeCallback(f"listing:detail:{target['id']}", msg)
    await results_mod.handle_listing_detail(cb, fsm)
    assert_telegram_safe(msg.text)
    assert target["title"][:40] in msg.text and target["url"] in msg.text


@pytest.mark.asyncio
async def test_save_unknown_id_reports_not_found(fsm, settings, stub_pipeline):
    await search_mod.cmd_search(FakeMessage(), fsm)
    cb = FakeCallback("listing:save:doesnotexist", FakeMessage())
    await results_mod.handle_listing_save(cb, fsm)
    assert "nie znalezione" in cb.answers[-1][0]


# --- message size on worst-case titles ------------------------------------

@pytest.mark.asyncio
async def test_page_stays_under_telegram_limit_with_long_titles(fsm, settings, monkeypatch):
    import scraper.pipeline as pl
    long_display = []
    for i in range(5):
        long_display.append({
            "id": f"L{i}", "title": ("Syndyk sprzeda udział 1/2 " * 8)[:120], "price": 12345678.0,
            "city": "Bielsko-Biała Komorowice Krakowskie", "voivodeship": "śląskie",
            "url": "https://www.olx.pl/d/oferta/" + "x" * 200 + ".html?search_reason=search%7Corganic",
            "source": "olx", "score": 100, "tier": "pewny", "share_source": "syndyk",
            "property_type": "mieszkanie", "fraction": "123/456", "attractiveness": 0.9,
            "area": None, "description": "d" * 1500,
        })

    async def fake(**kw):
        r = PipelineResult(raw_count=5, candidates_count=5, display=long_display,
                           portals=list(kw.get("portals") or []))
        r.classified = classify_and_rank([
            {"title": d["title"], "raw_description": "", "score": 100, "url": d["url"],
             "price": d["price"], "source_portal": "olx"} for d in long_display])
        return r

    monkeypatch.setattr(pl, "run_search_pipeline", fake)
    msg = FakeMessage()
    await search_mod.cmd_search(msg, fsm)
    final = [e for e in msg.log if e["op"] == "edit"][-1]["text"]
    assert_telegram_safe(final)
