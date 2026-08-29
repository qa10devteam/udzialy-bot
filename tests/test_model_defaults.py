"""Default LLM model for the Claude provider is Sonnet 4.6 — everywhere, with the exact ID."""

from __future__ import annotations

import json

import pytest

from bot.config import (
    CLAUDE_DEFAULT_MODEL,
    DEFAULT_LLM_MODELS,
    Settings,
    default_model_for,
    normalize_llm_model,
    reset_settings,
)

EXACT_ID = "claude-sonnet-4-6"  # Anthropic model ID — no date suffix


def test_exact_model_id():
    assert CLAUDE_DEFAULT_MODEL == EXACT_ID
    assert DEFAULT_LLM_MODELS["claude"] == EXACT_ID
    assert DEFAULT_LLM_MODELS["anthropic"] == EXACT_ID
    assert default_model_for("claude") == EXACT_ID
    assert default_model_for("Claude") == EXACT_ID


@pytest.mark.parametrize("provider,model,expected", [
    ("claude", "", EXACT_ID),
    ("claude", None, EXACT_ID),
    ("claude", "claude-haiku-4-5-20251001", EXACT_ID),   # superseded default written by old setup
    ("anthropic", "claude-haiku-4-5", EXACT_ID),
    ("claude", "claude-opus-4-6", "claude-opus-4-6"),   # explicit user choice is kept
    ("openai", "", "gpt-4o-mini"),
    ("openai", "gpt-4o", "gpt-4o"),
    ("gemini", "", "gemini-2.0-flash"),
])
def test_normalize_llm_model(provider, model, expected):
    assert normalize_llm_model(provider, model) == expected


def test_settings_upgrade_old_client_config():
    """Marek's config.yaml (written by 3.2.3 setup) carries the old Haiku default."""
    reset_settings()
    s = Settings(llm={"enabled": True, "provider": "claude", "api_key": "sk-x",
                      "model": "claude-haiku-4-5-20251001"})
    assert s.llm.model == EXACT_ID
    s2 = Settings(llm={"enabled": True, "provider": "claude", "api_key": "sk-x", "model": "claude-opus-4-6"})
    assert s2.llm.model == "claude-opus-4-6"
    reset_settings()


def test_cli_setup_default_is_sonnet_46(monkeypatch, tmp_path):
    """Drive `udzialy setup` non-interactively: token, id, key, provider 1, Enter for model."""
    import udzialy_cli

    monkeypatch.setattr(udzialy_cli, "APP_DIR", tmp_path)
    monkeypatch.setattr(udzialy_cli, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(udzialy_cli, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(udzialy_cli, "TOR_DATA_DIR", tmp_path / "tor")
    answers = iter(["123:ABC", "42", "sk-ant-test", "1", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    assert udzialy_cli.cmd_setup(None) == 0
    import yaml
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["llm"] == {"enabled": True, "provider": "claude", "api_key": "sk-ant-test", "model": EXACT_ID}

    # Re-running setup and pressing Enter keeps token, id and API key (was: key wiped)
    answers = iter(["", "", "", "1", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert udzialy_cli.cmd_setup(None) == 0
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["telegram"] == {"token": "123:ABC", "owner_id": 42}
    assert cfg["llm"]["api_key"] == "sk-ant-test" and cfg["llm"]["model"] == EXACT_ID


@pytest.mark.asyncio
async def test_ai_chat_sends_sonnet_46_to_anthropic(monkeypatch):
    """call_ai(provider='claude', model='') must POST model=claude-sonnet-4-6 to the Messages API."""
    import httpx
    import bot.routers.ai_chat as ai

    captured = {}

    async def fake_post(self, url, headers=None, json=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    r = await ai.call_ai("szukaj w Gdyni", [], "brak", provider="claude", api_key="sk-ant-x", model="")
    assert r.error is None and r.text == "ok"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["json"]["model"] == EXACT_ID
    assert captured["headers"]["x-api-key"] == "sk-ant-x"
    # old default in an existing config is upgraded too
    await ai.call_ai("x", [], "brak", provider="claude", api_key="k", model="claude-haiku-4-5-20251001")
    assert captured["json"]["model"] == EXACT_ID
    # explicit choice honoured
    await ai.call_ai("x", [], "brak", provider="claude", api_key="k", model="claude-opus-4-6")
    assert captured["json"]["model"] == "claude-opus-4-6"
    # no assistant prefill anywhere in the request (rejected by 4.6+)
    assert all(m["role"] == "user" for m in captured["json"]["messages"])


def test_analyzer_pricing_knows_sonnet_46():
    from detector.llm_analyzer import COST_PER_1M
    assert COST_PER_1M[EXACT_ID] == (3.00, 15.00)
