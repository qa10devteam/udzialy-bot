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
from typing import Any, Dict, List

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import get_settings
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
async def cmd_start(message: Message) -> None:
    """Handle /start command — welcome message and main menu."""
    if not message.from_user or not _is_owner(message.from_user.id):
        await message.answer("⛔ Bot jest prywatny. Brak dostępu.")
        return

    await message.answer(
        "🏠 <b>Udziały Bot</b>\n\n"
        "Witaj! Przeszukuję portale nieruchomości w poszukiwaniu "
        "ofert sprzedaży udziałów w nieruchomościach.\n\n"
        "🔍 <b>Szukaj</b> — rozpocznij wyszukiwanie\n"
        "⚙️ <b>Filtry</b> — ustaw województwo, miasto, cenę\n"
        "📋 <b>Zapisane</b> — przeglądaj zapisane ogłoszenia\n"
        "❓ <b>Pomoc</b> — dostępne komendy\n\n"
        "Użyj przycisków poniżej lub wpisz /search",
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

    # Show first page of results
    page_size = 5
    total_pages = (len(results) + page_size - 1) // page_size
    page_results = results[:page_size]

    text = _format_results_page(page_results, 0, total_pages, len(results))
    await progress_msg.edit_text(
        text,
        reply_markup=build_results_keyboard(0, total_pages, page_results),
        disable_web_page_preview=True,
    )

    logger.info(f"Search completed: {len(results)} listings found across {len(enabled)} portals")


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


# --- Formatters ---

def _format_results_page(
    results: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    total_results: int,
) -> str:
    """Format a page of results for display."""
    lines: List[str] = [
        f"📋 <b>Wyniki wyszukiwania</b> (str. {page + 1}/{total_pages}, "
        f"łącznie: {total_results})\n",
    ]

    for i, listing in enumerate(results, start=page * 5 + 1):
        title = listing.get("title", "Bez tytułu")[:60]
        price = listing.get("price")
        city = listing.get("city", "—")
        score = listing.get("score", 0)
        source = listing.get("source", "")

        price_str = f"{price:,.0f} PLN" if price else "cena nieznana"

        lines.append(
            f"<b>{i}.</b> {title}\n"
            f"   💰 {price_str} | 📍 {city}\n"
            f"   📊 Trafność: {score}/100 | 🏷️ {source}\n"
        )

    return "\n".join(lines)


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
