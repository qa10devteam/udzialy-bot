"""
FSM-based filter configuration — voivodeship, city, radius, price range.

States: FilterStates (voivodeship → city → radius → price_min → price_max)
- 16 voivodeships as inline buttons (4x4 grid)
- City as text input with fuzzy match via geo/cities.py
- Radius as inline buttons (10/25/50/100km)
- Price range as text input
- Save to SQLite via queries.create_filter()
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import get_settings
from bot.keyboards.inline import (
    build_voivodeship_keyboard,
    build_radius_keyboard,
    build_filter_summary_keyboard,
)
from bot.keyboards.reply import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="filters")


# --- FSM States ---

class FilterStates(StatesGroup):
    """States for filter configuration flow."""
    voivodeship = State()
    city = State()
    radius = State()
    price_min = State()
    price_max = State()


# --- Constants ---

VOIVODESHIPS: Dict[str, str] = {
    "DS": "dolnośląskie",
    "KP": "kujawsko-pomorskie",
    "LU": "lubelskie",
    "LB": "lubuskie",
    "LD": "łódzkie",
    "MA": "małopolskie",
    "MZ": "mazowieckie",
    "OP": "opolskie",
    "PK": "podkarpackie",
    "PD": "podlaskie",
    "PM": "pomorskie",
    "SL": "śląskie",
    "SK": "świętokrzyskie",
    "WM": "warmińsko-mazurskie",
    "WP": "wielkopolskie",
    "ZP": "zachodniopomorskie",
}


def _is_owner(user_id: int | None) -> bool:
    """Check if user is the bot owner."""
    settings = get_settings()
    if settings.owner_id == 0:
        return True
    return user_id == settings.owner_id


# --- Entry points ---

@router.message(Command("filters"))
@router.message(F.text == "⚙️ Filtry")
async def cmd_filters(message: Message, state: FSMContext) -> None:
    """Start filter configuration flow."""
    if not message.from_user or not _is_owner(message.from_user.id):
        return

    await state.set_state(FilterStates.voivodeship)
    await message.answer(
        "🗺️ <b>Konfiguracja filtrów</b>\n\n"
        "Krok 1/5: Wybierz województwo\n"
        "(lub pomiń, żeby szukać w całej Polsce)",
        reply_markup=build_voivodeship_keyboard(VOIVODESHIPS),
    )


# --- Step 1: Voivodeship ---

@router.callback_query(FilterStates.voivodeship, F.data.startswith("voiv:"))
async def handle_voivodeship_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle voivodeship selection from inline keyboard."""
    await callback.answer()

    parts = callback.data.split(":", 2)  # type: ignore[union-attr]
    code = parts[1]
    name = parts[2] if len(parts) > 2 else VOIVODESHIPS.get(code, code)

    await state.update_data(filter_voivodeship=name, filter_voivodeship_code=code)
    await state.set_state(FilterStates.city)

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Województwo: <b>{name}</b>\n\n"
        "Krok 2/5: Wpisz nazwę miasta\n"
        "(lub wyślij /skip żeby pominąć)",
    )


@router.callback_query(FilterStates.voivodeship, F.data == "filter_act:skip")
async def handle_voivodeship_skip(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip voivodeship selection."""
    await callback.answer()
    await state.update_data(filter_voivodeship=None, filter_voivodeship_code=None)
    await state.set_state(FilterStates.city)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "⏭️ Pominięto województwo — szukam w całej Polsce\n\n"
        "Krok 2/5: Wpisz nazwę miasta\n"
        "(lub wyślij /skip żeby pominąć)",
    )


# --- Step 2: City (text input with fuzzy match) ---

@router.message(FilterStates.city, Command("skip"))
async def handle_city_skip(message: Message, state: FSMContext) -> None:
    """Skip city entry."""
    await state.update_data(filter_city=None)
    await state.set_state(FilterStates.radius)
    await message.answer(
        "⏭️ Pominięto miasto\n\n"
        "Krok 3/5: Wybierz promień wyszukiwania:",
        reply_markup=build_radius_keyboard(),
    )


@router.message(FilterStates.city, F.text)
async def handle_city_input(message: Message, state: FSMContext) -> None:
    """Handle city name input with fuzzy matching."""
    city_query = message.text.strip() if message.text else ""
    if not city_query or city_query.startswith("/"):
        return

    # Try fuzzy matching via geo module
    matched_city = city_query
    try:
        from geo.cities import search_city
        matches = search_city(city_query)
        if matches:
            # Use best match (first result, sorted by population)
            matched_city = matches[0]["name"]
            if len(matches) > 1:
                # Show alternatives
                alternatives = ", ".join(m["name"] for m in matches[:5])
                await message.answer(
                    f"🔍 Znaleziono: <b>{matched_city}</b>\n"
                    f"Inne opcje: {alternatives}\n\n"
                    f"Używam: <b>{matched_city}</b>",
                )
    except ImportError:
        logger.warning("geo.cities module not available, using raw input")

    await state.update_data(filter_city=matched_city)
    await state.set_state(FilterStates.radius)
    await message.answer(
        f"✅ Miasto: <b>{matched_city}</b>\n\n"
        "Krok 3/5: Wybierz promień wyszukiwania:",
        reply_markup=build_radius_keyboard(),
    )


# --- Step 3: Radius (inline buttons) ---

@router.callback_query(FilterStates.radius, F.data.startswith("radius:"))
async def handle_radius_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle radius selection from inline buttons."""
    await callback.answer()

    value = callback.data.split(":")[1]  # type: ignore[union-attr]

    if value == "skip":
        await state.update_data(filter_radius=None)
        radius_text = "⏭️ Pominięto promień"
    else:
        radius = int(value)
        await state.update_data(filter_radius=radius)
        radius_text = f"✅ Promień: <b>{radius} km</b>"

    await state.set_state(FilterStates.price_min)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"{radius_text}\n\n"
        "Krok 4/5: Podaj minimalną cenę (PLN)\n"
        "(np. 50000, lub /skip żeby pominąć)",
    )


# --- Step 4: Price min ---

@router.message(FilterStates.price_min, Command("skip"))
async def handle_price_min_skip(message: Message, state: FSMContext) -> None:
    """Skip min price entry."""
    await state.update_data(filter_price_min=None)
    await state.set_state(FilterStates.price_max)
    await message.answer(
        "⏭️ Pominięto cenę minimalną\n\n"
        "Krok 5/5: Podaj maksymalną cenę (PLN)\n"
        "(np. 200000, lub /skip żeby pominąć)",
    )


@router.message(FilterStates.price_min, F.text)
async def handle_price_min_input(message: Message, state: FSMContext) -> None:
    """Handle min price input."""
    text = message.text.strip() if message.text else ""
    if text.startswith("/"):
        return

    text = text.replace(" ", "").replace(",", "").replace(".", "")
    try:
        price = int(text)
        if price < 0:
            raise ValueError("Price must be non-negative")
    except (ValueError, TypeError):
        await message.answer("❌ Podaj poprawną kwotę (np. 50000)")
        return

    await state.update_data(filter_price_min=price)
    await state.set_state(FilterStates.price_max)
    await message.answer(
        f"✅ Cena minimalna: <b>{price:,.0f} PLN</b>\n\n"
        "Krok 5/5: Podaj maksymalną cenę (PLN)\n"
        "(np. 200000, lub /skip żeby pominąć)",
    )


# --- Step 5: Price max ---

@router.message(FilterStates.price_max, Command("skip"))
async def handle_price_max_skip(message: Message, state: FSMContext) -> None:
    """Skip max price entry."""
    await state.update_data(filter_price_max=None)
    await _finalize_filters(message, state)


@router.message(FilterStates.price_max, F.text)
async def handle_price_max_input(message: Message, state: FSMContext) -> None:
    """Handle max price input."""
    text = message.text.strip() if message.text else ""
    if text.startswith("/"):
        return

    text = text.replace(" ", "").replace(",", "").replace(".", "")
    try:
        price = int(text)
        if price <= 0:
            raise ValueError("Price must be positive")
    except (ValueError, TypeError):
        await message.answer("❌ Podaj poprawną kwotę (np. 200000)")
        return

    await state.update_data(filter_price_max=price)
    await _finalize_filters(message, state)


# --- Filter reset ---

@router.callback_query(F.data == "filter_act:reset")
async def handle_filter_reset(callback: CallbackQuery, state: FSMContext) -> None:
    """Reset all filters."""
    await callback.answer("🗑️ Filtry wyczyszczone")
    await state.update_data(
        filter_voivodeship=None,
        filter_voivodeship_code=None,
        filter_city=None,
        filter_radius=None,
        filter_price_min=None,
        filter_price_max=None,
    )
    await state.set_state(None)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🗑️ Wszystkie filtry zostały wyczyszczone.\n"
        "Użyj /search żeby szukać bez filtrów\n"
        "lub /filters żeby ustawić nowe.",
    )


# --- Finalize ---

async def _finalize_filters(message: Message, state: FSMContext) -> None:
    """Show filter summary and save to DB."""
    data: Dict[str, Any] = await state.get_data()
    await state.set_state(None)

    voiv = data.get("filter_voivodeship")
    city = data.get("filter_city")
    radius = data.get("filter_radius")
    price_min = data.get("filter_price_min")
    price_max = data.get("filter_price_max")

    # Try to save filter to database
    try:
        from storage.database import DatabaseManager

        settings = get_settings()
        db = DatabaseManager(settings.database.path)
        await db.initialize()

        await db.execute(
            """
            INSERT INTO user_filters (name, voivodeship, city, radius_km, min_price, max_price, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (
                f"Filtr {city or voiv or 'ogólny'}",
                voiv,
                city,
                radius,
                price_min,
                price_max,
            ),
        )
        await db.commit()
        await db.close()
        logger.info(f"Filter saved to DB: voiv={voiv}, city={city}")
    except Exception as e:
        logger.warning(f"Could not save filter to DB: {e}")

    # Show summary
    lines: List[str] = ["✅ <b>Filtry ustawione:</b>\n"]
    lines.append(f"📍 Województwo: {voiv or 'cała Polska'}")
    lines.append(f"🏙️ Miasto: {city or '—'}")
    lines.append(f"📐 Promień: {f'{radius} km' if radius else '—'}")
    lines.append(f"💰 Cena min: {f'{price_min:,.0f} PLN' if price_min else '—'}")
    lines.append(f"💰 Cena max: {f'{price_max:,.0f} PLN' if price_max else '—'}")
    lines.append("\nUżyj 🔍 <b>Szukaj</b> aby wyszukać z tymi filtrami.")

    await message.answer(
        "\n".join(lines),
        reply_markup=build_filter_summary_keyboard(),
    )
