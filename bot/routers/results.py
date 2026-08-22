"""
Results pagination — inline keyboard navigation through search results.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext

from bot.keyboards.inline import (
    build_results_keyboard,
    build_listing_detail_keyboard,
)


logger = logging.getLogger(__name__)

router = Router(name="results")


# --- Callback Data ---

class ResultsPageCallback(CallbackData, prefix="results"):
    """Callback data for results pagination."""
    page: int
    total_pages: int


class ListingActionCallback(CallbackData, prefix="listing"):
    """Callback data for listing actions."""
    action: str  # "detail", "save", "hide", "link"
    listing_id: str


# --- Handlers ---

@router.callback_query(ResultsPageCallback.filter())
async def handle_results_page(
    callback: CallbackQuery,
    callback_data: ResultsPageCallback,
    state: FSMContext,
) -> None:
    """Handle pagination through search results."""
    await callback.answer()

    data: dict[str, Any] = await state.get_data()
    results: list[dict[str, Any]] = data.get("search_results", [])

    page = callback_data.page
    page_size = 5
    total_pages = callback_data.total_pages

    # Calculate slice
    start = page * page_size
    end = start + page_size
    page_results = results[start:end]

    if not page_results:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 Brak wyników na tej stronie.",
        )
        return

    # Format results page
    text = _format_results_page(page_results, page, total_pages)

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=build_results_keyboard(page, total_pages, page_results),
    )


@router.callback_query(ListingActionCallback.filter(F.action == "detail"))
async def handle_listing_detail(
    callback: CallbackQuery,
    callback_data: ListingActionCallback,
    state: FSMContext,
) -> None:
    """Show detailed view of a single listing."""
    await callback.answer()

    data: dict[str, Any] = await state.get_data()
    results: list[dict[str, Any]] = data.get("search_results", [])

    # Find listing by ID
    listing = next(
        (r for r in results if r.get("id") == callback_data.listing_id),
        None,
    )

    if not listing:
        await callback.answer("❌ Ogłoszenie nie znalezione", show_alert=True)
        return

    text = _format_listing_detail(listing)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=build_listing_detail_keyboard(callback_data.listing_id),
    )


@router.callback_query(ListingActionCallback.filter(F.action == "save"))
async def handle_listing_save(
    callback: CallbackQuery,
    callback_data: ListingActionCallback,
    state: FSMContext,
) -> None:
    """Save a listing to user's saved collection."""
    # TODO: Persist to database
    await callback.answer("💾 Zapisano!", show_alert=True)
    logger.info(f"Listing saved: {callback_data.listing_id}")


@router.callback_query(ListingActionCallback.filter(F.action == "hide"))
async def handle_listing_hide(
    callback: CallbackQuery,
    callback_data: ListingActionCallback,
) -> None:
    """Hide a listing from future results."""
    # TODO: Add to hidden list in database
    await callback.answer("🙈 Ukryto — nie pojawi się ponownie", show_alert=True)
    logger.info(f"Listing hidden: {callback_data.listing_id}")


# --- Formatters ---

def _format_results_page(
    results: list[dict[str, Any]],
    page: int,
    total_pages: int,
) -> str:
    """Format a page of results for display."""
    lines: list[str] = [
        f"📋 <b>Wyniki</b> (strona {page + 1}/{total_pages})\n",
    ]

    for i, listing in enumerate(results, start=1):
        title = listing.get("title", "Bez tytułu")
        price = listing.get("price", "—")
        location = listing.get("location", "—")
        portal = listing.get("portal", "—")
        share = listing.get("share_fraction", "")

        lines.append(
            f"<b>{i}.</b> {title}\n"
            f"   💰 {price} | 📍 {location}\n"
            f"   🏷️ {portal}"
            + (f" | 📊 Udział: {share}" if share else "")
            + "\n"
        )

    return "\n".join(lines)


def _format_listing_detail(listing: dict[str, Any]) -> str:
    """Format a single listing detail view."""
    return (
        f"🏠 <b>{listing.get('title', 'Bez tytułu')}</b>\n\n"
        f"💰 Cena: {listing.get('price', '—')}\n"
        f"📍 Lokalizacja: {listing.get('location', '—')}\n"
        f"📊 Udział: {listing.get('share_fraction', '—')}\n"
        f"🏷️ Portal: {listing.get('portal', '—')}\n"
        f"📅 Data: {listing.get('date', '—')}\n\n"
        f"📝 {listing.get('description', 'Brak opisu')}\n\n"
        f"🔗 <a href=\"{listing.get('url', '#')}\">Otwórz ogłoszenie</a>"
    )
