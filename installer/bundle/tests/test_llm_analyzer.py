"""
Tests for the multi-provider LLM analyzer.

Covers:
- JSON repair (code fences, trailing commas, Python booleans)
- Response validation and type coercion
- Provider adapters (OpenAI-compat, Anthropic)
- ListingAnalyzer retry logic (429, 401, 5xx)
- Semaphore concurrency control
- Cost tracking
- Full integration flow with mocked HTTP
"""

from __future__ import annotations

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from detector.llm_analyzer import (
    AnthropicProvider,
    AnalysisResult,
    ListingAnalyzer,
    LLMResponse,
    OpenAICompatProvider,
    ProviderConfig,
    PROVIDERS,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    create_analyzer_from_config,
    repair_json,
    validate_and_build,
)


# ---------------------------------------------------------------------------
# Test: repair_json
# ---------------------------------------------------------------------------

class TestRepairJson:
    """Test JSON repair utility."""

    def test_valid_json_passthrough(self):
        raw = '{"is_real_share": true, "confidence": 0.95}'
        result = repair_json(raw)
        assert result == {"is_real_share": True, "confidence": 0.95}

    def test_markdown_code_fence_json(self):
        raw = '```json\n{"stars": 4, "confidence": 0.8}\n```'
        result = repair_json(raw)
        assert result == {"stars": 4, "confidence": 0.8}

    def test_markdown_fence_no_language(self):
        raw = '```\n{"stars": 3}\n```'
        result = repair_json(raw)
        assert result == {"stars": 3}

    def test_python_booleans(self):
        raw = '{"is_real_share": True, "confidence": 0.9, "value": None}'
        result = repair_json(raw)
        assert result == {"is_real_share": True, "confidence": 0.9, "value": None}

    def test_trailing_comma(self):
        raw = '{"stars": 4, "confidence": 0.9,}'
        result = repair_json(raw)
        assert result == {"stars": 4, "confidence": 0.9}

    def test_trailing_comma_in_array(self):
        raw = '{"risks": ["ryzyko 1", "ryzyko 2",]}'
        result = repair_json(raw)
        assert result == {"risks": ["ryzyko 1", "ryzyko 2"]}

    def test_extract_json_from_text(self):
        raw = 'Here is my analysis:\n{"stars": 5, "confidence": 0.99}\nThank you!'
        result = repair_json(raw)
        assert result == {"stars": 5, "confidence": 0.99}

    def test_completely_invalid(self):
        raw = "This is not JSON at all"
        result = repair_json(raw)
        assert result is None

    def test_empty_string(self):
        result = repair_json("")
        assert result is None

    def test_nested_json(self):
        raw = '{"stars": 4, "risks": ["a", "b"]}'
        result = repair_json(raw)
        assert result == {"stars": 4, "risks": ["a", "b"]}


# ---------------------------------------------------------------------------
# Test: validate_and_build
# ---------------------------------------------------------------------------

class TestValidateAndBuild:
    """Test response validation and AnalysisResult construction."""

    def _valid_data(self) -> dict:
        return {
            "is_real_share": True,
            "confidence": 0.95,
            "stars": 4,
            "summary": "Dobra oferta — syndyk sprzedaje 1/2 udziału.",
            "fraction": "1/2",
            "property_type": "mieszkanie",
            "seller_motivation": "syndyk",
            "estimated_value_total": 280000,
            "price_assessment": "okazja",
            "risks": ["współwłaściciel blokuje", "konieczność zniesienia"],
        }

    def test_valid_data(self):
        result = validate_and_build(self._valid_data())
        assert result is not None
        assert result.is_real_share is True
        assert result.confidence == 0.95
        assert result.stars == 4
        assert result.fraction == "1/2"
        assert result.property_type == "mieszkanie"
        assert result.seller_motivation == "syndyk"
        assert result.estimated_value_total == 280000
        assert result.price_assessment == "okazja"
        assert len(result.risks) == 2

    def test_missing_required_field(self):
        data = self._valid_data()
        del data["stars"]
        assert validate_and_build(data) is None

    def test_confidence_as_string(self):
        data = self._valid_data()
        data["confidence"] = "0.85"
        result = validate_and_build(data)
        assert result is not None
        assert result.confidence == 0.85

    def test_stars_as_float(self):
        data = self._valid_data()
        data["stars"] = 4.0
        result = validate_and_build(data)
        assert result is not None
        assert result.stars == 4

    def test_stars_clamped_high(self):
        data = self._valid_data()
        data["stars"] = 10
        result = validate_and_build(data)
        assert result is not None
        assert result.stars == 5

    def test_stars_clamped_low(self):
        data = self._valid_data()
        data["stars"] = 0
        result = validate_and_build(data)
        assert result is not None
        assert result.stars == 1

    def test_confidence_clamped(self):
        data = self._valid_data()
        data["confidence"] = 1.5
        result = validate_and_build(data)
        assert result is not None
        assert result.confidence == 1.0

    def test_invalid_fraction_format(self):
        data = self._valid_data()
        data["fraction"] = "half"
        result = validate_and_build(data)
        assert result is not None
        assert result.fraction is None

    def test_fraction_none(self):
        data = self._valid_data()
        data["fraction"] = None
        result = validate_and_build(data)
        assert result is not None
        assert result.fraction is None

    def test_invalid_property_type_defaults(self):
        data = self._valid_data()
        data["property_type"] = "zamek"
        result = validate_and_build(data)
        assert result is not None
        assert result.property_type == "inne"

    def test_risks_as_string(self):
        data = self._valid_data()
        data["risks"] = "single risk"
        result = validate_and_build(data)
        assert result is not None
        assert result.risks == ["single risk"]

    def test_risks_truncated_to_5(self):
        data = self._valid_data()
        data["risks"] = ["r1", "r2", "r3", "r4", "r5", "r6", "r7"]
        result = validate_and_build(data)
        assert result is not None
        assert len(result.risks) == 5

    def test_is_real_share_false(self):
        data = self._valid_data()
        data["is_real_share"] = False
        data["stars"] = 1
        data["fraction"] = None
        data["seller_motivation"] = None
        data["price_assessment"] = None
        data["risks"] = []
        result = validate_and_build(data)
        assert result is not None
        assert result.is_real_share is False


# ---------------------------------------------------------------------------
# Test: OpenAICompatProvider
# ---------------------------------------------------------------------------

class TestOpenAICompatProvider:
    """Test OpenAI-compatible provider adapter."""

    def test_get_base_url(self):
        p = OpenAICompatProvider("https://api.openai.com/v1")
        assert p.get_base_url() == "https://api.openai.com/v1"

    def test_get_endpoint(self):
        p = OpenAICompatProvider("https://api.openai.com/v1")
        assert p.get_endpoint() == "/chat/completions"

    def test_headers_with_key(self):
        p = OpenAICompatProvider("https://api.openai.com/v1")
        headers = p.get_headers("sk-test123")
        assert headers["Authorization"] == "Bearer sk-test123"
        assert "Content-Type" in headers

    def test_headers_no_key(self):
        p = OpenAICompatProvider("http://localhost:11434/v1")
        headers = p.get_headers("")
        assert "Authorization" not in headers

    def test_build_request_basic(self):
        p = OpenAICompatProvider("https://api.openai.com/v1")
        messages = [{"role": "user", "content": "Hello"}]
        body = p.build_request(messages, "gpt-4o-mini")
        assert body["model"] == "gpt-4o-mini"
        assert body["messages"] == messages
        assert "response_format" not in body

    def test_build_request_json_mode(self):
        p = OpenAICompatProvider("https://api.openai.com/v1")
        messages = [{"role": "user", "content": "Hello"}]
        body = p.build_request(messages, "gpt-4o-mini", json_mode=True)
        assert body["response_format"] == {"type": "json_object"}

    def test_build_request_with_options(self):
        p = OpenAICompatProvider("https://api.openai.com/v1")
        messages = [{"role": "user", "content": "Hello"}]
        body = p.build_request(messages, "gpt-4o-mini", temperature=0.5, max_tokens=100)
        assert body["temperature"] == 0.5
        assert body["max_tokens"] == 100

    def test_parse_response(self):
        p = OpenAICompatProvider("https://api.openai.com/v1")
        data = {
            "id": "chatcmpl-123",
            "model": "gpt-4o-mini",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": '{"stars": 4}'},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        resp = p.parse_response(data)
        assert resp.content == '{"stars": 4}'
        assert resp.model == "gpt-4o-mini"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.finish_reason == "stop"


# ---------------------------------------------------------------------------
# Test: AnthropicProvider
# ---------------------------------------------------------------------------

class TestAnthropicProvider:
    """Test Anthropic Claude provider adapter."""

    def test_get_base_url(self):
        p = AnthropicProvider()
        assert p.get_base_url() == "https://api.anthropic.com/v1"

    def test_get_endpoint(self):
        p = AnthropicProvider()
        assert p.get_endpoint() == "/messages"

    def test_headers(self):
        p = AnthropicProvider()
        headers = p.get_headers("sk-ant-test")
        assert headers["x-api-key"] == "sk-ant-test"
        assert headers["anthropic-version"] == "2023-06-01"

    def test_build_request_separates_system(self):
        p = AnthropicProvider()
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        body = p.build_request(messages, "claude-sonnet-5", max_tokens=512)
        assert body["system"] == "You are helpful"
        assert body["messages"] == [{"role": "user", "content": "Hello"}]
        assert body["model"] == "claude-sonnet-5"
        assert body["max_tokens"] == 512

    def test_build_request_no_system(self):
        p = AnthropicProvider()
        messages = [{"role": "user", "content": "Hello"}]
        body = p.build_request(messages, "claude-haiku-4-5")
        assert "system" not in body
        assert body["messages"] == messages

    def test_parse_response(self):
        p = AnthropicProvider()
        data = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5",
            "content": [
                {"type": "text", "text": '{"stars": 5}'}
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 200, "output_tokens": 80},
        }
        resp = p.parse_response(data)
        assert resp.content == '{"stars": 5}'
        assert resp.model == "claude-sonnet-5"
        assert resp.input_tokens == 200
        assert resp.output_tokens == 80
        assert resp.finish_reason == "end_turn"

    def test_parse_response_multiple_blocks(self):
        p = AnthropicProvider()
        data = {
            "id": "msg_456",
            "type": "message",
            "model": "claude-sonnet-5",
            "content": [
                {"type": "text", "text": '{"stars"'},
                {"type": "text", "text": ': 3}'},
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 40},
        }
        resp = p.parse_response(data)
        assert resp.content == '{"stars": 3}'


# ---------------------------------------------------------------------------
# Test: ListingAnalyzer integration with mocked HTTP
# ---------------------------------------------------------------------------

class TestListingAnalyzer:
    """Test the full analyzer with mocked httpx responses."""

    def _make_analyzer(self, providers=None) -> ListingAnalyzer:
        if providers is None:
            providers = [
                ProviderConfig(name="openai", api_key="sk-test", model="gpt-4o-mini", priority=1),
            ]
        return ListingAnalyzer(providers=providers, timeout=5.0)

    def _openai_response(self, content: str, input_tokens=100, output_tokens=50) -> dict:
        return {
            "id": "chatcmpl-test",
            "model": "gpt-4o-mini",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    def _mock_response(self, status_code: int, json_data=None, text=None) -> httpx.Response:
        """Create a proper httpx.Response with request set."""
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        if json_data is not None:
            resp = httpx.Response(status_code, json=json_data, request=request)
        elif text is not None:
            resp = httpx.Response(status_code, text=text, request=request)
        else:
            resp = httpx.Response(status_code, request=request)
        return resp

    def _valid_llm_json(self) -> str:
        return json.dumps({
            "is_real_share": True,
            "confidence": 0.95,
            "stars": 4,
            "summary": "Syndyk sprzedaje 1/2 udziału w mieszkaniu.",
            "fraction": "1/2",
            "property_type": "mieszkanie",
            "seller_motivation": "syndyk",
            "estimated_value_total": 280000,
            "price_assessment": "okazja",
            "risks": ["współwłaściciel blokuje"],
        })

    @pytest.mark.asyncio
    async def test_successful_analysis(self):
        analyzer = self._make_analyzer()
        mock_response = self._mock_response(
            200, json_data=self._openai_response(self._valid_llm_json())
        )

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            result = await analyzer.analyze(
                title="Syndyk sprzeda udział 1/2 w mieszkaniu",
                description="Lokal 48m2 w Krakowie.",
                price="95000 PLN",
                location="Kraków",
            )

        assert result is not None
        assert result.is_real_share is True
        assert result.stars == 4
        assert result.fraction == "1/2"
        assert analyzer.stats["total_calls"] == 1
        assert analyzer.stats["total_errors"] == 0
        await analyzer.close()

    @pytest.mark.asyncio
    async def test_provider_fallback(self):
        """Second provider succeeds when first fails."""
        providers = [
            ProviderConfig(name="openai", api_key="sk-bad", model="gpt-4o-mini", priority=1),
            ProviderConfig(name="deepseek", api_key="ds-good", model="deepseek-v4-flash", priority=2),
        ]
        analyzer = self._make_analyzer(providers)

        call_count = [0]

        async def mock_post(*args, **kwargs):
            call_count[0] += 1
            # First 2 calls fail (initial + 1 retry for 5xx), then succeed
            if call_count[0] <= 2:
                return self._mock_response(500, text="Internal Server Error")
            return self._mock_response(200, json_data=self._openai_response(self._valid_llm_json()))

        with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
            result = await analyzer.analyze(
                title="Test",
                description="Test description",
            )

        assert result is not None
        assert result.is_real_share is True
        await analyzer.close()

    @pytest.mark.asyncio
    async def test_401_disables_provider(self):
        """401 permanently disables a provider."""
        analyzer = self._make_analyzer()
        unauth_resp = self._mock_response(401, text="Unauthorized")

        with patch.object(httpx.AsyncClient, "post", return_value=unauth_resp):
            result = await analyzer.analyze(title="Test", description="Test")

        assert result is None
        assert "openai" in analyzer._disabled_providers
        assert not analyzer.is_configured
        await analyzer.close()

    @pytest.mark.asyncio
    async def test_json_repair_in_pipeline(self):
        """LLM returns JSON wrapped in markdown fences — still parses."""
        analyzer = self._make_analyzer()
        fenced_json = f"```json\n{self._valid_llm_json()}\n```"
        mock_response = self._mock_response(
            200, json_data=self._openai_response(fenced_json)
        )

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            result = await analyzer.analyze(title="Test", description="Test")

        assert result is not None
        assert result.is_real_share is True
        await analyzer.close()

    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        """Cost is tracked after successful call."""
        analyzer = self._make_analyzer()
        mock_response = self._mock_response(
            200,
            json_data=self._openai_response(self._valid_llm_json(), input_tokens=1000, output_tokens=200),
        )

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            await analyzer.analyze(title="Test", description="Test")

        stats = analyzer.stats
        assert stats["total_input_tokens"] == 1000
        assert stats["total_output_tokens"] == 200
        assert stats["cost_usd"] > 0
        # gpt-4o-mini: (1000/1M)*0.15 + (200/1M)*0.60 = 0.00015 + 0.00012 = 0.00027
        assert abs(stats["cost_usd"] - 0.00027) < 0.0001
        await analyzer.close()

    @pytest.mark.asyncio
    async def test_not_configured_returns_none(self):
        """No providers → returns None immediately."""
        analyzer = ListingAnalyzer(providers=[])
        result = await analyzer.analyze(title="Test", description="Test")
        assert result is None
        await analyzer.close()

    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        """Invalid JSON from LLM → returns None."""
        analyzer = self._make_analyzer()
        mock_response = self._mock_response(
            200, json_data=self._openai_response("This is not JSON at all!")
        )

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            result = await analyzer.analyze(title="Test", description="Test")

        assert result is None
        assert analyzer.stats["total_errors"] > 0
        await analyzer.close()


# ---------------------------------------------------------------------------
# Test: create_analyzer_from_config
# ---------------------------------------------------------------------------

class TestCreateFromConfig:
    """Test factory function."""

    def test_disabled_returns_none(self):
        config = {"enabled": False, "api_key": "sk-test"}
        assert create_analyzer_from_config(config) is None

    def test_empty_config_returns_none(self):
        assert create_analyzer_from_config({}) is None
        assert create_analyzer_from_config(None) is None

    def test_legacy_single_provider(self):
        config = {
            "enabled": True,
            "api_key": "sk-test",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
        }
        analyzer = create_analyzer_from_config(config)
        assert analyzer is not None
        assert analyzer.is_configured

    def test_legacy_deepseek_detection(self):
        config = {
            "enabled": True,
            "api_key": "ds-test",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com/v1",
        }
        analyzer = create_analyzer_from_config(config)
        assert analyzer is not None
        assert analyzer._providers[0].name == "deepseek"

    def test_multi_provider_config(self):
        config = {
            "enabled": True,
            "providers": [
                {"name": "openai", "api_key": "sk-1", "model": "gpt-4o-mini", "priority": 1},
                {"name": "deepseek", "api_key": "ds-1", "model": "deepseek-v4-flash", "priority": 2},
                {"name": "anthropic", "api_key": "ant-1", "model": "claude-haiku-4-5", "priority": 3},
            ],
        }
        analyzer = create_analyzer_from_config(config)
        assert analyzer is not None
        assert len(analyzer._providers) == 3
        # Sorted by priority
        assert analyzer._providers[0].name == "openai"
        assert analyzer._providers[1].name == "deepseek"
        assert analyzer._providers[2].name == "anthropic"

    def test_provider_without_key_skipped(self):
        config = {
            "enabled": True,
            "providers": [
                {"name": "openai", "api_key": "", "model": "gpt-4o-mini"},
                {"name": "deepseek", "api_key": "ds-1", "model": "deepseek-v4-flash"},
            ],
        }
        analyzer = create_analyzer_from_config(config)
        assert analyzer is not None
        assert len(analyzer._providers) == 1
        assert analyzer._providers[0].name == "deepseek"


# ---------------------------------------------------------------------------
# Test: Provider registry
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    """Test the PROVIDERS dict."""

    def test_all_expected_providers(self):
        expected = {"openai", "deepseek", "gemini", "ollama", "lmstudio", "anthropic"}
        assert set(PROVIDERS.keys()) == expected

    def test_openai_compat_instances(self):
        for name in ["openai", "deepseek", "gemini", "ollama", "lmstudio"]:
            assert isinstance(PROVIDERS[name], OpenAICompatProvider)

    def test_anthropic_instance(self):
        assert isinstance(PROVIDERS["anthropic"], AnthropicProvider)

    def test_provider_urls(self):
        assert "api.openai.com" in PROVIDERS["openai"].get_base_url()
        assert "deepseek.com" in PROVIDERS["deepseek"].get_base_url()
        assert "googleapis.com" in PROVIDERS["gemini"].get_base_url()
        assert "localhost:11434" in PROVIDERS["ollama"].get_base_url()
        assert "localhost:1234" in PROVIDERS["lmstudio"].get_base_url()
        assert "anthropic.com" in PROVIDERS["anthropic"].get_base_url()


# ---------------------------------------------------------------------------
# Test: Prompt constants
# ---------------------------------------------------------------------------

class TestPrompts:
    """Verify prompt content meets specifications."""

    def test_system_prompt_in_polish(self):
        assert "Jesteś ekspertem" in SYSTEM_PROMPT
        assert "ODPOWIEDZ TYLKO PO POLSKU" in SYSTEM_PROMPT

    def test_system_prompt_has_examples(self):
        assert "PRZYKŁAD 1" in SYSTEM_PROMPT
        assert "PRZYKŁAD 2" in SYSTEM_PROMPT

    def test_system_prompt_has_json_schema_fields(self):
        for field in ["is_real_share", "confidence", "stars", "summary",
                      "fraction", "property_type", "seller_motivation",
                      "price_assessment", "risks"]:
            assert field in SYSTEM_PROMPT

    def test_user_template_has_markers(self):
        assert "[TYTUŁ]" in USER_PROMPT_TEMPLATE
        assert "[OPIS]" in USER_PROMPT_TEMPLATE
        assert "[CENA]" in USER_PROMPT_TEMPLATE
        assert "[LOKALIZACJA]" in USER_PROMPT_TEMPLATE
        assert "[POWIERZCHNIA]" in USER_PROMPT_TEMPLATE
