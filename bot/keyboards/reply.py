"""
Reply keyboard builders — persistent main menu keyboard.
"""

from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Build the main menu reply keyboard.

    Shown persistently at the bottom of the chat.
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="🔍 Szukaj"),
        KeyboardButton(text="🗺️ Filtry"),
    )
    builder.row(
        KeyboardButton(text="💾 Zapisane"),
        KeyboardButton(text="⚙️ Ustawienia"),
    )

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Wybierz akcję lub wpisz komendę...",
    )


def confirm_keyboard() -> ReplyKeyboardMarkup:
    """Build a simple Yes/No confirmation keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Tak"),
        KeyboardButton(text="❌ Nie"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
