"""Live pipeline integration test: fetch → parse → score → report.

Run with: .venv/bin/pytest tests/test_pipeline_live.py -v -s
"""

import asyncio
import re
import sys

import pytest

sys.path.insert(0, "/home/ubuntu/udzialy-bot")

from bs4 import BeautifulSoup
from detector.scorer import PropertyShareScorer
from scraper.stealth import fetch_with_stealth


@pytest.fixture
def scorer():
    return PropertyShareScorer()


@pytest.mark.asyncio
async def test_morizon_fetch_and_parse(scorer):
    """Fetch Morizon, parse listings, score for shares."""
    config = {"name": "morizon", "start_layer": 1, "use_tor": False, "timeout": 15}
    url = "https://www.morizon.pl/mieszkania/?q=udzia%C5%82"

    body = await fetch_with_stealth(url, config)
    assert body is not None, "Morizon fetch returned None"
    assert len(body) > 10000, f"Response too small: {len(body)} bytes"
    assert "property-card" in body, "No property-card elements in response"

    # Parse
    soup = BeautifulSoup(body, "html.parser")
    cards = soup.select("[data-cy=propertyUrl], a.property-card")
    assert len(cards) > 0, "No listing cards found"

    # Score
    shares = []
    for card in cards[:20]:
        title_el = card.select_one(".property-card__title, h2, h3")
        title = title_el.get_text(strip=True) if title_el else card.get_text(strip=True)[:100]
        result = scorer.score(title, "")
        if result.is_share:
            shares.append((title, result.score))

    print(f"\nMorizon: {len(cards)} cards, {len(shares)} shares detected")
    for title, score in shares[:5]:
        print(f"  [{score}] {title[:60]}")


@pytest.mark.asyncio
async def test_olx_via_tor(scorer):
    """Fetch OLX via curl_cffi + Tor, parse offers."""
    config = {
        "name": "olx",
        "start_layer": 3,
        "use_tor": True,
        "tor_proxy": "socks5://127.0.0.1:9050",
        "timeout": 20,
    }
    url = "https://www.olx.pl/nieruchomosci/q-udzia%C5%82/"

    body = await fetch_with_stealth(url, config)
    assert body is not None, "OLX fetch returned None"
    assert len(body) > 50000, f"Response too small: {len(body)} bytes"

    is_blocked = "just a moment" in body.lower() or "access denied" in body.lower()
    assert not is_blocked, "OLX response is blocked"

    # Parse offer links
    offer_links = re.findall(r'href="(/d/oferta/[^"]+)"', body)
    assert len(offer_links) > 0, "No offer links found"

    # Parse titles
    soup = BeautifulSoup(body[:1000000], "html.parser")
    titles = soup.select("[data-testid=ad-card-title] a, .css-u2ayx9 a")

    shares = []
    for t in titles[:15]:
        text = t.get_text(strip=True)
        result = scorer.score(text, "")
        if result.is_share:
            shares.append((text, result.score))

    print(f"\nOLX: {len(offer_links)} offers, {len(titles)} titles, {len(shares)} shares")
    for title, score in shares[:5]:
        print(f"  [{score}] {title[:60]}")


@pytest.mark.asyncio
async def test_gratka_fetch(scorer):
    """Fetch Gratka, verify response."""
    config = {"name": "gratka", "start_layer": 1, "use_tor": False, "timeout": 15}
    url = "https://gratka.pl/nieruchomosci/mieszkania?fraza=udzia%C5%82"

    body = await fetch_with_stealth(url, config)
    assert body is not None, "Gratka fetch returned None"
    assert len(body) > 10000, f"Response too small: {len(body)} bytes"

    is_blocked = "just a moment" in body.lower()
    assert not is_blocked, "Gratka is blocked by Cloudflare"
    print(f"\nGratka: {len(body)} bytes fetched OK")


@pytest.mark.asyncio
async def test_domiporta_fetch(scorer):
    """Fetch Domiporta, verify response and parse."""
    config = {"name": "domiporta", "start_layer": 1, "use_tor": False, "timeout": 15}
    url = "https://www.domiporta.pl/mieszkanie/sprzedam?KeyWords=udzia%C5%82"

    body = await fetch_with_stealth(url, config)
    assert body is not None, "Domiporta fetch returned None"
    assert len(body) > 10000, f"Response too small: {len(body)} bytes"

    soup = BeautifulSoup(body, "html.parser")
    cards = soup.select("article.sneakpeak, .sneakpeak__title, .listing-item")
    print(f"\nDomiporta: {len(body)} bytes, {len(cards)} elements")
    assert len(cards) > 0, "No listing elements found"
