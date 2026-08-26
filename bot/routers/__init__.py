"""
Router registration — collects all routers into the dispatcher.
"""

from __future__ import annotations

from aiogram import Dispatcher

from bot.routers.search import router as search_router
from bot.routers.filters import router as filters_router
from bot.routers.results import router as results_router
from bot.routers.saved import router as saved_router
from bot.routers.settings import router as settings_router
from bot.routers.ai_chat import router as ai_chat_router


def register_routers(dp: Dispatcher) -> None:
    """Register all routers with the dispatcher.

    Order matters — first registered gets priority for overlapping filters.
    AI chat is LAST — catch-all for unmatched text messages.
    """
    dp.include_router(search_router)
    dp.include_router(filters_router)
    dp.include_router(results_router)
    dp.include_router(saved_router)
    dp.include_router(settings_router)
    dp.include_router(ai_chat_router)  # Must be last (catch-all)

    # Catch-all for non-text (photos, stickers, voice)
    from aiogram import F as _F
    from aiogram.types import Message as _Msg

    @dp.message(~_F.text)
    async def _non_text_handler(message: _Msg) -> None:
        await message.answer("💬 Wysyłaj mi tekst — zdjęcia i pliki nie obsługuję.")
