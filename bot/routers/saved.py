"""
Saved listings management — view, delete, export saved listings.
"""

from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext

from bot.keyboards.inline import build_saved_keyboard


logger = logging.getLogger(__name__)

router = Router(name="saved")


# --- Callback Data ---

class SavedActionCallback(CallbackData, prefix="saved"):
    """Callback for saved listing actions."""
    action: str  # "view", "delete", "export", "page"
    listing_id: str = ""
    page: int = 0


# --- Handlers ---

@router.message(Command("saved"))
async def cmd_saved(message: Message, state: FSMContext) -> None:
    """Show saved listings."""
    # TODO: Load from database
    saved_listings: list[dict] = []

    if not saved_listings:
        await message.answer(
            "📭 <b>Brak zapisanych ogłoszeń</b>\n\n"
            "Użyj /search żeby znaleźć ogłoszenia,\n"
            "a następnie zapisz interesujące przyciskiem 💾.",
        )
        return

    text = _format_saved_list(saved_listings, page=0)
    await message.answer(
        text,
        reply_markup=build_saved_keyboard(saved_listings, page=0),
    )


@router.callback_query(SavedActionCallback.filter(F.action == "page"))
async def handle_saved_page(
    callback: CallbackQuery,
    callback_data: SavedActionCallback,
    state: FSMContext,
) -> None:
    """Paginate through saved listings."""
    await callback.answer()

    # TODO: Load from database
    saved_listings: list[dict] = []
    page = callback_data.page

    text = _format_saved_list(saved_listings, page=page)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=build_saved_keyboard(saved_listings, page=page),
    )


@router.callback_query(SavedActionCallback.filter(F.action == "delete"))
async def handle_saved_delete(
    callback: CallbackQuery,
    callback_data: SavedActionCallback,
) -> None:
    """Delete a saved listing."""
    listing_id = callback_data.listing_id

    # TODO: Delete from database
    await callback.answer(f"🗑️ Usunięto z zapisanych", show_alert=True)
    logger.info(f"Saved listing deleted: {listing_id}")


@router.callback_query(SavedActionCallback.filter(F.action == "export"))
async def handle_saved_export(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Export all saved listings as a text file."""
    await callback.answer()

    # TODO: Generate export file
    await callback.message.answer(  # type: ignore[union-attr]
        "📤 Eksport zapisanych ogłoszeń (wkrótce...)",
    )


@router.message(F.text == "💾 Zapisane")
async def btn_saved(message: Message, state: FSMContext) -> None:
    """Handle 'Saved' button from reply keyboard."""
    await cmd_saved(message, state)


# --- Formatters ---

def _format_saved_list(listings: list[dict], page: int) -> str:
    """Format saved listings for display."""
    if not listings:
        return "📭 Brak zapisanych ogłoszeń."

    page_size = 5
    start = page * page_size
    end = start + page_size
    page_listings = listings[start:end]
    total_pages = (len(listings) + page_size - 1) // page_size

    lines: list[str] = [
        f"💾 <b>Zapisane ogłoszenia</b> ({page + 1}/{total_pages})\n",
    ]

    for i, listing in enumerate(page_listings, start=start + 1):
        title = listing.get("title", "Bez tytułu")
        price = listing.get("price", "—")
        date_saved = listing.get("saved_at", "—")
        lines.append(f"<b>{i}.</b> {title}\n   💰 {price} | 📅 {date_saved}\n")

    return "\n".join(lines)
