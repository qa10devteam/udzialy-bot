"""
FSM-based filter configuration — voivodeship, city, radius, price.

Guides the user through a step-by-step filter setup using Finite State Machine.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.callback_data import CallbackData

from bot.keyboards.inline import build_voivodeship_keyboard, build_filter_summary_keyboard


logger = logging.getLogger(__name__)

router = Router(name="filters")


# --- FSM States ---

class FilterStates(StatesGroup):
    """States for filter configuration flow."""
    choosing_voivodeship = State()
    entering_city = State()
    entering_radius = State()
    entering_price_min = State()
    entering_price_max = State()
    confirming = State()


# --- Callback Data ---

class VoivodeshipCallback(CallbackData, prefix="voiv"):
    """Callback for voivodeship selection."""
    code: str
    name: str


class FilterActionCallback(CallbackData, prefix="filter_act"):
    """Callback for filter actions."""
    action: str  # "reset", "skip", "confirm"


# --- Constants ---

VOIVODESHIPS: dict[str, str] = {
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


# --- Handlers ---

@router.message(Command("filters"))
async def cmd_filters(message: Message, state: FSMContext) -> None:
    """Start filter configuration flow."""
    await state.set_state(FilterStates.choosing_voivodeship)
    await message.answer(
        "🗺️ <b>Konfiguracja filtrów</b>\n\n"
        "Krok 1/4: Wybierz województwo\n"
        "(lub pomiń, żeby szukać w całej Polsce)",
        reply_markup=build_voivodeship_keyboard(VOIVODESHIPS),
    )


@router.callback_query(
    FilterStates.choosing_voivodeship,
    VoivodeshipCallback.filter(),
)
async def handle_voivodeship_choice(
    callback: CallbackQuery,
    callback_data: VoivodeshipCallback,
    state: FSMContext,
) -> None:
    """Handle voivodeship selection."""
    await callback.answer()
    await state.update_data(
        filter_voivodeship=callback_data.name,
        filter_voivodeship_code=callback_data.code,
    )
    await state.set_state(FilterStates.entering_city)

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Województwo: <b>{callback_data.name}</b>\n\n"
        "Krok 2/4: Wpisz nazwę miasta\n"
        "(lub wyślij /skip żeby pominąć)",
    )


@router.callback_query(
    FilterStates.choosing_voivodeship,
    FilterActionCallback.filter(F.action == "skip"),
)
async def handle_voivodeship_skip(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Skip voivodeship selection."""
    await callback.answer()
    await state.update_data(filter_voivodeship=None, filter_voivodeship_code=None)
    await state.set_state(FilterStates.entering_city)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "⏭️ Pominięto województwo — szukam w całej Polsce\n\n"
        "Krok 2/4: Wpisz nazwę miasta\n"
        "(lub wyślij /skip żeby pominąć)",
    )


@router.message(FilterStates.entering_city, Command("skip"))
async def handle_city_skip(message: Message, state: FSMContext) -> None:
    """Skip city entry."""
    await state.update_data(filter_city=None)
    await state.set_state(FilterStates.entering_radius)
    await message.answer(
        "⏭️ Pominięto miasto\n\n"
        "Krok 3/4: Podaj promień wyszukiwania w km\n"
        "(np. 50, lub /skip żeby pominąć)",
    )


@router.message(FilterStates.entering_city, F.text)
async def handle_city_input(message: Message, state: FSMContext) -> None:
    """Handle city name input."""
    city = message.text.strip() if message.text else ""
    if not city or city.startswith("/"):
        return

    await state.update_data(filter_city=city)
    await state.set_state(FilterStates.entering_radius)
    await message.answer(
        f"✅ Miasto: <b>{city}</b>\n\n"
        "Krok 3/4: Podaj promień wyszukiwania w km\n"
        "(np. 50, lub /skip żeby pominąć)",
    )


@router.message(FilterStates.entering_radius, Command("skip"))
async def handle_radius_skip(message: Message, state: FSMContext) -> None:
    """Skip radius entry."""
    await state.update_data(filter_radius=None)
    await state.set_state(FilterStates.entering_price_max)
    await message.answer(
        "⏭️ Pominięto promień\n\n"
        "Krok 4/4: Podaj maksymalną cenę (PLN)\n"
        "(np. 100000, lub /skip żeby pominąć)",
    )


@router.message(FilterStates.entering_radius, F.text)
async def handle_radius_input(message: Message, state: FSMContext) -> None:
    """Handle radius input."""
    text = message.text.strip() if message.text else ""
    try:
        radius = int(text)
        if radius <= 0 or radius > 500:
            raise ValueError("Radius out of range")
    except (ValueError, TypeError):
        await message.answer("❌ Podaj liczbę od 1 do 500 (km)")
        return

    await state.update_data(filter_radius=radius)
    await state.set_state(FilterStates.entering_price_max)
    await message.answer(
        f"✅ Promień: <b>{radius} km</b>\n\n"
        "Krok 4/4: Podaj maksymalną cenę (PLN)\n"
        "(np. 100000, lub /skip żeby pominąć)",
    )


@router.message(FilterStates.entering_price_max, Command("skip"))
async def handle_price_skip(message: Message, state: FSMContext) -> None:
    """Skip price entry."""
    await state.update_data(filter_price_max=None)
    await _show_filter_summary(message, state)


@router.message(FilterStates.entering_price_max, F.text)
async def handle_price_input(message: Message, state: FSMContext) -> None:
    """Handle max price input."""
    text = message.text.strip() if message.text else ""
    text = text.replace(" ", "").replace(",", "").replace(".", "")
    try:
        price = int(text)
        if price <= 0:
            raise ValueError("Price must be positive")
    except (ValueError, TypeError):
        await message.answer("❌ Podaj poprawną kwotę (np. 100000)")
        return

    await state.update_data(filter_price_max=price)
    await _show_filter_summary(message, state)


@router.callback_query(FilterActionCallback.filter(F.action == "reset"))
async def handle_filter_reset(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Reset all filters."""
    await callback.answer("🗑️ Filtry wyczyszczone")
    await state.update_data(
        filter_voivodeship=None,
        filter_voivodeship_code=None,
        filter_city=None,
        filter_radius=None,
        filter_price_max=None,
    )
    await state.set_state(None)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🗑️ Wszystkie filtry zostały wyczyszczone.\n"
        "Użyj /search żeby szukać bez filtrów\n"
        "lub /filters żeby ustawić nowe.",
    )


# --- Helpers ---

async def _show_filter_summary(message: Message, state: FSMContext) -> None:
    """Show filter summary after configuration."""
    data: dict[str, Any] = await state.get_data()
    await state.set_state(None)

    lines: list[str] = ["✅ <b>Filtry ustawione:</b>\n"]

    voiv = data.get("filter_voivodeship")
    city = data.get("filter_city")
    radius = data.get("filter_radius")
    price_max = data.get("filter_price_max")

    lines.append(f"📍 Województwo: {voiv or 'cała Polska'}")
    lines.append(f"🏙️ Miasto: {city or '—'}")
    lines.append(f"📐 Promień: {f'{radius} km' if radius else '—'}")
    lines.append(f"💰 Max cena: {f'{price_max:,.0f} PLN' if price_max else '—'}")
    lines.append("\nUżyj /search aby rozpocząć wyszukiwanie z tymi filtrami.")

    await message.answer(
        "\n".join(lines),
        reply_markup=build_filter_summary_keyboard(),
    )
