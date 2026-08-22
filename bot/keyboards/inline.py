"""
Inline keyboard builders — pagination, listing actions, filters, voivodeships, radius.
"""

from __future__ import annotations

from typing import Any, Dict, List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# --- Search / Results ---

def build_search_progress_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during search (cancel button)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Anuluj", callback_data="search_cancel")
    return builder.as_markup()


def build_results_keyboard(
    page: int,
    total_pages: int,
    results: List[Dict[str, Any]],
) -> InlineKeyboardMarkup:
    """
    Build pagination keyboard for search results.

    Each listing gets: [🔗 Link] [💾 Zapisz]
    Bottom nav row: [◀️] [1/N] [▶️]
    """
    builder = InlineKeyboardBuilder()

    # Per-listing action buttons
    for idx, listing in enumerate(results):
        listing_id = listing.get("id", str(idx))
        url = listing.get("url", "")
        row_buttons = []

        # Link button (URL button if we have a URL, otherwise callback)
        if url:
            row_buttons.append(
                InlineKeyboardButton(text="🔗 Link", url=url)
            )
        else:
            row_buttons.append(
                InlineKeyboardButton(
                    text="🔗 Szczegóły",
                    callback_data=f"listing:detail:{listing_id}",
                )
            )

        # Save button
        row_buttons.append(
            InlineKeyboardButton(
                text="💾 Zapisz",
                callback_data=f"listing:save:{listing_id}",
            )
        )
        builder.row(*row_buttons)

    # Navigation row
    nav_buttons: List[InlineKeyboardButton] = []

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"page:{page - 1}",
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
                text="▶️",
                callback_data=f"page:{page + 1}",
            )
        )

    builder.row(*nav_buttons)
    return builder.as_markup()


def build_listing_detail_keyboard(listing_id: str, url: str = "") -> InlineKeyboardMarkup:
    """Build keyboard for single listing detail view."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💾 Zapisz", callback_data=f"listing:save:{listing_id}"),
    )
    if url:
        builder.row(
            InlineKeyboardButton(text="🔗 Otwórz ogłoszenie", url=url),
        )
    builder.row(
        InlineKeyboardButton(text="◀️ Powrót do wyników", callback_data="page:0"),
    )
    return builder.as_markup()


# --- Filters ---

def build_voivodeship_keyboard(
    voivodeships: Dict[str, str],
) -> InlineKeyboardMarkup:
    """
    Build voivodeship selection keyboard (4x4 grid).

    16 voivodeships arranged 4 per row.
    """
    builder = InlineKeyboardBuilder()

    for code, name in voivodeships.items():
        # Truncate long names for button display
        display = name[:12].capitalize()
        builder.button(
            text=display,
            callback_data=f"voiv:{code}:{name}",
        )

    # Skip button
    builder.button(text="⏭️ Pomiń (cała Polska)", callback_data="filter_act:skip")

    # 4 columns for voivodeships, then 1 for skip button
    builder.adjust(4, 4, 4, 4, 1)
    return builder.as_markup()


def build_radius_keyboard() -> InlineKeyboardMarkup:
    """Build radius selection keyboard: 10/25/50/100 km."""
    builder = InlineKeyboardBuilder()

    for km in [10, 25, 50, 100]:
        builder.button(text=f"{km} km", callback_data=f"radius:{km}")

    builder.button(text="⏭️ Pomiń", callback_data="radius:skip")
    builder.adjust(4, 1)
    return builder.as_markup()


def build_filter_summary_keyboard() -> InlineKeyboardMarkup:
    """Keyboard after filter configuration."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Szukaj z filtrami", callback_data="search_with_filters"),
        InlineKeyboardButton(text="🗑️ Resetuj filtry", callback_data="filter_act:reset"),
    )
    return builder.as_markup()


# --- Saved listings ---

def build_saved_keyboard(
    listings: List[Dict[str, Any]],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Build keyboard for saved listings view with pagination and delete buttons."""
    builder = InlineKeyboardBuilder()
    page_size = 5
    total_pages = max(1, (len(listings) + page_size - 1) // page_size)

    # Delete button for each listing on current page
    start = page * page_size
    end = start + page_size
    for listing in listings[start:end]:
        lid = listing.get("id", "")
        title_short = listing.get("title", "?")[:20]
        builder.row(
            InlineKeyboardButton(text=f"🗑️ Usuń: {title_short}", callback_data=f"saved_del:{lid}"),
        )

    # Navigation
    nav_buttons: List[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"saved_page:{page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"saved_page:{page + 1}")
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


# --- Settings ---

def build_settings_keyboard(data: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Build settings panel keyboard."""
    builder = InlineKeyboardBuilder()

    # Notification toggle
    notif_enabled = data.get("notifications_enabled", True)
    notif_text = "🔔 Wyłącz powiadomienia" if notif_enabled else "🔕 Włącz powiadomienia"
    builder.row(
        InlineKeyboardButton(
            text=notif_text,
            callback_data="settings:toggle_notifications::",
        )
    )

    # Portal toggles
    portals = ["otodom", "olx", "gratka", "morizon"]
    disabled = data.get("disabled_portals", [])

    for portal in portals:
        status = "❌" if portal in disabled else "✅"
        builder.button(
            text=f"{status} {portal}",
            callback_data=f"settings:toggle_portal:{portal}:",
        )
    builder.adjust(2)

    builder.row(
        InlineKeyboardButton(text="🔄 Reset ustawień", callback_data="settings:reset::")
    )

    return builder.as_markup()
