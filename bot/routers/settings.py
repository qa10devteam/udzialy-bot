"""
User settings/preferences — notification toggle, default filters, portal prefs.
"""

from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext

from bot.keyboards.inline import build_settings_keyboard


logger = logging.getLogger(__name__)

router = Router(name="settings")


# --- Callback Data ---

class SettingsCallback(CallbackData, prefix="settings"):
    """Callback for settings actions."""
    action: str  # "toggle_notifications", "toggle_portal", "reset"
    portal: str = ""
    value: str = ""


# --- Handlers ---

@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    """Show user settings panel."""
    data = await state.get_data()
    text = _format_settings(data)
    await message.answer(text, reply_markup=build_settings_keyboard(data))


@router.callback_query(SettingsCallback.filter(F.action == "toggle_notifications"))
async def handle_toggle_notifications(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext,
) -> None:
    """Toggle notification preference."""
    data = await state.get_data()
    current = data.get("notifications_enabled", True)
    await state.update_data(notifications_enabled=not current)

    status = "wyłączone" if current else "włączone"
    await callback.answer(f"🔔 Powiadomienia {status}")

    # Refresh settings view
    data = await state.get_data()
    await callback.message.edit_text(  # type: ignore[union-attr]
        _format_settings(data),
        reply_markup=build_settings_keyboard(data),
    )


@router.callback_query(SettingsCallback.filter(F.action == "toggle_portal"))
async def handle_toggle_portal(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext,
) -> None:
    """Toggle a specific portal on/off for this user."""
    portal = callback_data.portal
    data = await state.get_data()

    disabled_portals: list[str] = data.get("disabled_portals", [])
    if portal in disabled_portals:
        disabled_portals.remove(portal)
        await callback.answer(f"✅ {portal} włączony")
    else:
        disabled_portals.append(portal)
        await callback.answer(f"❌ {portal} wyłączony")

    await state.update_data(disabled_portals=disabled_portals)

    # Refresh settings view
    data = await state.get_data()
    await callback.message.edit_text(  # type: ignore[union-attr]
        _format_settings(data),
        reply_markup=build_settings_keyboard(data),
    )


@router.callback_query(SettingsCallback.filter(F.action == "reset"))
async def handle_settings_reset(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Reset all user settings to defaults."""
    await state.update_data(
        notifications_enabled=True,
        disabled_portals=[],
    )
    await callback.answer("🔄 Ustawienia zresetowane")

    data = await state.get_data()
    await callback.message.edit_text(  # type: ignore[union-attr]
        _format_settings(data),
        reply_markup=build_settings_keyboard(data),
    )


@router.message(F.text == "⚙️ Ustawienia")
async def btn_settings(message: Message, state: FSMContext) -> None:
    """Handle 'Settings' button from reply keyboard."""
    await cmd_settings(message, state)


# --- Formatters ---

def _format_settings(data: dict) -> str:
    """Format settings panel."""
    notif = "✅ włączone" if data.get("notifications_enabled", True) else "❌ wyłączone"
    disabled = data.get("disabled_portals", [])

    text = (
        "⚙️ <b>Ustawienia</b>\n\n"
        f"🔔 Powiadomienia: {notif}\n"
        f"🚫 Wyłączone portale: {len(disabled)}\n\n"
        "Użyj przycisków poniżej aby zmienić ustawienia."
    )
    return text
