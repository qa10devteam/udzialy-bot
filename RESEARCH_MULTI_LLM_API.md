# Multi-LLM API Compatibility Research

> Research date: August 2026  
> Purpose: Determine optimal architecture for Python async httpx-based multi-provider LLM client  
> Use case: Telegram bot analyzing real estate listings with structured output

---

## TL;DR — Architecture Decision

**YES, we can use ONE httpx client with a provider adapter pattern.**

- **4 out of 6 providers** are 100% OpenAI-compatible (same endpoint format, same request/response schema)
- **Only Anthropic Claude** requires a truly different adapter (different endpoint, headers, request body, response format)
- **Recommended approach**: Raw `httpx.AsyncClient` + thin adapter layer (~200 lines total). NO litellm needed.

### Provider Compatibility Matrix

| Provider | OpenAI-Compatible? | Adapter Needed? |
|----------|-------------------|-----------------|
| OpenAI | ✅ Native | Base adapter |
| DeepSeek | ✅ 100% compatible | Just change base_url |
| Gemini | ✅ OpenAI compat endpoint | Just change base_url + key format |
| Ollama | ✅ OpenAI compat endpoint | Just change base_url |
| LM Studio | ✅ OpenAI compat endpoint | Just change base_url |
| **Anthropic Claude** | ❌ Different API | **Full adapter needed** |

---

## 1. OpenAI (GPT-4o, GPT-4o-mini)

### Endpoint
```
POST https://api.openai.com/v1/chat/completions
```

### Auth
```
Authorization: Bearer sk-...
```

### Request Format
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0.7,
  "response_format": {"type": "json_object"}
}
```

### Response Format
```json
{
  "id": "chatcmpl-...",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "..."},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150}
}
```

### Structured Output
- `response_format: {"type": "json_object"}` — basic JSON mode
- `response_format: {"type": "json_schema", "json_schema": {...}}` — strict schema enforcement
- Function calling with `tools` array

### Streaming
- SSE format: `data: {"choices": [{"delta": {"content": "..."}}]}\n\n`
- Final: `data: [DONE]\n\n`

### Rate Limits (Tier 1)
- GPT-4o-mini: 500 RPM, 200,000 TPM
- GPT-4o: 500 RPM, 30,000 TPM

### Cost (per 1M tokens)
- GPT-4o-mini: $0.15 input / $0.60 output
- GPT-4o: $2.50 input / $10.00 output

### Latency
- GPT-4o-mini: ~1-2s for 500 tokens
- GPT-4o: ~2-4s for 500 tokens

---

## 2. DeepSeek (deepseek-v4-flash, deepseek-v4-pro)

### ⚡ KEY FINDING: 100% OpenAI-Compatible

From official docs: *"The DeepSeek API uses an API format compatible with OpenAI/Anthropic. By modifying the configuration, you can use the OpenAI SDK or softwares compatible with the OpenAI API to access the DeepSeek API."*

### Endpoint
```
POST https://api.deepseek.com/chat/completions
```
(Also works as: `https://api.deepseek.com/v1/chat/completions`)

### Auth
```
Authorization: Bearer sk-...
```
**IDENTICAL to OpenAI** — uses Bearer token with their own API key.

### Request Format — IDENTICAL to OpenAI
```json
{
  "model": "deepseek-v4-flash",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "Hello"}
  ],
  "stream": false
}
```

### Response Format — IDENTICAL to OpenAI
```json
{
  "choices": [{
    "message": {"role": "assistant", "content": "..."},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...}
}
```

### Structured Output
- ✅ JSON mode supported (`response_format: {"type": "json_object"}`)
- ✅ Tool/Function calling supported (OpenAI format)

### Streaming
- ✅ SSE format — identical to OpenAI

### Rate Limits
- deepseek-v4-flash: 2500 concurrent connections
- deepseek-v4-pro: 500 concurrent connections
- **Note**: DeepSeek uses concurrency-based limits, not RPM/TPM

### Cost (per 1M tokens — OFF-PEAK prices)
- **deepseek-v4-flash**: $0.22 input (cache miss) / $0.66 output ← CHEAPEST
- **deepseek-v4-pro**: $0.66 input / $1.98 output
- Cache hit: $0.007 input (flash), $0.022 input (pro) — incredibly cheap!
- Peak hours (01:00-04:00, 06:00-10:00 UTC): 2x prices

### Latency
- deepseek-v4-flash: ~1-3s for 500 tokens
- deepseek-v4-pro: ~3-6s for 500 tokens (thinking mode)

### Implementation
```python
# LITERALLY just change base_url — no other code changes needed
async with httpx.AsyncClient(base_url="https://api.deepseek.com") as client:
    response = await client.post("/chat/completions", 
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": "deepseek-v4-flash", "messages": messages}
    )
```

---

## 3. Google Gemini (gemini-3.7-flash, gemini-3.5-flash-lite)

### ⚡ KEY FINDING: Has Official OpenAI-Compatible Endpoint!

From official docs: *"Gemini models are accessible using the OpenAI libraries (Python and TypeScript/Javascript) along with the REST API, by updating three lines of code and using your Gemini API key."*

### Endpoint (OpenAI-compatible)
```
POST https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
```

### Auth
```
Authorization: Bearer GEMINI_API_KEY
```
**Uses Bearer token** — same header format as OpenAI, just with Gemini API key.

### Request Format — OpenAI-Compatible
```json
{
  "model": "gemini-3.7-flash",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain AI"}
  ]
}
```

### Response Format — OpenAI-Compatible
```json
{
  "choices": [{
    "message": {"role": "assistant", "content": "..."},
    "finish_reason": "stop"
  }]
}
```

### Structured Output
- ✅ `response_format` with JSON schema — supported via OpenAI compat!
- ✅ Function calling with `tools` array — fully supported
- ✅ `client.beta.chat.completions.parse()` with Pydantic models works

### Streaming
- ✅ SSE format — identical to OpenAI

### Rate Limits (Free tier → Paid Tier 1)
- Free: 15 RPM, 1M TPM (generous free tier!)
- Paid Tier 1: ~1000 RPM (varies by model)
- Spend-based limits: $10/10min (Tier 1), $50/10min (Tier 2)

### Cost (per 1M tokens — Paid tier)
- **gemini-3.5-flash-lite**: $0.30 input / $2.50 output ← cheapest Gemini
- **gemini-3.7-flash**: $0.75 input / $3.75 output (through Dec 2026, then doubles)
- **Free tier available** with lower rate limits!

### Latency
- gemini-3.7-flash: ~1-2s for 500 tokens
- gemini-3.5-flash-lite: ~0.5-1.5s for 500 tokens (fastest)

### Implementation
```python
# Same code as OpenAI — just different base_url
async with httpx.AsyncClient(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai"
) as client:
    response = await client.post("/chat/completions",
        headers={"Authorization": f"Bearer {gemini_key}"},
        json={"model": "gemini-3.7-flash", "messages": messages}
    )
```

---

## 4. Anthropic Claude (claude-sonnet-5, claude-haiku-4-5)

### ⚠️ DIFFERENT API — Requires Custom Adapter

Claude's Messages API is **NOT** OpenAI-compatible. Key differences:

### Endpoint
```
POST https://api.anthropic.com/v1/messages
```

### Auth — DIFFERENT!
```
x-api-key: sk-ant-...
anthropic-version: 2023-06-01
```
**Uses `x-api-key` header** (NOT `Authorization: Bearer`), plus requires `anthropic-version` header.

### Request Format — DIFFERENT!
```json
{
  "model": "claude-sonnet-5",
  "max_tokens": 1024,
  "system": "You are a helpful assistant.",
  "messages": [
    {"role": "user", "content": "Hello"}
  ]
}
```

**Key differences from OpenAI:**
1. `system` is a **top-level field**, NOT in the messages array
2. `max_tokens` is **REQUIRED** (OpenAI defaults it)
3. No `response_format` parameter for JSON mode
4. Different structured output mechanism

### Response Format — DIFFERENT!
```json
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "content": [
    {"type": "text", "text": "Hello! How can I help?"}
  ],
  "model": "claude-sonnet-5",
  "stop_reason": "end_turn",
  "usage": {"input_tokens": 25, "output_tokens": 50}
}
```

**Key differences from OpenAI:**
1. Response is `content[0].text` (NOT `choices[0].message.content`)
2. `content` is an **array of content blocks** (can have multiple text/tool_use blocks)
3. `stop_reason` instead of `finish_reason`
4. No `choices` array wrapper
5. `usage` uses `input_tokens`/`output_tokens` (not `prompt_tokens`/`completion_tokens`)

### Structured Output
- ❌ No `response_format` parameter
- ✅ Tool use (function calling) — similar concept but different format:
```json
{
  "tools": [{
    "name": "analyze_listing",
    "description": "...",
    "input_schema": {"type": "object", "properties": {...}}
  }]
}
```
- For JSON output: Use system prompt instruction + tool_use to force structured response

### Streaming — DIFFERENT!
- Uses SSE but with **different event types**:
```
event: message_start
data: {"type": "message_start", "message": {...}}

event: content_block_start  
data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}

event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}

event: message_stop
data: {"type": "message_stop"}
```

### Rate Limits (Build tier — Tier 1)
- All models: 1,000 RPM
- Claude Sonnet 5: 2,000,000 input TPM, 400,000 output TPM
- Claude Haiku 4.5: similar limits

### Cost (per 1M tokens)
- **Claude Haiku 4.5**: $1.00 input / $5.00 output
- **Claude Sonnet 5**: $2.00 input / $10.00 output
- **Claude Opus 5**: $5.00 input / $25.00 output

### Latency
- Claude Haiku 4.5: ~1-2s for 500 tokens (fastest Claude)
- Claude Sonnet 5: ~2-4s for 500 tokens

### Adapter Implementation Required
```python
class ClaudeAdapter:
    BASE_URL = "https://api.anthropic.com/v1"
    
    def build_headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    
    def build_request(self, messages: list, model: str, **kwargs) -> dict:
        # Extract system message from messages array
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
        
        return {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "system": system,
            "messages": user_messages
        }
    
    def parse_response(self, data: dict) -> str:
        # Convert Claude response to unified format
        return data["content"][0]["text"]
```

---

## 5. Ollama (Local)

### Endpoint
```
POST http://localhost:11434/v1/chat/completions
```

### Auth
- **None required** — local service, no auth needed

### Format
- 100% OpenAI-compatible (messages array, choices response)
- Supports `response_format: {"type": "json_object"}`

### Implementation
```python
# No auth needed, same format as OpenAI
async with httpx.AsyncClient(base_url="http://localhost:11434/v1") as client:
    response = await client.post("/chat/completions",
        json={"model": "llama3.1", "messages": messages}
    )
```

---

## 6. LM Studio (Local)

### Endpoint
```
POST http://localhost:1234/v1/chat/completions
```

### Auth
- **None required** (or dummy key accepted)

### Format
- 100% OpenAI-compatible

---

## Library Comparison: litellm vs raw httpx

### litellm
- **Pros**: Supports 100+ providers, handles all format translation
- **Cons**: 
  - Adds ~15 direct dependencies (fastuuid, pydantic-settings, importlib-metadata, etc.)
  - Total transitive deps: 30-40+
  - Package is large (~40MB wheel as of v1.97.0)
  - Overkill for 6 providers
  - Abstracts away control over retry logic, timeouts, connection pooling

### openai SDK with base_url
- **Pros**: Official, well-maintained, handles OpenAI-compat providers
- **Cons**: 
  - Sync by default (AsyncOpenAI exists but adds complexity)
  - Still need separate handling for Anthropic
  - Adds ~10 deps (httpx, pydantic, etc.)
  - Less control over connection pooling

### Raw httpx (RECOMMENDED ✅)
- **Pros**:
  - Already a dependency of most async Python projects
  - Full control over connection pooling, timeouts, retries
  - Minimal footprint (~3 deps: httpcore, certifi, anyio)
  - Easy to implement adapter pattern
  - Perfect for 5 OpenAI-compat + 1 Claude adapter
- **Cons**:
  - Must implement SSE parsing manually (trivial ~30 lines)
  - Must handle retries manually (desirable for fine control)

---

## Recommended Architecture: Provider Adapter Pattern

```python
import httpx
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class LLMResponse:
    """Unified response format"""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str

class BaseProvider(ABC):
    @abstractmethod
    def get_base_url(self) -> str: ...
    
    @abstractmethod
    def get_headers(self, api_key: str) -> dict: ...
    
    @abstractmethod
    def build_request(self, messages: list, model: str, **kwargs) -> dict: ...
    
    @abstractmethod
    def parse_response(self, data: dict) -> LLMResponse: ...

class OpenAICompatProvider(BaseProvider):
    """Works for: OpenAI, DeepSeek, Gemini, Ollama, LM Studio"""
    
    def __init__(self, base_url: str):
        self._base_url = base_url
    
    def get_base_url(self) -> str:
        return self._base_url
    
    def get_headers(self, api_key: str) -> dict:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers
    
    def build_request(self, messages: list, model: str, **kwargs) -> dict:
        body = {"model": model, "messages": messages}
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
            finish_reason=choice.get("finish_reason", "stop")
        )

class AnthropicProvider(BaseProvider):
    """Custom adapter for Claude's Messages API"""
    
    def get_base_url(self) -> str:
        return "https://api.anthropic.com/v1"
    
    def get_headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    
    def build_request(self, messages: list, model: str, **kwargs) -> dict:
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
        
        body = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": user_messages
        }
        if system:
            body["system"] = system
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
            finish_reason=data.get("stop_reason", "end_turn")
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

# Unified client
class LLMClient:
    def __init__(self):
        self._http = httpx.AsyncClient(timeout=60.0)
    
    async def complete(self, provider_name: str, api_key: str, 
                       model: str, messages: list, **kwargs) -> LLMResponse:
        provider = PROVIDERS[provider_name]
        
        endpoint = "/messages" if provider_name == "anthropic" else "/chat/completions"
        url = f"{provider.get_base_url()}{endpoint}"
        
        response = await self._http.post(
            url,
            headers=provider.get_headers(api_key),
            json=provider.build_request(messages, model, **kwargs)
        )
        response.raise_for_status()
        return provider.parse_response(response.json())
    
    async def close(self):
        await self._http.aclose()
```

---

## Cost Comparison Summary (per 1M tokens, cheapest model per provider)

| Provider | Model | Input | Output | Total for 500-token analysis* |
|----------|-------|-------|--------|-------------------------------|
| DeepSeek | v4-flash (off-peak) | $0.22 | $0.66 | ~$0.0004 |
| Gemini | 3.5-flash-lite | $0.30 | $2.50 | ~$0.0014 |
| OpenAI | GPT-4o-mini | $0.15 | $0.60 | ~$0.0004 |
| Anthropic | Haiku 4.5 | $1.00 | $5.00 | ~$0.003 |
| Gemini | 3.7-flash | $0.75 | $3.75 | ~$0.002 |
| DeepSeek | v4-pro | $0.66 | $1.98 | ~$0.001 |
| Anthropic | Sonnet 5 | $2.00 | $10.00 | ~$0.006 |

*Assuming ~500 input tokens (listing data) + ~500 output tokens (analysis)

---

## Streaming SSE Parsing (for future use)

```python
async def stream_response(response: httpx.Response) -> AsyncIterator[str]:
    """Parse SSE stream from OpenAI-compatible endpoints"""
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            delta = chunk["choices"][0].get("delta", {})
            if content := delta.get("content"):
                yield content
```

---

## Key Decisions & Recommendations

1. **Use raw httpx** — minimal deps, full async control, ~200 lines of adapter code
2. **Skip litellm** — too heavy for 6 providers, we only need the adapter pattern above
3. **Don't use openai SDK** — adds unnecessary deps when we already need httpx for Claude
4. **For structured output**: Use `response_format: {"type": "json_object"}` for OpenAI-compat providers, use system prompt + explicit JSON instruction for Claude
5. **Start with non-streaming** — simpler, sufficient for Telegram bot (user waits for full analysis)
6. **Default model recommendation**: DeepSeek v4-flash or GPT-4o-mini (cheapest + fast)

---

## Gemini Models Available (as of Aug 2026)

| Model ID | Notes |
|----------|-------|
| gemini-3.7-flash | Best Flash model, agentic workflows |
| gemini-3.5-flash-lite | Most cost-efficient, high-volume |
| gemini-3.1-flash-lite | Previous gen cost-efficient |
| gemini-3.1-pro-preview | Most capable (preview) |

---

## DeepSeek Models Available (as of Aug 2026)

| Model ID | Notes |
|----------|-------|
| deepseek-v4-flash | Default, fast, cheap (updated to V4-Flash-0731) |
| deepseek-v4-pro | Best quality, thinking mode (updated to V4-Pro-0813) |
| deepseek-v4-flash-vision-exp | Experimental, accepts images |

---

## Claude Models Available (as of Aug 2026)

| Model ID | Notes |
|----------|-------|
| claude-haiku-4-5 | Fastest, cheapest Claude |
| claude-sonnet-5 | Best speed/intelligence balance |
| claude-opus-5 | Complex agentic work |
| claude-fable-5 | Most capable (newest, expensive) |

---

## Implementation Notes for Telegram Bot

1. **Connection pooling**: Use single `httpx.AsyncClient` instance shared across requests
2. **Timeout handling**: Set 60s timeout (some models are slow with long context)
3. **Retry logic**: Implement exponential backoff for 429 (rate limit) and 5xx errors
4. **Error mapping**: Convert provider-specific errors to unified error types
5. **API key validation**: Test key with a simple request before saving
6. **Token estimation**: Use ~4 chars per token heuristic for cost estimates before sending
