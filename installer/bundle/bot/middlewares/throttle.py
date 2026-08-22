"""
Anti-flood (throttle) middleware — prevents spam from rapid repeated messages.

Uses a simple per-user time-based rate limiter stored in memory.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject


logger = logging.getLogger(__name__)


class ThrottleMiddleware(BaseMiddleware):
    """
    Rate-limiting middleware for aiogram 3.x.

    Drops messages/callbacks from users who exceed the rate limit.
    Uses a simple sliding window approach per user.

    Args:
        rate_limit: Minimum seconds between allowed requests per user.
    """

    def __init__(self, rate_limit: float = 1.0) -> None:
        self.rate_limit = rate_limit
        self._user_last_request: Dict[int, float] = {}
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process an incoming event through the throttle."""
        user_id = self._extract_user_id(event)
        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()
        last_request = self._user_last_request.get(user_id, 0.0)
        elapsed = now - last_request

        if elapsed < self.rate_limit:
            # Rate limited — silently drop
            logger.debug(
                f"Throttled user {user_id}: {elapsed:.2f}s < {self.rate_limit}s limit"
            )
            # For callback queries, still answer to prevent loading indicator
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Zbyt szybko! Poczekaj chwilę...", show_alert=False)
            return None

        # Allow through — update timestamp
        self._user_last_request[user_id] = now
        return await handler(event, data)

    @staticmethod
    def _extract_user_id(event: TelegramObject) -> int | None:
        """Extract user ID from various event types."""
        if isinstance(event, Message):
            return event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            return event.from_user.id if event.from_user else None
        return None

    def cleanup_old_entries(self, max_age: float = 3600.0) -> None:
        """Remove stale entries older than max_age seconds."""
        now = time.monotonic()
        self._user_last_request = {
            uid: ts
            for uid, ts in self._user_last_request.items()
            if now - ts < max_age
        }
