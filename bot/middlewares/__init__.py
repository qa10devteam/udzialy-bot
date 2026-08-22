"""
Middlewares package — setup and registration.
"""

from __future__ import annotations

from aiogram import Dispatcher

from bot.middlewares.throttle import ThrottleMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    """Register all middlewares with the dispatcher."""
    # Anti-flood middleware on message updates
    dp.message.middleware(ThrottleMiddleware(rate_limit=1.0))
    dp.callback_query.middleware(ThrottleMiddleware(rate_limit=0.5))
