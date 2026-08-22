"""
/search command — triggers property share scraping across portals.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.config import get_settings
from bot.keyboards.inline import build_search_progress_keyboard
from bot.keyboards.reply import main_menu_keyboard


logger = logging.getLogger(__name__)

router = Router(name="search")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command — welcome message and main menu."""
    settings = get_settings()

    # Single-user check
    if settings.telegram.owner_id and message.from_user:
        if message.from_user.id != settings.telegram.owner_id:
            await message.answer("⛔ Bot jest prywatny.")
            return

    await message.answer(
        "🏠 <b>Udziały Bot</b>\n\n"
        "Witaj! Przeszukuję portale nieruchomości w poszukiwaniu "
        "ofert sprzedaży udziałów.\n\n"
        "Użyj /search aby rozpocząć wyszukiwanie\n"
        "lub /help aby zobaczyć dostępne komendy.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command — show available commands."""
    await message.answer(
        "📋 <b>Dostępne komendy:</b>\n\n"
        "/search — Nowe wyszukiwanie\n"
        "/filters — Ustaw filtry (woj., miasto, cena)\n"
        "/saved — Zapisane ogłoszenia\n"
        "/settings — Ustawienia\n"
        "/help — Ta pomoc",
    )


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    """
    Handle /search command — initiate scraping across all enabled portals.

    Sends a progress message that gets updated as portals are scraped.
    """
    settings = get_settings()

    # Owner check
    if settings.telegram.owner_id and message.from_user:
        if message.from_user.id != settings.telegram.owner_id:
            return

    # Get current filters from FSM state
    data: dict[str, Any] = await state.get_data()
    filters_info = _format_active_filters(data)

    # Send initial progress message
    enabled = settings.portals.enabled_portals()
    progress_msg = await message.answer(
        f"🔍 <b>Rozpoczynam wyszukiwanie...</b>\n\n"
        f"Portale: {len(enabled)}\n"
        f"{filters_info}\n\n"
        f"⏳ Proszę czekać...",
        reply_markup=build_search_progress_keyboard(),
    )

    # Store message ID for progress updates
    await state.update_data(
        search_message_id=progress_msg.message_id,
        search_results=[],
    )

    # TODO: Trigger actual scraping pipeline here
    # Results will be collected and displayed via results router
    total_found = 0

    await progress_msg.edit_text(
        f"✅ <b>Wyszukiwanie zakończone</b>\n\n"
        f"Przeszukano portali: {len(enabled)}\n"
        f"Znaleziono ogłoszeń: {total_found}\n"
        f"{filters_info}\n\n"
        f"Użyj przycisków poniżej aby przeglądać wyniki.",
    )

    logger.info(f"Search completed: {total_found} listings found across {len(enabled)} portals")


@router.message(F.text == "🔍 Szukaj")
async def btn_search(message: Message, state: FSMContext) -> None:
    """Handle 'Search' button from reply keyboard."""
    await cmd_search(message, state)


def _format_active_filters(data: dict[str, Any]) -> str:
    """Format active filter summary for display."""
    parts: list[str] = []

    if voivodeship := data.get("filter_voivodeship"):
        parts.append(f"📍 Woj.: {voivodeship}")
    if city := data.get("filter_city"):
        parts.append(f"🏙️ Miasto: {city}")
    if price_max := data.get("filter_price_max"):
        parts.append(f"💰 Max cena: {price_max:,.0f} PLN")
    if radius := data.get("filter_radius"):
        parts.append(f"📐 Promień: {radius} km")

    if parts:
        return "Aktywne filtry:\n" + "\n".join(parts)
    return "Filtry: brak (szukam wszędzie)"
