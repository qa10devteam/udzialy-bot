"""
Results pagination — inline keyboard navigation through search results.

Handles page_N callbacks, formats listings (title, price, city, score, link),
5 per page, inline keyboard with ◀️▶️ + 💾 save button per listing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import get_settings
from bot.keyboards.inline import build_results_keyboard, build_listing_detail_keyboard

logger = logging.getLogger(__name__)

router = Router(name="results")

PAGE_SIZE = 5


# --- Pagination handler ---

@router.callback_query(F.data.startswith("page:"))
async def handle_page_navigation(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle pagination: page:N callback."""
    if not callback.from_user or not _is_owner(callback.from_user.id):
        await callback.answer("⛔ Brak dostępu", show_alert=True)
        return

    await callback.answer()

    # Parse page number
    try:
        page = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        page = 0

    data: Dict[str, Any] = await state.get_data()
    results: List[Dict[str, Any]] = data.get("search_results", [])

    if not results:
        await callback.message.edit_text("📭 Brak wyników do wyświetlenia.")  # type: ignore[union-attr]
        return

    total_pages = (len(results) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))

    # Get page slice
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_results = results[start:end]

    text = _format_results_page(page_results, page, total_pages, len(results))

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=build_results_keyboard(page, total_pages, page_results),
            disable_web_page_preview=True,
        )
    except Exception:
        pass  # Message not modified (same page)

    # Update current page in state
    await state.update_data(search_page=page)


# --- Listing actions ---

@router.callback_query(F.data.startswith("listing:save:"))
async def handle_listing_save(callback: CallbackQuery, state: FSMContext) -> None:
    """Save a listing to user's saved collection in SQLite."""
    if not callback.from_user or not _is_owner(callback.from_user.id):
        await callback.answer("⛔ Brak dostępu", show_alert=True)
        return

    listing_id = callback.data.split(":", 2)[2]  # type: ignore[union-attr]

    data: Dict[str, Any] = await state.get_data()
    results: List[Dict[str, Any]] = data.get("search_results", [])

    # Find listing
    listing = next((r for r in results if r.get("id") == listing_id), None)
    if not listing:
        await callback.answer("❌ Ogłoszenie nie znalezione", show_alert=True)
        return

    # Save to database
    try:
        from storage.database import DatabaseManager
        from storage import queries

        settings = get_settings()
        db = DatabaseManager(settings.database.path)
        await db.initialize()

        # Save the listing
        await db.execute(
            """
            INSERT OR IGNORE INTO saved_listings (listing_id, notes, saved_at)
            VALUES (?, ?, datetime('now'))
            """,
            (listing_id, listing.get("title", "")),
        )
        await db.commit()
        await db.close()

        await callback.answer("💾 Zapisano!", show_alert=True)
        logger.info(f"Listing saved: {listing_id}")
    except Exception as e:
        logger.error(f"Failed to save listing: {e}")
        # Fallback: save to FSM state
        saved = data.get("saved_listings", [])
        if not any(s.get("id") == listing_id for s in saved):
            saved.append(listing)
            await state.update_data(saved_listings=saved)
        await callback.answer("💾 Zapisano (w pamięci)!", show_alert=True)


@router.callback_query(F.data.startswith("listing:detail:"))
async def handle_listing_detail(callback: CallbackQuery, state: FSMContext) -> None:
    """Show detailed view of a single listing."""
    if not callback.from_user or not _is_owner(callback.from_user.id):
        await callback.answer("⛔ Brak dostępu", show_alert=True)
        return

    await callback.answer()

    listing_id = callback.data.split(":", 2)[2]  # type: ignore[union-attr]

    data: Dict[str, Any] = await state.get_data()
    results: List[Dict[str, Any]] = data.get("search_results", [])

    listing = next((r for r in results if r.get("id") == listing_id), None)
    if not listing:
        await callback.answer("❌ Ogłoszenie nie znalezione", show_alert=True)
        return

    text = _format_listing_detail(listing)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=build_listing_detail_keyboard(listing_id, listing.get("url", "")),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """No-op callback for informational buttons (page counter)."""
    await callback.answer()


# --- Formatters ---

def _format_results_page(
    results: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    total_results: int,
) -> str:
    """Format a page of results for display.

    If analysis data is present (LLM mode), shows stars + summary + risks.
    Otherwise falls back to basic title + price + link format.
    """
    lines: List[str] = [
        f"📋 <b>Wyniki</b> (str. {page + 1}/{total_pages}, "
        f"łącznie: {total_results})\n",
    ]

    for i, listing in enumerate(results, start=page * PAGE_SIZE + 1):
        title = listing.get("title", "Bez tytułu")[:60]
        price = listing.get("price")
        city = listing.get("city", "—")
        url = listing.get("url", "")
        analysis = listing.get("analysis")

        price_str = f"{price:,.0f} PLN" if price else "—"

        if analysis:
            # LLM-enriched format: stars + summary + risks
            stars = analysis.get("stars", 0)
            stars_str = "⭐" * stars + "☆" * (5 - stars)
            summary = analysis.get("summary", "")
            is_real = analysis.get("is_real_share", True)
            fraction = analysis.get("fraction", "")
            prop_type = analysis.get("property_type", "")
            motivation = analysis.get("seller_motivation", "")

            # Build risk indicators
            risks: List[str] = []
            if not is_real:
                risks.append("⚠️ Możliwe nie-udział")
            if motivation and motivation.lower() in ("egzekucja", "syndyk"):
                risks.append(f"⚡ {motivation}")

            line = (
                f"<b>{i}.</b> {stars_str} {title}\n"
                f"   💰 {price_str} | 📍 {city}\n"
            )
            if fraction:
                line += f"   📊 Udział: {fraction}"
                if prop_type:
                    line += f" | 🏠 {prop_type}"
                line += "\n"
            if summary:
                line += f"   💡 <i>{summary[:120]}</i>\n"
            if risks:
                line += f"   {'  '.join(risks)}\n"
            if url:
                line += f'   🔗 <a href="{url}">Link</a>'
        else:
            # Basic format (no LLM)
            source = listing.get("source", "")
            score = listing.get("score", 0)
            line = (
                f"<b>{i}.</b> {title}\n"
                f"   💰 {price_str} | 📍 {city}\n"
                f"   📊 {score}/100 | 🏷️ {source}"
            )
            if url:
                line += f'\n   🔗 <a href="{url}">Link</a>'

        lines.append(line + "\n")

    return "\n".join(lines)


def _format_listing_detail(listing: Dict[str, Any]) -> str:
    """Format a single listing detail view with optional LLM analysis."""
    title = listing.get("title", "Bez tytułu")
    price = listing.get("price")
    city = listing.get("city", "—")
    voivodeship = listing.get("voivodeship", "—")
    score = listing.get("score", 0)
    source = listing.get("source", "—")
    fraction = listing.get("fraction", "")
    area = listing.get("area")
    url = listing.get("url", "")
    analysis = listing.get("analysis")

    price_str = f"{price:,.0f} PLN" if price else "—"
    area_str = f"{area} m²" if area else "—"

    text = (
        f"🏠 <b>{title}</b>\n\n"
        f"💰 Cena: {price_str}\n"
        f"📍 Lokalizacja: {city}, {voivodeship}\n"
        f"📐 Powierzchnia: {area_str}\n"
        f"📊 Trafność: {score}/100\n"
        f"🏷️ Portal: {source}\n"
    )

    if analysis:
        # LLM analysis section
        stars = analysis.get("stars", 0)
        stars_str = "⭐" * stars + "☆" * (5 - stars)
        summary = analysis.get("summary", "")
        is_real = analysis.get("is_real_share", True)
        a_fraction = analysis.get("fraction", "")
        prop_type = analysis.get("property_type", "")
        motivation = analysis.get("seller_motivation", "")
        price_m2 = analysis.get("price_per_m2_estimate")

        text += f"\n{'─' * 20}\n"
        text += f"🤖 <b>Analiza AI:</b> {stars_str}\n"
        if a_fraction:
            text += f"📊 Udział: {a_fraction}\n"
        if prop_type:
            text += f"🏠 Typ: {prop_type}\n"
        if motivation and motivation != "nieznana":
            text += f"👤 Motywacja: {motivation}\n"
        if price_m2:
            text += f"💲 Szt. cena/m²: ~{price_m2:,.0f} PLN\n"
        if not is_real:
            text += "⚠️ <b>Uwaga:</b> Może nie być prawdziwym udziałem!\n"
        if summary:
            text += f"\n💡 <i>{summary}</i>\n"
    else:
        if fraction:
            text += f"📊 Udział: {fraction}\n"

    if url:
        text += f'\n🔗 <a href="{url}">Otwórz ogłoszenie</a>'

    return text


def _is_owner(user_id: int | None) -> bool:
    """Check if user is the bot owner."""
    settings = get_settings()
    if settings.owner_id == 0:
        return True
    return user_id == settings.owner_id
