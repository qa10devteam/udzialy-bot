"""
AI Conversational Engine — the brain of the bot.

Architecture:
- Maintains conversation context per user (last N messages)
- Uses function calling to trigger bot actions (search, filters, save)
- Responds naturally in Polish
- Understands intent: "szukaj w Gdyni" → sets city filter + runs search
- Proactive: suggests actions based on context

Provider support: Claude (primary), OpenAI, DeepSeek, Gemini
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.config import get_settings

logger = logging.getLogger(__name__)

router = Router(name="ai_chat")

# ---------------------------------------------------------------------------
# Conversation memory (per-user, last 10 messages)
# ---------------------------------------------------------------------------

_conversations: Dict[int, List[Dict[str, str]]] = {}
MAX_HISTORY = 10
MAX_USERS = 100  # Evict oldest when exceeded


def _get_history(user_id: int) -> List[Dict[str, str]]:
    """Get conversation history for user."""
    return _conversations.get(user_id, [])


def _add_message(user_id: int, role: str, content: str) -> None:
    """Add message to conversation history."""
    if user_id not in _conversations:
        # Evict oldest user if at capacity
        if len(_conversations) >= MAX_USERS:
            oldest_key = next(iter(_conversations))
            del _conversations[oldest_key]
        _conversations[user_id] = []
    _conversations[user_id].append({"role": role, "content": content})
    # Trim to last N
    if len(_conversations[user_id]) > MAX_HISTORY:
        _conversations[user_id] = _conversations[user_id][-MAX_HISTORY:]


# ---------------------------------------------------------------------------
# System prompt with tool descriptions
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Jesteś "Udziały Bot" — inteligentnym asystentem do wyszukiwania udziałów w nieruchomościach w Polsce.

KONTEKST: Użytkownik szuka ogłoszeń sprzedaży udziałów (ułamkowych części własności) w nieruchomościach. Przeszukujesz 8 portali: OLX, Otodom, Morizon, Domiporta, Gratka, Allegro, Nieruchomości-online, Szybko.

TWOJE MOŻLIWOŚCI (tools):
1. search_listings — skanuj portale z aktualnymi filtrami
2. set_filters — ustaw filtry (miasto, województwo, cena min/max, promień km)
3. get_saved — pokaż zapisane ogłoszenia
4. clear_filters — wyczyść filtry

JAK ODPOWIADAĆ:
- Krótko, konkretnie, po polsku
- Gdy user chce szukać → wywołaj odpowiedni tool
- Gdy user podaje lokalizację/cenę → set_filters + search
- Gdy user pyta ogólnie o udziały → odpowiedz merytorycznie (spadki, licytacje, współwłasność, ryzyka)
- Gdy user pisze "co nowego?" → search z aktualnymi filtrami
- Proaktywnie podpowiadaj: "Mogę zawęzić do Gdyni — podaj max cenę?"

ZASADY:
- NIE odpowiadaj "użyj komendy /search" — sam to zrób
- NIE bądź formalny — bądź pomocny i bezpośredni
- Gdy nie rozumiesz — dopytaj krótko
- Gdy wyniki puste — zaproponuj rozszerzenie filtrów

Aktualne filtry użytkownika: {filters_info}
"""

TOOLS_SCHEMA = [
    {
        "name": "search_listings",
        "description": "Przeszukaj portale nieruchomości z aktualnymi filtrami. Użyj gdy user chce szukać ogłoszeń.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "set_filters",
        "description": "Ustaw filtry wyszukiwania. Użyj gdy user podaje miasto, cenę, województwo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Miasto (np. Gdynia, Warszawa)"},
                "voivodeship": {"type": "string", "description": "Województwo (np. pomorskie, mazowieckie)"},
                "price_min": {"type": "number", "description": "Cena minimalna PLN"},
                "price_max": {"type": "number", "description": "Cena maksymalna PLN"},
                "radius_km": {"type": "number", "description": "Promień szukania od miasta w km"},
            },
        },
    },
    {
        "name": "get_saved",
        "description": "Pokaż zapisane ogłoszenia użytkownika.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "clear_filters",
        "description": "Wyczyść wszystkie filtry — szukaj w całej Polsce.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ---------------------------------------------------------------------------
# LLM call with tool use
# ---------------------------------------------------------------------------

@dataclass
class AIResponse:
    """Response from AI engine."""
    text: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


async def call_ai(
    user_message: str,
    history: List[Dict[str, str]],
    filters_info: str,
    provider: str,
    api_key: str,
) -> AIResponse:
    """Call LLM with conversation history and tools."""
    if not api_key:
        return AIResponse(error="no_api_key")

    system = SYSTEM_PROMPT.format(filters_info=filters_info or "brak (szukam wszędzie)")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if provider == "claude":
                return await _call_claude(client, system, history, user_message, api_key)
            elif provider in ("openai", "deepseek"):
                return await _call_openai(client, system, history, user_message, api_key, provider)
            else:
                # Fallback: simple completion without tools
                return await _call_simple(client, system, history, user_message, api_key, provider)
    except Exception as e:
        logger.error(f"AI call failed: {e}")
        return AIResponse(error=str(e))


async def _call_claude(
    client: httpx.AsyncClient,
    system: str,
    history: List[Dict[str, str]],
    user_message: str,
    api_key: str,
) -> AIResponse:
    """Call Claude with tool use."""
    messages = [*history, {"role": "user", "content": user_message}]

    response = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": llm_config.get("model", "claude-haiku-4-5-20251001") if isinstance(llm_config, dict) else getattr(llm_config, "model", "claude-haiku-4-5-20251001"),
            "max_tokens": 1024,
            "system": system,
            "messages": messages,
            "tools": TOOLS_SCHEMA,
        },
    )

    if response.status_code != 200:
        logger.warning(f"Gemini API error {response.status_code}")
        return AIResponse(error=f"API error {response.status_code}")

    data = response.json()
    result = AIResponse()

    for block in data.get("content", []):
        if block["type"] == "text":
            result.text = block["text"]
        elif block["type"] == "tool_use":
            result.tool_calls.append({
                "name": block["name"],
                "input": block.get("input", {}),
            })

    return result


async def _call_openai(
    client: httpx.AsyncClient,
    system: str,
    history: List[Dict[str, str]],
    user_message: str,
    api_key: str,
    provider: str,
) -> AIResponse:
    """Call OpenAI/DeepSeek with function calling."""
    base_url = "https://api.deepseek.com/v1" if provider == "deepseek" else "https://api.openai.com/v1"
    model = "deepseek-chat" if provider == "deepseek" else "gpt-4o-mini"

    # Convert tools to OpenAI format
    functions = [
        {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        }
        for t in TOOLS_SCHEMA
    ]

    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": user_message},
    ]

    response = await client.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "max_tokens": 1024,
            "messages": messages,
            "functions": functions,
            "function_call": "auto",
        },
    )

    if response.status_code != 200:
        return AIResponse(error=f"API error {response.status_code}")

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        return AIResponse(error="Empty response from API")
    choice = choices[0].get("message", {})
    result = AIResponse(text=choice.get("content"))

    if fc := choice.get("function_call"):
        try:
            args = json.loads(fc.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}
        result.tool_calls.append({"name": fc["name"], "input": args})

    return result


async def _call_simple(
    client: httpx.AsyncClient,
    system: str,
    history: List[Dict[str, str]],
    user_message: str,
    api_key: str,
    provider: str,
) -> AIResponse:
    """Simple text completion without tools (Gemini, Ollama)."""
    # Build prompt with tool hints in text
    tool_hint = (
        "\n\nJeśli user chce szukać, odpowiedz: [ACTION:search]\n"
        "Jeśli user podaje miasto/cenę, odpowiedz: [ACTION:filters miasto=X cena_max=Y]\n"
        "W innym przypadku odpowiedz normalnie.\n"
    )
    full_prompt = system + tool_hint + "\n\nUser: " + user_message

    if provider == "gemini":
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": full_prompt}]}], "generationConfig": {"maxOutputTokens": 1024}},
        )
        if response.status_code == 200:
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_action_text(text)
        return AIResponse(error=f"Gemini error {response.status_code}")

    return AIResponse(text="Nie skonfigurowano providera AI. Użyj /search.")


def _parse_action_text(text: str) -> AIResponse:
    """Parse [ACTION:...] markers from simple providers."""
    result = AIResponse()
    if "[ACTION:search]" in text:
        result.tool_calls.append({"name": "search_listings", "input": {}})
        result.text = text.replace("[ACTION:search]", "").strip()
    elif "[ACTION:filters" in text:
        # Parse filters from text
        import re
        m = re.search(r"\[ACTION:filters\s+(.*?)\]", text)
        if m:
            parts = m.group(1).split()
            filters = {}
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                    filters[k.replace("miasto", "city").replace("cena_max", "price_max")] = v
            result.tool_calls.append({"name": "set_filters", "input": filters})
            result.text = text[:text.find("[ACTION:")].strip()
    else:
        result.text = text
    return result


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def execute_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    message: Message,
    state: FSMContext,
) -> str:
    """Execute a tool call and return result description."""
    if tool_name == "search_listings":
        # Trigger search
        from bot.routers.search import cmd_search
        await cmd_search(message, state)
        return "Uruchomiłem wyszukiwanie."

    elif tool_name == "set_filters":
        # Set filters in FSM state
        data = await state.get_data()
        if city := tool_input.get("city"):
            data["filter_city"] = city
        if voiv := tool_input.get("voivodeship"):
            data["filter_voivodeship"] = voiv
        if price_min := tool_input.get("price_min"):
            try:
                data["filter_price_min"] = int(float(str(price_min).replace(" ", "").replace("k", "000")))
            except (ValueError, TypeError):
                pass
        if price_max := tool_input.get("price_max"):
            try:
                data["filter_price_max"] = int(float(str(price_max).replace(" ", "").replace("k", "000")))
            except (ValueError, TypeError):
                pass
        if radius := tool_input.get("radius_km"):
            try:
                data["filter_radius"] = int(float(str(radius)))
            except (ValueError, TypeError):
                pass
        await state.update_data(**data)

        parts = []
        if city := tool_input.get("city"):
            parts.append(f"miasto: {city}")
        if voiv := tool_input.get("voivodeship"):
            parts.append(f"woj: {voiv}")
        if tool_input.get("price_max"):
            parts.append(f"max: {tool_input['price_max']} PLN")
        if tool_input.get("price_min"):
            parts.append(f"min: {tool_input['price_min']} PLN")

        return f"Ustawiono filtry: {', '.join(parts)}"

    elif tool_name == "get_saved":
        from bot.routers.saved import cmd_saved
        await cmd_saved(message, state)
        return "Pokazuję zapisane."

    elif tool_name == "clear_filters":
        await state.update_data(
            filter_city=None, filter_voivodeship=None,
            filter_price_min=None, filter_price_max=None, filter_radius=None,
        )
        return "Filtry wyczyszczone — szukam w całej Polsce."

    return ""


# ---------------------------------------------------------------------------
# Router handler
# ---------------------------------------------------------------------------

def _is_owner(user_id: int | None) -> bool:
    """Check if user is the bot owner."""
    settings = get_settings()
    if settings.owner_id == 0:
        return True
    return user_id == int(settings.owner_id)


def _format_filters(data: Dict[str, Any]) -> str:
    """Format current filters for system prompt."""
    parts = []
    if v := data.get("filter_voivodeship"):
        parts.append(f"woj. {v}")
    if c := data.get("filter_city"):
        parts.append(f"miasto: {c}")
    if r := data.get("filter_radius"):
        parts.append(f"promień: {r} km")
    if p := data.get("filter_price_min"):
        parts.append(f"cena od: {p} PLN")
    if p := data.get("filter_price_max"):
        parts.append(f"cena do: {p} PLN")
    return ", ".join(parts) if parts else "brak (szukam wszędzie)"


@router.message(F.text)
async def handle_ai_chat(message: Message, state: FSMContext) -> None:
    """Catch-all for text messages — AI-powered conversational handler."""
    if not message.from_user or not _is_owner(message.from_user.id):
        return

    if not message.text:
        return

    settings = get_settings()
    llm_config = settings.llm
    user_id = message.from_user.id

    if not llm_config.enabled or not llm_config.api_key:
        await message.answer(
            "💡 Podpowiedź:\n"
            "/search — szukaj udziałów\n"
            "/filters — ustaw filtry\n\n"
            "Aby rozmawiać z AI, uruchom `udzialy setup` i dodaj klucz API."
        )
        return

    # Get current filters and history
    fsm_data = await state.get_data()
    filters_info = _format_filters(fsm_data)
    history = _get_history(user_id)

    # Guard against re-entrancy (search → AI → search loop)
    fsm_data_check = await state.get_data()
    if fsm_data_check.get("_ai_processing"):
        return
    await state.update_data(_ai_processing=True)

    try:
        # Show typing
        try:
            await message.bot.send_chat_action(message.chat.id, "typing")  # type: ignore
        except Exception:
            pass

        # Call AI
        ai_response = await call_ai(
            user_message=message.text,
            history=history,
            filters_info=filters_info,
            provider=llm_config.provider,
            api_key=llm_config.api_key,
        )

        if ai_response.error:
            if ai_response.error == "no_api_key":
                await message.answer("⚠️ Brak klucza API. Uruchom `udzialy setup`.")
            else:
                await message.answer(f"⚠️ Błąd AI: {ai_response.error[:100]}")
            return

        # Save to history
        _add_message(user_id, "user", message.text)

        # Execute tool calls
        tool_executed = False
        for tool_call in ai_response.tool_calls:
            tool_result = await execute_tool(
                tool_call["name"], tool_call.get("input", {}), message, state
            )
            if tool_result:
                tool_executed = True
                # If AI also has text, send it before tool execution
                if ai_response.text and not tool_executed:
                    await message.answer(ai_response.text)

        # Send text response (if no tool was executed, or tool + text)
        if ai_response.text and not tool_executed:
            await message.answer(ai_response.text)
            _add_message(user_id, "assistant", ai_response.text)
        elif ai_response.text and tool_executed:
            # Tool ran + AI has commentary
            _add_message(user_id, "assistant", ai_response.text)
        elif not ai_response.text and not tool_executed:
            # No response at all — shouldn't happen
            await message.answer("🤔 Nie zrozumiałem. Spróbuj: \"szukaj udziałów w Gdyni do 200k\"")
    finally:
        await state.update_data(_ai_processing=False)
