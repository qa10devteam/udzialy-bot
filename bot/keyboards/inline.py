"""
Inline keyboard builders — pagination, listing actions, filters, settings.
"""

from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_search_progress_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during search (cancel button)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Anuluj", callback_data="search_cancel")
    return builder.as_markup()


def build_results_keyboard(
    page: int,
    total_pages: int,
    results: list[dict[str, Any]],
) -> InlineKeyboardMarkup:
    """Build pagination keyboard for search results."""
    builder = InlineKeyboardBuilder()

    # Listing action buttons (one row per listing)
    for listing in results:
        listing_id = listing.get("id", "")
        builder.row(
            InlineKeyboardButton(
                text=f"📄 {listing.get('title', '?')[:20]}",
                callback_data=f"listing:detail:{listing_id}",
            ),
            InlineKeyboardButton(
                text="💾",
                callback_data=f"listing:save:{listing_id}",
            ),
            InlineKeyboardButton(
                text="🙈",
                callback_data=f"listing:hide:{listing_id}",
            ),
        )

    # Navigation row
    nav_buttons: list[InlineKeyboardButton] = []

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️ Poprzednia",
                callback_data=f"results:{page - 1}:{total_pages}",
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Następna ▶️",
                callback_data=f"results:{page + 1}:{total_pages}",
            )
        )

    builder.row(*nav_buttons)
    return builder.as_markup()


def build_listing_detail_keyboard(listing_id: str) -> InlineKeyboardMarkup:
    """Build keyboard for single listing detail view."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💾 Zapisz", callback_data=f"listing:save:{listing_id}"),
        InlineKeyboardButton(text="🙈 Ukryj", callback_data=f"listing:hide:{listing_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Otwórz link", callback_data=f"listing:link:{listing_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Powrót do wyników", callback_data="results:0:1"),
    )
    return builder.as_markup()


def build_voivodeship_keyboard(
    voivodeships: dict[str, str],
) -> InlineKeyboardMarkup:
    """Build voivodeship selection keyboard (4 columns)."""
    builder = InlineKeyboardBuilder()

    for code, name in voivodeships.items():
        builder.button(
            text=name.capitalize(),
            callback_data=f"voiv:{code}:{name}",
        )

    # Skip button
    builder.button(text="⏭️ Pomiń (cała Polska)", callback_data="filter_act:skip")

    # Arrange in grid: 2 per row for voivodeships + 1 row for skip
    builder.adjust(2, 2, 2, 2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def build_filter_summary_keyboard() -> InlineKeyboardMarkup:
    """Keyboard after filter configuration."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Szukaj z filtrami", callback_data="search_with_filters"),
        InlineKeyboardButton(text="🗑️ Resetuj filtry", callback_data="filter_act:reset"),
    )
    return builder.as_markup()


def build_saved_keyboard(
    listings: list[dict[str, Any]],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Build keyboard for saved listings view."""
    builder = InlineKeyboardBuilder()
    page_size = 5
    total_pages = max(1, (len(listings) + page_size - 1) // page_size)

    # Action buttons for each listing
    start = page * page_size
    end = start + page_size
    for listing in listings[start:end]:
        lid = listing.get("id", "")
        builder.row(
            InlineKeyboardButton(text="👁️ Szczegóły", callback_data=f"saved:view:{lid}:0"),
            InlineKeyboardButton(text="🗑️ Usuń", callback_data=f"saved:delete:{lid}:0"),
        )

    # Navigation
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"saved:page::{page - 1}")
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"saved:page::{page + 1}")
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    # Export
    builder.row(
        InlineKeyboardButton(text="📤 Eksportuj wszystkie", callback_data="saved:export::0")
    )

    return builder.as_markup()


def build_settings_keyboard(data: dict[str, Any]) -> InlineKeyboardMarkup:
    """Build settings panel keyboard."""
    builder = InlineKeyboardBuilder()

    # Notification toggle
    notif_enabled = data.get("notifications_enabled", True)
    notif_text = "🔔 Wyłącz powiadomienia" if notif_enabled else "🔕 Włącz powiadomienia"
    builder.row(
        InlineKeyboardButton(
            text=notif_text,
            callback_data="settings:toggle_notifications:::",
        )
    )

    # Portal toggles (sample)
    portals = ["otodom", "olx", "gratka", "morizon"]
    disabled = data.get("disabled_portals", [])

    for portal in portals:
        status = "❌" if portal in disabled else "✅"
        builder.button(
            text=f"{status} {portal}",
            callback_data=f"settings:toggle_portal:{portal}:",
        )
    builder.adjust(2)  # 2 portals per row

    # Reset
    builder.row(
        InlineKeyboardButton(text="🔄 Reset ustawień", callback_data="settings:reset:::")
    )

    return builder.as_markup()
