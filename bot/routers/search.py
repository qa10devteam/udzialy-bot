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
        await message.answer("⛔ Bot jest prywatny. Brak dostępu.")
        return

    # Reset state on fresh start
    await state.clear()

    settings = get_settings()
    has_ai = settings.llm.enabled and settings.llm.api_key

    if has_ai:
        await message.answer(
            "👋 <b>Cześć! Jestem Udziały Bot.</b>\n\n"
            "Przeszukuję 8 portali nieruchomości w poszukiwaniu "
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
    Handle /search command and 🔍 button — initiate scraping.

    1. Send 'Szukam...' message
    2. Call ScraperManager.search_all() with active filters
    3. Update message with progress
    4. Show results with pagination
    """
    if not message.from_user or not _is_owner(message.from_user.id):
        return

    # Prevent concurrent searches
    data_pre: Dict[str, Any] = await state.get_data()
    if data_pre.get("_search_running"):
        await message.answer("⏳ Wyszukiwanie już trwa, poczekaj na wyniki...")
        return
    await state.update_data(_search_running=True)

    # Persist filters for restart recovery
    try:
        filters_file = PROJECT_ROOT / "filters.json"
        filter_data = {k: v for k, v in data_pre.items() if k.startswith("filter_")}
        filters_file.write_text(json.dumps(filter_data, ensure_ascii=False))
    except Exception:
        pass

    settings = get_settings()

    # Get current filters from FSM state
    data: Dict[str, Any] = await state.get_data()

    # Build filters dict for scraper
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

    filters_info = _format_active_filters(data)
    enabled = settings.portals.enabled_portals()

    # Send initial progress message
    progress_msg = await message.answer(
        f"🔍 <b>Szukam...</b>\n\n"
        f"Portale: {len(enabled)}\n"
        f"{filters_info}\n\n"
        f"⏳ Proszę czekać...",
        reply_markup=build_search_progress_keyboard(),
    )

    # Run the scraper
    results: List[Dict[str, Any]] = []
    try:
        results = await _run_search(enabled, filters, progress_msg)
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        await progress_msg.edit_text(
            f"❌ <b>Błąd wyszukiwania</b>\n\n"
            f"Szczegóły: {str(e)[:200]}\n\n"
            f"Spróbuj ponownie za chwilę.",
        )
        return

    # Store results in FSM state for pagination
    await state.update_data(search_results=results, search_page=0)

    if not results:
        await progress_msg.edit_text(
            f"📭 <b>Brak wyników</b>\n\n"
            f"Przeszukano portali: {len(enabled)}\n"
            f"{filters_info}\n\n"
            f"Spróbuj zmienić filtry (/filters) i wyszukaj ponownie.",
        )
        return

    # === STAGE 2: DEEP FETCH candidates ===
    # Only deep-fetch listings that have SOME signal (score > 0)
    from detector.scorer import PropertyShareScorer
    scorer = PropertyShareScorer()
    
    candidates = []
    noise = []
    for listing in results:
        r = scorer.score(listing.get("title", ""), listing.get("raw_description", ""))
        listing["score"] = r.score
        listing["is_share"] = r.is_share
        listing["fraction_detected"] = r.fraction_detected
        if r.score > 0:
            candidates.append(listing)
        else:
            noise.append(listing)

    if candidates:
        try:
            await progress_msg.edit_text(
                f"🔬 <b>Deep scan: {len(candidates)} kandydatów...</b>\n\n"
                f"Pobieram pełne opisy ogłoszeń\n"
                f"(odrzucono {len(noise)} szumu)\n\n"
                f"⏳ Proszę czekać...",
            )
        except Exception:
            pass
        
        from scraper.deep_parser import deep_fetch_batch, rescore_with_deep_data
        candidates = await deep_fetch_batch(candidates, max_concurrent=5)
        candidates = rescore_with_deep_data(candidates)

    # === STAGE 3: CLASSIFY + RANK ===
    from detector.ranking import classify_and_rank, format_summary, format_results_page as fmt_page

    # Use candidates (deep-fetched + re-scored) for classification
    classified = classify_and_rank(candidates, min_score=25)

    # Store classified results for pagination (compact: no raw HTML/descriptions)
    await state.update_data(
        classified_results=[{
            "score": c.score, "tier": c.tier.value,
            "source": c.source.value, "property_type": c.property_type.value,
            "fraction": c.fraction, "attractiveness": c.attractiveness,
            "url": c.url, "title": c.title[:80], "price": c.price,
            "city": c.city, "portal": c.portal,
        } for c in classified],
        classified_page=0,
    )

    # Run LLM analysis on top tier if enabled
    if settings.llm.enabled and settings.llm.api_key and classified:
        try:
            await progress_msg.edit_text(
                f"🤖 <b>Analizuję {len(classified)} udziałów z AI...</b>\n\n"
                f"⏳ Proszę czekać...",
            )
        except Exception:
            pass
        results = await _run_llm_analysis(results)

    # Show summary + first page
    summary = format_summary(classified)
    
    if classified:
        page_text, total_pages = fmt_page(classified, page=0, page_size=5)
        full_text = f"{summary}\n\n{'─' * 30}\n\n{page_text}"
    else:
        full_text = (
            f"🔍 Przeszukano {len(enabled)} portali, znaleziono {len(results)} ogłoszeń.\n\n"
            f"📭 Żadne nie wygląda na prawdziwy udział w nieruchomości.\n"
            f"Spróbuj rozszerzyć filtry lub poczekaj — nowe ogłoszenia pojawiają się codziennie."
        )
        total_pages = 1

    await progress_msg.edit_text(
        full_text,
        reply_markup=build_results_keyboard(0, total_pages, results[:5] if results else []),
        disable_web_page_preview=True,
    )

    logger.info(
        f"Search completed: {len(results)} raw → {len(classified)} classified shares "
        f"across {len(enabled)} portals"
    )

    # Release search lock (also handles cancellation)
    try:
        await state.update_data(_search_running=False)
    except Exception:
        pass


@router.callback_query(F.data == "search_cancel")
async def handle_search_cancel(callback: CallbackQuery) -> None:
    """Cancel ongoing search."""
    await callback.answer("❌ Wyszukiwanie anulowane")
    if callback.message:
        await callback.message.edit_text("❌ Wyszukiwanie anulowane.")  # type: ignore[union-attr]


@router.callback_query(F.data == "search_with_filters")
async def handle_search_with_filters(callback: CallbackQuery, state: FSMContext) -> None:
    """Trigger search after filter setup (from filter summary keyboard)."""
    await callback.answer()
    if callback.message:
        # Create a fake message-like trigger for the search
        await cmd_search(callback.message, state)  # type: ignore[arg-type]


# --- Search execution ---

async def _run_search(
    enabled_portals: List[str],
    filters: Dict[str, Any],
    progress_msg: Message,
) -> List[Dict[str, Any]]:
    """
    Execute the search via ScraperManager.

    Updates progress_msg as portals are scraped.
    Returns list of result dicts suitable for display.
    """
    results: List[Dict[str, Any]] = []

    try:
        # Try to import and use the real ScraperManager
        sys.path.insert(0, str(get_settings()._find_project_root() if hasattr(get_settings(), '_find_project_root') else ''))
        from scraper.manager import ScraperManager

        manager = ScraperManager()
        manager.register_all_portals()

        portals_done = 0
        total_portals = len(enabled_portals)

        async def progress_callback(portal_name: str, status: str) -> None:
            nonlocal portals_done
            portals_done += 1
            try:
                await progress_msg.edit_text(
                    f"🔍 <b>Szukam...</b>\n\n"
                    f"✅ {portal_name}: {status}\n"
                    f"Postęp: {portals_done}/{total_portals} portali\n\n"
                    f"⏳ Proszę czekać...",
                )
            except Exception:
                pass  # Ignore edit errors (rate limit, etc.)

        # Default keywords for share detection
        keywords = ["udział", "udziały", "współwłasność", "1/2", "1/4", "1/3"]

        raw_results = await manager.search_all(
            keywords=keywords,
            filters=filters,
            progress_callback=progress_callback,
        )

        # Convert RawListing objects to dicts for display
        for item in raw_results:
            if hasattr(item, '__dict__'):
                d = {
                    "id": getattr(item, "id", ""),
                    "title": getattr(item, "title", "Bez tytułu"),
                    "price": getattr(item, "price", None),
                    "city": getattr(item, "city", None) or getattr(item, "location", ""),
                    "voivodeship": getattr(item, "voivodeship", ""),
                    "url": getattr(item, "url", ""),
                    "source": getattr(item, "source", ""),
                    "score": getattr(item, "score", 0),
                    "fraction": getattr(item, "fraction", ""),
                    "area": getattr(item, "area", None),
                }
            elif isinstance(item, dict):
                d = item
            else:
                continue
            results.append(d)

    except ImportError as e:
        logger.warning(f"ScraperManager not available: {e}. Returning empty results.")
    except Exception as e:
        logger.error(f"Scraper error: {e}", exc_info=True)
        raise

    return results


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
        "api_key": settings.llm.api_key,
        "model": settings.llm.model,
        "base_url": settings.llm.base_url,
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

    # Run all analyses concurrently (semaphore in analyzer limits parallelism)
    analyzed = await asyncio.gather(*[_analyze_one(r) for r in results])

    # Sort by stars descending (items without analysis go to end)
    def sort_key(item: Dict[str, Any]) -> int:
        a = item.get("analysis")
        if a and a.get("stars"):
            return -a["stars"]
        return 0

    analyzed_list = list(analyzed)
    analyzed_list.sort(key=sort_key)

    logger.info(
        f"LLM analysis complete: {sum(1 for r in analyzed_list if r.get('analysis'))}/"
        f"{len(analyzed_list)} analyzed, stats={analyzer.stats}"
    )
    return analyzed_list


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
