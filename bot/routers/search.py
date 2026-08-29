"""
/start and /search — handle welcome, owner check, and search execution.

Flow:
  /start → welcome + main menu
  /search or 🔍 button → 'Szukam...' → ScraperManager.search_all() → results via pagination
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import get_settings, PROJECT_ROOT
from scraper.manager import ScraperManager
import json
from bot.keyboards.inline import build_search_progress_keyboard, build_results_keyboard
from bot.keyboards.reply import main_menu_keyboard


logger = logging.getLogger(__name__)

router = Router(name="search")


def _is_owner(user_id: int | None) -> bool:
    """Check if user is the bot owner."""
    settings = get_settings()
    # If owner_id is 0, allow anyone (not configured yet)
    if settings.owner_id == 0:
        return True
    return user_id == settings.owner_id


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command — conversational onboarding."""
    if not message.from_user or not _is_owner(message.from_user.id):
        await message.answer("⛔ Bot jest prywatny. Skontaktuj się z właścicielem.")
        return

    # Reset state on fresh start (clean orphan keys from previous flows)
    await state.clear()

    # Load persisted filters if any
    try:
        filters_file = PROJECT_ROOT / "filters.json"
        if filters_file.exists():
            import json as _json
            saved_filters = _json.loads(filters_file.read_text())
            if saved_filters:
                await state.update_data(**saved_filters)
    except Exception:
        pass

    settings = get_settings()
    has_ai = settings.llm.enabled and settings.llm.api_key

    if has_ai:
        await message.answer(
            "👋 <b>Cześć! Jestem Udziały Bot.</b>\n\n"
            f"Przeszukuję {len(ScraperManager.MAIN_PORTALS)} portali nieruchomości w poszukiwaniu "
            "ofert sprzedaży udziałów — spadkowych, z licytacji, "
            "od współwłaścicieli.\n\n"
            "Napisz mi po prostu czego szukasz, np.:\n"
            "• <i>\"Szukaj w Gdyni do 200 tysięcy\"</i>\n"
            "• <i>\"Co nowego w Trójmieście?\"</i>\n"
            "• <i>\"Pokaż najtańsze udziały\"</i>\n\n"
            "Mogę też odpowiedzieć na pytania o udziały, "
            "ryzyka zakupu, procedury prawne.\n\n"
            "Od czego zaczynamy? 🏠",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            "🏠 <b>Udziały Bot</b>\n\n"
            "Przeszukuję portale nieruchomości w poszukiwaniu "
            "ofert sprzedaży udziałów.\n\n"
            "Komendy:\n"
            "/search — szukaj udziałów\n"
            "/filters — ustaw miasto i cenę\n"
            "/saved — zapisane ogłoszenia\n"
            "/help — pomoc",
            reply_markup=main_menu_keyboard(),
        )


@router.message(Command("help"))
@router.message(F.text == "❓ Pomoc")
async def cmd_help(message: Message) -> None:
    """Handle /help command and ❓ button — show available commands."""
    if not message.from_user or not _is_owner(message.from_user.id):
        return

    await message.answer(
        "📋 <b>Dostępne komendy:</b>\n\n"
        "/search — Nowe wyszukiwanie udziałów\n"
        "/filters — Ustaw filtry (woj., miasto, cena)\n"
        "/saved — Zapisane ogłoszenia\n"
        "/help — Ta pomoc\n\n"
        "<b>Przyciski klawiatury:</b>\n"
        "🔍 Szukaj — to samo co /search\n"
        "⚙️ Filtry — to samo co /filters\n"
        "📋 Zapisane — to samo co /saved",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("search"))
@router.message(F.text == "🔍 Szukaj")
async def cmd_search(message: Message, state: FSMContext) -> None:
    """
    Handle /search command and 🔍 button — run the 3-stage pipeline.

    1. Send 'Szukam...' message
    2. run_search_pipeline(): scan portals → deep fetch → classify & rank
    3. Optional LLM analysis of the ranked shares
    4. Store ONE list (`search_results`) used by page 1, pagination, save and detail
    """
    if not message.from_user or not _is_owner(message.from_user.id):
        return
    await start_search(message, state)


async def start_search(message: Message, state: FSMContext) -> None:
    """Run a search in `message`'s chat. Caller has already checked ownership.

    Used by /search, the 🔍 button, the AI tool call and the "search with filters"
    inline button (whose `callback.message.from_user` is the bot, not the owner).
    """
    # Prevent concurrent searches
    data_pre: Dict[str, Any] = await state.get_data()
    if data_pre.get("_search_running"):
        await message.answer("⏳ Wyszukiwanie już trwa, poczekaj na wyniki...")
        return
    await state.update_data(_search_running=True)

    try:
        await _do_search(message, state, data_pre)
    finally:
        # Always release the lock — error, empty result and cancel included.
        try:
            await state.update_data(_search_running=False)
        except Exception:
            pass


async def _do_search(message: Message, state: FSMContext, data: Dict[str, Any]) -> None:
    """Body of cmd_search (separated so the lock release lives in one finally)."""
    from scraper.pipeline import run_search_pipeline, select_portals

    settings = get_settings()

    # Persist filters for restart recovery
    try:
        filters_file = PROJECT_ROOT / "filters.json"
        filter_data = {k: v for k, v in data.items() if k.startswith("filter_")}
        filters_file.write_text(json.dumps(filter_data, ensure_ascii=False))
    except Exception:
        pass

    filters = _build_filters(data)
    filters_info = _format_active_filters(data)
    portals = select_portals(settings.portals.enabled_portals())

    progress_msg = await message.answer(
        f"🔍 <b>Szukam...</b>\n\n"
        f"Portale: {len(portals)}\n"
        f"{filters_info}\n\n"
        f"⏳ Proszę czekać...",
        reply_markup=build_search_progress_keyboard(),
    )

    async def _edit(text: str) -> None:
        try:
            await progress_msg.edit_text(text)
        except Exception:
            pass  # rate limit / not modified — cosmetic only

    async def _progress(stage: str, d: Dict[str, Any]) -> None:
        if stage == "portal":
            icon = "✅" if d["status"] == "done" else "⚠️"
            await _edit(
                f"🔍 <b>Szukam...</b>\n\n"
                f"{icon} {d['portal']}: {d['status']} ({d['count']})\n"
                f"Postęp: {d['done']}/{d['total']} portali\n\n"
                f"⏳ Proszę czekać..."
            )
        elif stage == "deep":
            await _edit(
                f"🔬 <b>Deep scan: {d['candidates']} kandydatów...</b>\n\n"
                f"Pobieram pełne opisy ogłoszeń\n"
                f"(odrzucono {d['noise']} szumu)\n\n"
                f"⏳ Proszę czekać..."
            )

    try:
        result = await run_search_pipeline(
            filters=filters,
            portals=portals,
            timeout_per_portal=float(settings.scraping.portal_timeout),
            progress=_progress,
        )
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        await _edit(
            f"❌ <b>Błąd wyszukiwania</b>\n\n"
            f"Szczegóły: {str(e)[:200]}\n\n"
            f"Spróbuj ponownie za chwilę."
        )
        return

    display = result.display

    # Optional LLM analysis — only on the ranked shares, never on raw noise
    if settings.llm.enabled and settings.llm.api_key and display:
        await _edit(
            f"🤖 <b>Analizuję {min(len(display), MAX_LLM_ANALYZED)} udziałów z AI...</b>\n\n"
            f"⏳ Proszę czekać..."
        )
        display = await _run_llm_analysis(display)

    # ONE source of truth for page 1, pagination, save and detail
    await state.update_data(
        search_results=display,
        search_page=0,
        search_stats={
            "raw": result.raw_count,
            "candidates": result.candidates_count,
            "portals": result.portal_status,
        },
    )

    if not display:
        failed = [p for p, st in result.portal_status.items() if st["status"] != "done"]
        hint = f"\n⚠️ Portale bez odpowiedzi: {', '.join(failed)}" if failed else ""
        if result.raw_count == 0:
            await _edit(
                f"📭 <b>Brak wyników</b>\n\n"
                f"Przeszukano portali: {len(portals)}\n"
                f"{filters_info}{hint}\n\n"
                f"Spróbuj zmienić filtry (/filters) i wyszukaj ponownie."
            )
        else:
            await _edit(
                f"🔍 Przeszukano {len(portals)} portali, znaleziono {result.raw_count} ogłoszeń.\n\n"
                f"📭 Żadne nie wygląda na prawdziwy udział w nieruchomości.{hint}\n"
                f"Spróbuj rozszerzyć filtry lub poczekaj — nowe ogłoszenia pojawiają się codziennie."
            )
        return

    from bot.routers.results import PAGE_SIZE, _format_results_page
    from detector.ranking import format_summary

    total_pages = (len(display) + PAGE_SIZE - 1) // PAGE_SIZE
    page_text = _format_results_page(display[:PAGE_SIZE], 0, total_pages, len(display))
    full_text = f"{format_summary(result.classified)}\n\n{'─' * 30}\n\n{page_text}"

    try:
        await progress_msg.edit_text(
            full_text,
            reply_markup=build_results_keyboard(0, total_pages, display[:PAGE_SIZE]),
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"Could not edit progress message ({e}); sending new one")
        await message.answer(
            full_text,
            reply_markup=build_results_keyboard(0, total_pages, display[:PAGE_SIZE]),
            disable_web_page_preview=True,
        )

    logger.info(
        f"Search completed: {result.raw_count} raw → {result.candidates_count} candidates → "
        f"{len(display)} shares across {len(portals)} portals"
    )


def _build_filters(data: Dict[str, Any]) -> Dict[str, Any]:
    """Translate FSM filter_* keys into the scraper filters dict."""
    filters: Dict[str, Any] = {}
    if voiv := data.get("filter_voivodeship"):
        filters["voivodeship"] = voiv
    if city := data.get("filter_city"):
        filters["city"] = city
    if radius := data.get("filter_radius"):
        filters["radius_km"] = radius
    if price_min := data.get("filter_price_min"):
        filters["price_min"] = price_min
    if price_max := data.get("filter_price_max"):
        filters["price_max"] = price_max
    return filters


@router.callback_query(F.data == "search_cancel")
async def handle_search_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel ongoing search (releases the search lock)."""
    await callback.answer("❌ Wyszukiwanie anulowane")
    try:
        await state.update_data(_search_running=False)
    except Exception:
        pass
    if callback.message:
        try:
            await callback.message.edit_text("❌ Wyszukiwanie anulowane.")  # type: ignore[union-attr]
        except Exception:
            pass


@router.callback_query(F.data == "search_with_filters")
async def handle_search_with_filters(callback: CallbackQuery, state: FSMContext) -> None:
    """Trigger search after filter setup (from filter summary keyboard)."""
    await callback.answer()
    # callback.message.from_user is the BOT — check ownership on callback.from_user
    if not callback.from_user or not _is_owner(callback.from_user.id):
        return
    if callback.message:
        await start_search(callback.message, state)  # type: ignore[arg-type]


# --- LLM analysis ---

# Cap so a search never fires hundreds of paid API calls.
MAX_LLM_ANALYZED = 15


async def _run_llm_analysis(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Run LLM analysis on search results using ListingAnalyzer.

    Adds 'analysis' key to each result dict with AnalysisResult data,
    or None if analysis failed/skipped.
    Returns results sorted by stars (best first).
    """
    settings = get_settings()
    llm_config = {
        "enabled": settings.llm.enabled,
        "providers": [{
            "name": _provider_name(settings.llm.provider),
            "api_key": settings.llm.api_key,
            "model": settings.llm.model,
            "priority": 1,
        }],
        "max_concurrent": settings.llm.max_concurrent,
        "timeout": settings.llm.timeout,
    }

    try:
        from detector.llm_analyzer import create_analyzer_from_config, AnalysisResult
    except ImportError as e:
        logger.warning(f"LLM analyzer not available: {e}")
        return results

    analyzer = create_analyzer_from_config(llm_config)
    if analyzer is None:
        return results

    async def _analyze_one(item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single listing and attach result."""
        title = item.get("title", "")
        description = item.get("description", "")
        price = item.get("price")
        location = item.get("city", "") or item.get("location", "")
        fraction = item.get("fraction", "")

        result = await analyzer.analyze(
            title=title,
            description=description,
            price=price,
            location=location,
            fraction=fraction,
        )

        if result is not None:
            item["analysis"] = {
                "stars": result.stars,
                "summary": result.summary,
                "is_real_share": result.is_real_share,
                "fraction": result.key_facts.get("fraction", ""),
                "property_type": result.key_facts.get("property_type", ""),
                "seller_motivation": result.key_facts.get("seller_motivation", ""),
                "price_per_m2_estimate": result.key_facts.get("price_per_m2_estimate"),
            }
        else:
            item["analysis"] = None
        return item

    # Analyze only the top-ranked shares (cost cap); leave the rest untouched
    head, tail = results[:MAX_LLM_ANALYZED], results[MAX_LLM_ANALYZED:]
    analyzed = list(await asyncio.gather(*[_analyze_one(r) for r in head])) + tail

    # Sort by stars descending (items without analysis go to end)
    def sort_key(item: Dict[str, Any]) -> int:
        a = item.get("analysis")
        if a and a.get("stars"):
            return -a["stars"]
        return 0

    analyzed_list = list(analyzed)
    analyzed_list.sort(key=sort_key)  # stable: unanalyzed keep ranking order

    logger.info(
        f"LLM analysis complete: {sum(1 for r in analyzed_list if r.get('analysis'))}/"
        f"{len(analyzed_list)} analyzed, stats={analyzer.stats}"
    )
    return analyzed_list


def _provider_name(provider: str) -> str:
    """Map config provider names to detector.llm_analyzer PROVIDERS keys."""
    p = (provider or "openai").lower()
    return {"claude": "anthropic", "chatgpt": "openai"}.get(p, p)


# --- Formatters ---

def _format_results_page(
    results: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    total_results: int,
) -> str:
    """Format a page of results for display (delegates to results module)."""
    from bot.routers.results import _format_results_page as _results_format
    return _results_format(results, page, total_pages, total_results)


def _format_active_filters(data: Dict[str, Any]) -> str:
    """Format active filter summary for display."""
    parts: List[str] = []

    if voivodeship := data.get("filter_voivodeship"):
        parts.append(f"📍 Woj.: {voivodeship}")
    if city := data.get("filter_city"):
        parts.append(f"🏙️ Miasto: {city}")
    if price_min := data.get("filter_price_min"):
        parts.append(f"💰 Min cena: {price_min:,.0f} PLN")
    if price_max := data.get("filter_price_max"):
        parts.append(f"💰 Max cena: {price_max:,.0f} PLN")
    if radius := data.get("filter_radius"):
        parts.append(f"📐 Promień: {radius} km")

    if parts:
        return "Aktywne filtry:\n" + "\n".join(parts)
    return "Filtry: brak (szukam wszędzie)"
