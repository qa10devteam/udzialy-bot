"""
Saved listings management — /saved command, pagination, delete.

Shows saved listings from SQLite with pagination (5 per page)
and option to delete individual items.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import get_settings
from bot.keyboards.inline import build_saved_keyboard
from bot.keyboards.reply import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="saved")

PAGE_SIZE = 5


def _is_owner(user_id: int | None) -> bool:
    """Check if user is the bot owner."""
    settings = get_settings()
    if settings.owner_id == 0:
        return True
    return user_id == settings.owner_id


# --- Entry points ---

@router.message(Command("saved"))
@router.message(F.text == "📋 Zapisane")
async def cmd_saved(message: Message, state: FSMContext) -> None:
    """Show saved listings with pagination."""
    if not message.from_user or not _is_owner(message.from_user.id):
        return

    saved_listings = await _load_saved_listings(state)

    if not saved_listings:
        await message.answer(
            "📭 <b>Brak zapisanych ogłoszeń</b>\n\n"
            "Użyj /search żeby znaleźć ogłoszenia,\n"
            "a następnie zapisz interesujące przyciskiem 💾.",
            reply_markup=main_menu_keyboard(),
        )
        return

    text = _format_saved_list(saved_listings, page=0)
    await message.answer(
        text,
        reply_markup=build_saved_keyboard(saved_listings, page=0),
        disable_web_page_preview=True,
    )


# --- Pagination ---

@router.callback_query(F.data.startswith("saved_page:"))
async def handle_saved_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Paginate through saved listings."""
    if not callback.from_user or not _is_owner(callback.from_user.id):
        await callback.answer("⛔ Brak dostępu", show_alert=True)
        return

    await callback.answer()

    try:
        page = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        page = 0

    saved_listings = await _load_saved_listings(state)

    if not saved_listings:
        await callback.message.edit_text("📭 Brak zapisanych ogłoszeń.")  # type: ignore[union-attr]
        return

    total_pages = (len(saved_listings) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))

    text = _format_saved_list(saved_listings, page=page)
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=build_saved_keyboard(saved_listings, page=page),
            disable_web_page_preview=True,
        )
    except Exception:
        pass


# --- Delete ---

@router.callback_query(F.data.startswith("saved_del:"))
async def handle_saved_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """Delete a saved listing."""
    if not callback.from_user or not _is_owner(callback.from_user.id):
        await callback.answer("⛔ Brak dostępu", show_alert=True)
        return

    listing_id = callback.data.split(":", 1)[1]  # type: ignore[union-attr]

    # Try to delete from database
    try:
        from storage.database import DatabaseManager

        settings = get_settings()
        db = DatabaseManager(settings.database.path)
        await db.initialize()
        await db.execute(
            "DELETE FROM saved_listings WHERE listing_id = ?",
            (listing_id,),
        )
        await db.commit()
        await db.close()
    except Exception as e:
        logger.warning(f"DB delete failed: {e}")

    # Also remove from FSM state
    data = await state.get_data()
    saved = data.get("saved_listings", [])
    saved = [s for s in saved if s.get("id") != listing_id]
    await state.update_data(saved_listings=saved)

    await callback.answer("🗑️ Usunięto z zapisanych", show_alert=True)
    logger.info(f"Saved listing deleted: {listing_id}")

    # Refresh the list
    saved_listings = await _load_saved_listings(state)
    if not saved_listings:
        await callback.message.edit_text("📭 Brak zapisanych ogłoszeń.")  # type: ignore[union-attr]
    else:
        text = _format_saved_list(saved_listings, page=0)
        try:
            await callback.message.edit_text(  # type: ignore[union-attr]
                text,
                reply_markup=build_saved_keyboard(saved_listings, page=0),
                disable_web_page_preview=True,
            )
        except Exception:
            pass


# --- Data loading ---

async def _load_saved_listings(state: FSMContext) -> List[Dict[str, Any]]:
    """Load saved listings from DB, falling back to FSM state."""
    try:
        from storage.database import DatabaseManager

        settings = get_settings()
        db = DatabaseManager(settings.database.path)
        await db.initialize()

        rows = await db.fetchall(
            """
            SELECT s.listing_id as id, s.notes as title, s.saved_at,
                   l.title as listing_title, l.price, l.city, l.url, l.score
            FROM saved_listings s
            LEFT JOIN listings l ON s.listing_id = l.id
            ORDER BY s.saved_at DESC
            """,
        )
        await db.close()

        if rows:
            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "title": row.get("listing_title") or row.get("title") or "Bez tytułu",
                    "price": row.get("price"),
                    "city": row.get("city", "—"),
                    "url": row.get("url", ""),
                    "score": row.get("score", 0),
                    "saved_at": row.get("saved_at", ""),
                })
            return results
    except Exception as e:
        logger.debug(f"Could not load from DB: {e}")

    # Fallback: FSM state
    data = await state.get_data()
    return data.get("saved_listings", [])


# --- Formatters ---

def _format_saved_list(listings: List[Dict[str, Any]], page: int) -> str:
    """Format saved listings for display."""
    if not listings:
        return "📭 Brak zapisanych ogłoszeń."

    total_pages = max(1, (len(listings) + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_listings = listings[start:end]

    lines: List[str] = [
        f"💾 <b>Zapisane ogłoszenia</b> (str. {page + 1}/{total_pages})\n",
    ]

    for i, listing in enumerate(page_listings, start=start + 1):
        title = listing.get("title", "Bez tytułu")[:50]
        price = listing.get("price")
        city = listing.get("city", "—")
        saved_at = listing.get("saved_at", "")[:10]

        price_str = f"{price:,.0f} PLN" if price else "—"

        lines.append(
            f"<b>{i}.</b> {title}\n"
            f"   💰 {price_str} | 📍 {city}\n"
            f"   📅 Zapisano: {saved_at}\n"
        )

    return "\n".join(lines)
