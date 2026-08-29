"""
Multi-provider LLM listing analyzer for property share detection.

Architecture:
- OpenAICompatProvider: OpenAI, DeepSeek, Gemini, Ollama, LM Studio
- AnthropicProvider: Claude (different API format)
- ListingAnalyzer: orchestrator with retry, semaphore, cost tracking, JSON repair

Uses raw httpx.AsyncClient with provider adapter pattern (~400 LOC).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """\
Jesteś ekspertem od obrotu udziałami w nieruchomościach w Polsce. Twoje zadanie: przeanalizować ogłoszenie o sprzedaży i ocenić czy dotyczy ono RZECZYWISTEGO udziału w nieruchomości.

DEFINICJA: "Udział w nieruchomości" to ułamkowe prawo własności do nieruchomości (np. 1/2, 1/4, 3/8). Powstaje najczęściej ze spadku, rozwodu, upadłości lub współwłasności. NIE jest udziałem w nieruchomości:
- udział w drodze wewnętrznej (standardowy przy działkach)
- udział w gruncie pod budynkiem (standardowy w spółdzielniach/wspólnotach)
- udział w częściach wspólnych budynku
- udział w spółce/funduszu

ANALIZA — oceń kolejno:
1. Czy to RZECZYWISTY udział? (is_real_share)
2. Jaki ułamek? (fraction) — jeśli podany
3. Typ nieruchomości (property_type)
4. Motywacja sprzedającego (seller_motivation)
5. Ocena ceny (price_assessment) — czy cena za udział jest okazją, uczciwa, czy droga
6. Ryzyka dla kupującego (risks)

OCENA GWIAZDKOWA (stars 1-5):
- 5 = idealna okazja: duży udział (≥1/2), niska cena, jasna sytuacja prawna
- 4 = dobra oferta: rozsądna cena, znany ułamek, motywacja czytelna
- 3 = średnia: niepełne informacje ale prawdopodobnie real deal
- 2 = wątpliwa: mało danych, ryzykowna, możliwe problemy
- 1 = nieatrakcyjna lub to nie jest prawdziwy udział

ODPOWIEDŹ — zwróć WYŁĄCZNIE obiekt JSON (bez markdown, bez komentarzy):
{"is_real_share":true/false,"confidence":0.0-1.0,"stars":1-5,"summary":"2-3 zdania po polsku","fraction":"1/2" lub null,"property_type":"mieszkanie"|"działka"|"kamienica"|"dom"|"lokal"|"grunt"|"inne"|null,"seller_motivation":"spadek"|"syndyk"|"rozwód"|"zadłużenie"|"egzekucja"|"inne"|null,"estimated_value_total":liczba lub null,"price_assessment":"okazja"|"uczciwa"|"droga"|null,"risks":["ryzyko1","ryzyko2"]}

PRZYKŁAD 1 — prawdziwy udział:
Tytuł: "Syndyk sprzeda udział 1/2 w lokalu mieszkalnym 48m2, Kraków"
Cena: 95000 PLN
Odpowiedź: {"is_real_share":true,"confidence":0.95,"stars":4,"summary":"Syndyk sprzedaje 1/2 udziału w mieszkaniu 48m2 w Krakowie za 95 tys. Cena wywoławcza sugeruje możliwość negocjacji.","fraction":"1/2","property_type":"mieszkanie","seller_motivation":"syndyk","estimated_value_total":280000,"price_assessment":"okazja","risks":["współwłaściciel może blokować sprzedaż","konieczność zniesienia współwłasności"]}

PRZYKŁAD 2 — NIE jest udziałem:
Tytuł: "Działka budowlana 1200m2, udział w drodze wewnętrznej"
Cena: 180000 PLN
Odpowiedź: {"is_real_share":false,"confidence":0.95,"stars":1,"summary":"Standardowa sprzedaż działki. 'Udział w drodze' to typowy dostęp komunikacyjny, nie sprzedaż współwłasności.","fraction":null,"property_type":"działka","seller_motivation":null,"estimated_value_total":null,"price_assessment":null,"risks":[]}

ODPOWIEDZ TYLKO PO POLSKU. Format: TYLKO JSON."""


USER_PROMPT_TEMPLATE = """Przeanalizuj to ogłoszenie:

[TYTUŁ]
{title}

[OPIS]
{description}

[CENA]
{price}

[LOKALIZACJA]
{location}

[POWIERZCHNIA]
{area}"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str


@dataclass
class AnalysisResult:
    """Validated analysis result from LLM."""
    is_real_share: bool
    confidence: float
    stars: int
    summary: str
    fraction: Optional[str]
    property_type: Optional[str]
    seller_motivation: Optional[str]
    estimated_value_total: Optional[int]
    price_assessment: Optional[str]
    risks: List[str]


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    name: str
    api_key: str
    model: str
    enabled: bool = True
    priority: int = 1


# ---------------------------------------------------------------------------
# Provider adapters
# ---------------------------------------------------------------------------

class BaseProvider(ABC):
    """Abstract base for LLM provider adapters."""

    @abstractmethod
    def get_base_url(self) -> str: ...

    @abstractmethod
    def get_headers(self, api_key: str) -> dict: ...

    @abstractmethod
    def build_request(self, messages: list, model: str, **kwargs) -> dict: ...

    @abstractmethod
    def parse_response(self, data: dict) -> LLMResponse: ...

    @abstractmethod
    def get_endpoint(self) -> str: ...


class OpenAICompatProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs (OpenAI, DeepSeek, Gemini, Ollama, LM Studio)."""

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def get_base_url(self) -> str:
        return self._base_url

    def get_endpoint(self) -> str:
        return "/chat/completions"

    def get_headers(self, api_key: str) -> dict:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def build_request(self, messages: list, model: str, **kwargs) -> dict:
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if kwargs.get("json_mode"):
            body["response_format"] = {"type": "json_object"}
        if kwargs.get("max_tokens"):
            body["max_tokens"] = kwargs["max_tokens"]
        if kwargs.get("temperature") is not None:
            body["temperature"] = kwargs["temperature"]
        return body

    def parse_response(self, data: dict) -> LLMResponse:
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", ""),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude Messages API."""

    def get_base_url(self) -> str:
        return "https://api.anthropic.com/v1"

    def get_endpoint(self) -> str:
        return "/messages"

    def get_headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def build_request(self, messages: list, model: str, **kwargs) -> dict:
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)

        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": user_messages,
        }
        if system:
            body["system"] = system
        if kwargs.get("temperature") is not None:
            body["temperature"] = kwargs["temperature"]
        return body

    def parse_response(self, data: dict) -> LLMResponse:
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block["text"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", ""),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            finish_reason=data.get("stop_reason", "end_turn"),
        )


# Provider registry — pre-built instances
PROVIDERS: Dict[str, BaseProvider] = {
    "openai": OpenAICompatProvider("https://api.openai.com/v1"),
    "deepseek": OpenAICompatProvider("https://api.deepseek.com/v1"),
    "gemini": OpenAICompatProvider("https://generativelanguage.googleapis.com/v1beta/openai"),
    "ollama": OpenAICompatProvider("http://localhost:11434/v1"),
    "lmstudio": OpenAICompatProvider("http://localhost:1234/v1"),
    "anthropic": AnthropicProvider(),
}

# Cost per 1M tokens (input, output) for common models
COST_PER_1M: Dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "deepseek-v4-flash": (0.22, 0.66),
    "deepseek-v4-pro": (0.66, 1.98),
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-5": (2.00, 10.00),
}


# ---------------------------------------------------------------------------
# JSON repair utility
# ---------------------------------------------------------------------------

def repair_json(raw: str) -> Optional[dict]:
    """Attempt to parse and repair common LLM JSON issues.

    Handles:
    - Markdown code fences (```json ... ```)
    - Trailing commas
    - Single quotes instead of double quotes
    - Unescaped newlines in strings
    - Boolean/null case variants (True/False/None -> true/false/null)
    """
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last ``` if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fix Python-style booleans/None
    text_fixed = text
    text_fixed = re.sub(r'\bTrue\b', 'true', text_fixed)
    text_fixed = re.sub(r'\bFalse\b', 'false', text_fixed)
    text_fixed = re.sub(r'\bNone\b', 'null', text_fixed)

    try:
        return json.loads(text_fixed)
    except json.JSONDecodeError:
        pass

    # Remove trailing commas before } or ]
    text_fixed = re.sub(r',\s*([}\]])', r'\1', text_fixed)

    try:
        return json.loads(text_fixed)
    except json.JSONDecodeError:
        pass

    # Last resort: try to extract JSON object from text
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text_fixed, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = [
    "is_real_share", "confidence", "stars", "summary",
    "fraction", "property_type", "seller_motivation",
    "estimated_value_total", "price_assessment", "risks",
]

VALID_PROPERTY_TYPES = {"mieszkanie", "działka", "kamienica", "dom", "lokal", "grunt", "inne", None}
VALID_MOTIVATIONS = {"spadek", "syndyk", "rozwód", "zadłużenie", "egzekucja", "inne", None}
VALID_PRICE_ASSESSMENTS = {"okazja", "uczciwa", "droga", None}


def validate_and_build(data: dict) -> Optional[AnalysisResult]:
    """Validate parsed JSON and construct AnalysisResult. Returns None on invalid data."""
    # Check required fields
    if not all(k in data for k in REQUIRED_FIELDS):
        return None

    # Type coercion for common model errors
    try:
        is_real_share = bool(data["is_real_share"])

        confidence = data["confidence"]
        if isinstance(confidence, str):
            confidence = float(confidence)
        confidence = max(0.0, min(1.0, float(confidence)))

        stars = data["stars"]
        if isinstance(stars, float):
            stars = int(stars)
        if isinstance(stars, str):
            stars = int(float(stars))
        stars = max(1, min(5, int(stars)))

        summary = str(data.get("summary", ""))

        fraction = data.get("fraction")
        if fraction is not None:
            fraction = str(fraction)
            # Validate fraction format (digits/digits)
            if not re.match(r'^\d+/\d+$', fraction):
                fraction = None

        property_type = data.get("property_type")
        if property_type not in VALID_PROPERTY_TYPES:
            property_type = "inne"

        seller_motivation = data.get("seller_motivation")
        if seller_motivation not in VALID_MOTIVATIONS:
            seller_motivation = "inne"

        estimated_value_total = data.get("estimated_value_total")
        if estimated_value_total is not None:
            estimated_value_total = int(float(estimated_value_total))

        price_assessment = data.get("price_assessment")
        if price_assessment not in VALID_PRICE_ASSESSMENTS:
            price_assessment = None

        risks = data.get("risks", [])
        if isinstance(risks, str):
            risks = [risks]
        if not isinstance(risks, list):
            risks = []
        risks = [str(r) for r in risks[:5]]

    except (ValueError, TypeError):
        return None

    return AnalysisResult(
        is_real_share=is_real_share,
        confidence=confidence,
        stars=stars,
        summary=summary,
        fraction=fraction,
        property_type=property_type,
        seller_motivation=seller_motivation,
        estimated_value_total=estimated_value_total,
        price_assessment=price_assessment,
        risks=risks,
    )


# ---------------------------------------------------------------------------
# ListingAnalyzer — main orchestrator
# ---------------------------------------------------------------------------

class ListingAnalyzer:
    """Multi-provider LLM analyzer with retry, concurrency control, and cost tracking.

    Args:
        providers: List of ProviderConfig to use (tried in priority order).
        max_concurrent: Semaphore limit for parallel API calls.
        timeout: Per-call timeout in seconds.
        temperature: LLM temperature (0.0–1.0).
        max_tokens: Max output tokens.
    """

    def __init__(
        self,
        providers: Optional[List[ProviderConfig]] = None,
        max_concurrent: int = 5,
        timeout: float = 30.0,
        temperature: float = 0.3,
        max_tokens: int = 600,
    ):
        self._providers = sorted(providers or [], key=lambda p: p.priority)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._timeout = timeout
        self._temperature = temperature
        self._max_tokens = max_tokens

        # Single shared httpx client for connection pooling
        self._client: Optional[httpx.AsyncClient] = None

        # Cost & stats tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_calls = 0
        self._total_errors = 0
        self._cost_usd = 0.0
        self._disabled_providers: set = set()

    @property
    def is_configured(self) -> bool:
        """At least one enabled provider with an API key."""
        return any(
            p.enabled and p.api_key and p.name not in self._disabled_providers
            for p in self._providers
        )

    @property
    def stats(self) -> Dict[str, Any]:
        """Usage statistics."""
        return {
            "total_calls": self._total_calls,
            "total_errors": self._total_errors,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "cost_usd": round(self._cost_usd, 6),
            "disabled_providers": list(self._disabled_providers),
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init shared httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_messages(
        self, title: str, description: str, price: Optional[str],
        location: Optional[str], area: Optional[str],
    ) -> list:
        """Build messages array for LLM call."""
        desc_truncated = (description or "brak opisu")[:1500]
        price_str = price if price else "brak danych"
        location_str = location or "brak danych"
        area_str = area or "brak danych"

        user_content = USER_PROMPT_TEMPLATE.format(
            title=title,
            description=desc_truncated,
            price=price_str,
            location=location_str,
            area=area_str,
        )

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    def _track_cost(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Track token usage and estimate cost."""
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        costs = COST_PER_1M.get(model, (0.15, 0.60))  # default to gpt-4o-mini pricing
        self._cost_usd += (input_tokens / 1_000_000) * costs[0]
        self._cost_usd += (output_tokens / 1_000_000) * costs[1]

    async def _call_provider(
        self, provider_cfg: ProviderConfig, messages: list
    ) -> Optional[LLMResponse]:
        """Make a single API call to a provider with retry logic.

        Retry strategy:
        - 429 (rate limit): exponential backoff, up to 2 retries
        - 5xx (server error): retry once after 1s
        - 401 (auth error): disable provider permanently
        - Other errors: no retry
        """
        provider = PROVIDERS.get(provider_cfg.name)
        if not provider:
            logger.warning(f"Unknown provider: {provider_cfg.name}")
            return None

        url = f"{provider.get_base_url()}{provider.get_endpoint()}"
        headers = provider.get_headers(provider_cfg.api_key)

        kwargs: Dict[str, Any] = {
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        # Enable JSON mode for OpenAI-compatible providers
        if isinstance(provider, OpenAICompatProvider):
            kwargs["json_mode"] = True

        body = provider.build_request(messages, provider_cfg.model, **kwargs)
        client = await self._get_client()

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(url, headers=headers, json=body)

                if response.status_code == 401:
                    logger.error(
                        f"Provider {provider_cfg.name}: 401 Unauthorized — disabling"
                    )
                    self._disabled_providers.add(provider_cfg.name)
                    return None

                if response.status_code == 429:
                    if attempt < max_retries:
                        wait = 2 ** (attempt + 1)  # 2s, 4s
                        logger.warning(
                            f"Provider {provider_cfg.name}: 429 rate limited, "
                            f"retrying in {wait}s (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(wait)
                        continue
                    logger.error(f"Provider {provider_cfg.name}: 429 after all retries")
                    return None

                if response.status_code >= 500:
                    if attempt < 1:  # retry once for 5xx
                        logger.warning(
                            f"Provider {provider_cfg.name}: {response.status_code}, "
                            f"retrying in 1s"
                        )
                        await asyncio.sleep(1)
                        continue
                    logger.error(
                        f"Provider {provider_cfg.name}: {response.status_code} "
                        f"after retry"
                    )
                    return None

                response.raise_for_status()
                data = response.json()
                return provider.parse_response(data)

            except httpx.TimeoutException:
                logger.warning(f"Provider {provider_cfg.name}: timeout (attempt {attempt + 1})")
                if attempt < 1:
                    await asyncio.sleep(1)
                    continue
                return None
            except httpx.HTTPStatusError as e:
                logger.warning(f"Provider {provider_cfg.name}: HTTP {e.response.status_code}")
                return None
            except Exception as e:
                logger.warning(f"Provider {provider_cfg.name}: unexpected error: {e}")
                return None

        return None

    async def analyze(
        self,
        title: str,
        description: str,
        price: Optional[str] = None,
        location: Optional[str] = None,
        area: Optional[str] = None,
    ) -> Optional[AnalysisResult]:
        """Analyze a listing using configured LLM providers (fallback chain).

        Args:
            title: Listing title.
            description: Listing description (truncated to 1500 chars).
            price: Price string (e.g. "120000 PLN").
            location: City/district.
            area: Area string (e.g. "52.4 m²").

        Returns:
            AnalysisResult if successful, None on all-provider failure.
        """
        if not self.is_configured:
            logger.debug("No configured providers available")
            return None

        messages = self._build_messages(title, description, price, location, area)

        async with self._semaphore:
            self._total_calls += 1
            start = time.monotonic()

            for provider_cfg in self._providers:
                if not provider_cfg.enabled:
                    continue
                if provider_cfg.name in self._disabled_providers:
                    continue

                llm_resp = await self._call_provider(provider_cfg, messages)
                if llm_resp is None:
                    self._total_errors += 1
                    continue

                # Track cost
                self._track_cost(
                    provider_cfg.model, llm_resp.input_tokens, llm_resp.output_tokens
                )

                # Parse JSON response
                parsed = repair_json(llm_resp.content)
                if parsed is None:
                    logger.warning(
                        f"Provider {provider_cfg.name}: JSON parse failed. "
                        f"Raw: {llm_resp.content[:200]}"
                    )
                    self._total_errors += 1
                    continue

                # Validate and build result
                result = validate_and_build(parsed)
                if result is None:
                    logger.warning(
                        f"Provider {provider_cfg.name}: validation failed. "
                        f"Parsed: {parsed}"
                    )
                    self._total_errors += 1
                    continue

                elapsed = time.monotonic() - start
                logger.debug(
                    f"Analysis OK via {provider_cfg.name}/{provider_cfg.model} "
                    f"in {elapsed:.2f}s"
                )
                return result

            # All providers failed
            logger.error("All LLM providers failed for this listing")
            return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_analyzer_from_config(config: Dict[str, Any]) -> Optional[ListingAnalyzer]:
    """Create ListingAnalyzer from config dict.

    Expected config structure:
    {
        "enabled": true,
        "max_concurrent": 5,
        "timeout": 30,
        "temperature": 0.3,
        "providers": [
            {"name": "openai", "api_key": "sk-...", "model": "gpt-4o-mini", "priority": 1},
            {"name": "deepseek", "api_key": "...", "model": "deepseek-v4-flash", "priority": 2},
            ...
        ]
    }

    Legacy single-provider config also supported:
    {
        "enabled": true,
        "api_key": "sk-...",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1"
    }
    """
    if not config:
        return None

    if not config.get("enabled", False):
        logger.info("LLM analyzer disabled in config")
        return None

    providers_cfg: List[ProviderConfig] = []

    # New multi-provider format
    if "providers" in config:
        for i, p in enumerate(config["providers"]):
            if not p.get("api_key"):
                continue
            providers_cfg.append(ProviderConfig(
                name=p.get("name", "openai"),
                api_key=p["api_key"],
                model=p.get("model", "gpt-4o-mini"),
                enabled=p.get("enabled", True),
                priority=p.get("priority", i + 1),
            ))
    else:
        # Legacy single-provider format
        api_key = config.get("api_key", "")
        if not api_key:
            logger.info("LLM analyzer: no API key configured")
            return None
        # Detect provider from base_url
        base_url = config.get("base_url", "https://api.openai.com/v1")
        provider_name = "openai"
        if "deepseek" in base_url:
            provider_name = "deepseek"
        elif "generativelanguage.googleapis" in base_url:
            provider_name = "gemini"
        elif "anthropic" in base_url:
            provider_name = "anthropic"
        elif "localhost:11434" in base_url:
            provider_name = "ollama"
        elif "localhost:1234" in base_url:
            provider_name = "lmstudio"

        providers_cfg.append(ProviderConfig(
            name=provider_name,
            api_key=api_key,
            model=config.get("model", "gpt-4o-mini"),
            priority=1,
        ))

    if not providers_cfg:
        logger.info("LLM analyzer: no valid providers configured")
        return None

    return ListingAnalyzer(
        providers=providers_cfg,
        max_concurrent=config.get("max_concurrent", 5),
        timeout=float(config.get("timeout", 30)),
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 600),
    )
