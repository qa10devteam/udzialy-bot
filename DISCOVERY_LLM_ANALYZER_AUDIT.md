# DISCOVERY LOOP 2: LLM Analyzer Audit

> Date: 2026-08-22  
> File: `/home/ubuntu/udzialy-bot/detector/llm_analyzer.py` (324 lines, 10930 bytes)  
> Reference: `/home/ubuntu/udzialy-bot/RESEARCH_MULTI_LLM_API.md`

---

## Executive Summary

The existing `llm_analyzer.py` is a **solid foundation** but only supports **OpenAI-compatible providers**. It does NOT handle Claude's different API format, has minimal error handling (no retry, no 429/401 differentiation), and hardcodes cost to gpt-4o-mini pricing. It needs a **provider adapter layer** to support all 6 providers.

**Verdict: ~60% complete.** Good structure, needs multi-provider adapter and proper error handling.

---

## Detailed Audit

### ✅ WHAT'S GOOD

| Feature | Status | Notes |
|---------|--------|-------|
| Async httpx usage | ✅ Good | Raw httpx.AsyncClient, no heavy SDK deps |
| Semaphore for max_concurrent | ✅ Good | `asyncio.Semaphore(max_concurrent)` on line 108 |
| Cost tracking (tokens) | ✅ Good | Tracks prompt/completion tokens, has `cost_estimate` property |
| JSON parsing with fallback | ✅ Good | Handles markdown code fences, clamps stars 1-5 |
| System prompt | ✅ Excellent | Polish real estate share expert, proper JSON schema instruction |
| AnalysisResult dataclass | ✅ Good | Clean typed result with key_facts dict |
| Factory from config | ✅ Good | `create_analyzer_from_config()` reads yaml section |
| Graceful None return | ✅ Good | Any error → None, bot continues without LLM |
| Timeout (15s) | ✅ OK | Configured per-instance, passed to httpx |
| Description truncation | ✅ Good | Truncates to 1500 chars to save tokens |

### ❌ WHAT'S MISSING

| Feature | Status | Impact |
|---------|--------|--------|
| Claude adapter | ❌ Missing | Cannot use Anthropic API (different endpoint, headers, request/response format) |
| Provider detection | ❌ Missing | No way to auto-detect provider from base_url or config |
| Error differentiation | ❌ Missing | All errors caught generically — no retry on 429, no "invalid key" message on 401 |
| Retry with backoff | ❌ Missing | Single attempt only — transient failures lose the analysis |
| Connection pooling | ❌ Missing | Creates new `httpx.AsyncClient` PER CALL (line 229) — wastes TCP connections |
| Multi-model cost tracking | ❌ Missing | Hardcodes gpt-4o-mini pricing ($0.15/$0.60 per 1M) — wrong for DeepSeek/Gemini/Claude |
| Provider-specific headers | ❌ Missing | Always sends `Authorization: Bearer` — wrong for Claude (`x-api-key`) and Ollama (none needed) |
| `response_format` compat | ⚠️ Partial | Sends `response_format: {"type": "json_object"}` unconditionally — Claude doesn't support it |
| Fallback chain | ❌ Missing | Research recommends primary→fallback provider; not implemented |
| API key validation | ❌ Missing | No way to test if key is valid before starting the bot |

### ⚠️ WHAT'S BROKEN (would fail with non-OpenAI providers)

1. **Claude would 400-error**: Sends `Authorization: Bearer` (should be `x-api-key`), puts system in messages array (should be top-level `system` field), sends `response_format` (unsupported), posts to `/chat/completions` (should be `/messages`)
2. **Claude response parsing would fail**: Expects `choices[0].message.content` but Claude returns `content[0].text`
3. **Ollama sends unnecessary auth**: `Authorization: Bearer ""` header sent even when key is empty
4. **New httpx client per call**: Line 229 `async with httpx.AsyncClient(timeout=self.timeout) as client:` — creates/destroys TCP connection pool on every analysis call. Should use a shared client.

---

## System Prompt Evaluation

```python
SYSTEM_PROMPT = """Jesteś ekspertem od udziałów w nieruchomościach w Polsce..."""
```

**Rating: 9/10 — Excellent for the use case.**

Strengths:
- Written entirely in Polish (matches output language requirement)
- Clearly defines what IS vs ISN'T a real property share
- Provides concrete 1-5 star rating criteria
- Specifies exact JSON output schema
- Mentions key motivations: syndyk, spadek, rozwód, egzekucja

Minor improvements possible:
- Could add instruction about handling incomplete/ambiguous listings
- Could specify max response length (currently relies on `max_tokens: 500`)
- For Claude (no `response_format`), needs stronger "respond ONLY with JSON" instruction

---

## Correct Multi-Provider Architecture Design

Based on the research, here's the design for the rewrite:

### Architecture: Provider Adapter Pattern

```python
"""
Multi-provider LLM client for udzialy-bot.

Supports:
- OpenAI (GPT-4o, GPT-4o-mini) 
- DeepSeek (v4-flash, v4-pro)
- Gemini (3.7-flash, 3.5-flash-lite)
- Ollama (local, any model)
- LM Studio (local, any model)
- Anthropic Claude (haiku-4-5, sonnet-5) ← custom adapter

Pattern: Base OpenAI-compat handler + Claude adapter override
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    finish_reason: str

class BaseProvider(ABC):
    @abstractmethod
    def get_url(self) -> str: ...
    
    @abstractmethod
    def get_headers(self, api_key: str) -> dict: ...
    
    @abstractmethod
    def build_payload(self, messages: list, model: str, **kwargs) -> dict: ...
    
    @abstractmethod
    def parse_response(self, data: dict) -> LLMResponse: ...

class OpenAICompatProvider(BaseProvider):
    """Handles: OpenAI, DeepSeek, Gemini, Ollama, LM Studio"""
    
    def __init__(self, base_url: str):
        self._base_url = base_url
    
    def get_url(self) -> str:
        return f"{self._base_url}/chat/completions"
    
    def get_headers(self, api_key: str) -> dict:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h
    
    def build_payload(self, messages: list, model: str, **kwargs) -> dict:
        body = {"model": model, "messages": messages}
        if kwargs.get("json_mode"):
            body["response_format"] = {"type": "json_object"}
        if kwargs.get("temperature") is not None:
            body["temperature"] = kwargs["temperature"]
        if kwargs.get("max_tokens"):
            body["max_tokens"] = kwargs["max_tokens"]
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
    """Custom adapter for Claude's Messages API"""
    
    BASE_URL = "https://api.anthropic.com/v1"
    
    def get_url(self) -> str:
        return f"{self.BASE_URL}/messages"
    
    def get_headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    
    def build_payload(self, messages: list, model: str, **kwargs) -> dict:
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
        
        body = {
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
            if block["type"] == "text":
                content += block["text"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", ""),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            finish_reason=data.get("stop_reason", "end_turn"),
        )

# Provider registry
PROVIDERS = {
    "openai": OpenAICompatProvider("https://api.openai.com/v1"),
    "deepseek": OpenAICompatProvider("https://api.deepseek.com"),
    "gemini": OpenAICompatProvider("https://generativelanguage.googleapis.com/v1beta/openai"),
    "ollama": OpenAICompatProvider("http://localhost:11434/v1"),
    "lmstudio": OpenAICompatProvider("http://localhost:1234/v1"),
    "anthropic": AnthropicProvider(),
}

# Cost per 1M tokens (input, output)
COST_PER_MILLION = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "deepseek-v4-flash": (0.22, 0.66),
    "deepseek-v4-pro": (0.66, 1.98),
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
}
```

### Error Handling Design

```python
import asyncio
import httpx

class LLMError(Exception):
    """Base LLM error"""
    pass

class RateLimitError(LLMError):
    """429 — back off and retry"""
    def __init__(self, retry_after: float = 60.0):
        self.retry_after = retry_after

class AuthError(LLMError):
    """401/403 — invalid API key, don't retry"""
    pass

class ProviderError(LLMError):
    """5xx — provider issue, retry with backoff"""
    pass

async def call_with_retry(
    client: httpx.AsyncClient,
    provider: BaseProvider,
    api_key: str,
    messages: list,
    model: str,
    max_retries: int = 3,
    **kwargs,
) -> LLMResponse:
    """Call LLM with exponential backoff retry."""
    
    for attempt in range(max_retries):
        try:
            response = await client.post(
                provider.get_url(),
                headers=provider.get_headers(api_key),
                json=provider.build_payload(messages, model, **kwargs),
            )
            
            if response.status_code == 429:
                retry_after = float(response.headers.get("retry-after", 2 ** attempt))
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_after)
                    continue
                raise RateLimitError(retry_after)
            
            if response.status_code in (401, 403):
                raise AuthError(f"Invalid API key for {model}")
            
            if response.status_code >= 500:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ProviderError(f"Provider returned {response.status_code}")
            
            response.raise_for_status()
            return provider.parse_response(response.json())
            
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                continue
            raise LLMError(f"Timeout after {max_retries} attempts")
        
        except httpx.ConnectError:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            raise LLMError("Cannot connect to LLM provider")
    
    raise LLMError("Max retries exceeded")
```

### Key Changes from Current Code

| Current | Proposed | Reason |
|---------|----------|--------|
| `httpx.AsyncClient` per call | Shared client (class attribute) | Connection pooling |
| Single `Authorization: Bearer` | Provider-specific headers | Claude needs `x-api-key` |
| Always `/chat/completions` | Provider determines URL | Claude uses `/messages` |
| Always `response_format` | Only for OpenAI-compat | Claude doesn't support it |
| Generic exception catch | Typed errors (429/401/5xx) | Retry vs fail-fast logic |
| No retry | Exponential backoff (3 retries) | Transient failures recovered |
| Hardcoded cost ($0.15/$0.60) | Per-model cost table | Accurate tracking |
| `system` in messages array | Provider builds payload | Claude needs top-level `system` |
| 15s timeout | 60s timeout (configurable) | Slow models need more time |

### Config YAML Design

```yaml
llm:
  enabled: true
  provider: deepseek          # openai | deepseek | gemini | ollama | lmstudio | anthropic
  api_key: "sk-..."
  model: deepseek-v4-flash
  max_concurrent: 5
  timeout: 60
  max_retries: 3
  # Optional fallback
  fallback:
    provider: gemini
    api_key: "AIza..."
    model: gemini-3.5-flash-lite
```

### Provider Auto-Detection (bonus)

```python
def detect_provider(base_url: str) -> str:
    """Auto-detect provider from base_url for backward compatibility."""
    url = base_url.lower()
    if "openai.com" in url:
        return "openai"
    if "deepseek.com" in url:
        return "deepseek"
    if "generativelanguage.googleapis" in url:
        return "gemini"
    if "anthropic.com" in url:
        return "anthropic"
    if "localhost:11434" in url or "127.0.0.1:11434" in url:
        return "ollama"
    if "localhost:1234" in url or "127.0.0.1:1234" in url:
        return "lmstudio"
    # Default to openai-compat for custom endpoints
    return "openai"
```

---

## Implementation Priority

1. **P0 — Connection pooling fix** (5 min): Move `httpx.AsyncClient` to `__init__` as shared instance
2. **P0 — Provider adapter layer** (30 min): Add `BaseProvider`, `OpenAICompatProvider`, `AnthropicProvider`
3. **P1 — Error handling** (20 min): Typed errors + retry with backoff
4. **P1 — Multi-model cost table** (10 min): Replace hardcoded pricing
5. **P2 — Config update** (10 min): Add `provider` field, `fallback` section
6. **P2 — Provider auto-detection** (5 min): For backward compat with existing `base_url` configs
7. **P3 — Fallback chain** (15 min): Try primary → if error/timeout → try fallback provider
8. **P3 — API key validation** (10 min): Test key with lightweight request on startup

**Total estimated effort: ~2 hours for full rewrite with all features.**

---

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `detector/llm_analyzer.py` | **Rewrite** | Add provider adapters, error handling, shared client |
| `config.yaml` | **Update** | Add `provider` field, `fallback` section |
| `detector/__init__.py` | Check | May need updated imports |
| `tests/test_llm_analyzer.py` | **Create** | Unit tests for all providers, error cases |

---

## Conclusion

The existing code is a **clean, working implementation for OpenAI-only** use. The rewrite should:
1. Keep the excellent `SYSTEM_PROMPT` and `AnalysisResult` dataclass unchanged
2. Keep the `_build_user_message` logic unchanged  
3. Replace the `_call_llm` internals with the provider adapter pattern
4. Add proper error handling and retry logic
5. Add shared httpx client with connection pooling
6. Support all 6 providers via config

The `SYSTEM_PROMPT` is the best part — it's production-quality for Polish real estate share analysis.
