"""
Udziały Bot — Main entry point.

Sets up the aiogram Dispatcher, registers routers, configures middleware,
and starts polling.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.middlewares import setup_middlewares
from bot.routers import register_routers


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging based on settings."""
    settings = get_settings()

    # Ensure log directory exists
    log_path = Path(settings.logging.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.logging.level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)


async def on_startup(bot: Bot) -> None:
    """Actions to perform on bot startup."""
    settings = get_settings()
    logger.info("Bot starting up...")

    # Ensure data directory exists
    Path(settings.database.path).parent.mkdir(parents=True, exist_ok=True)

    # Notify owner
    if settings.telegram.owner_id:
        try:
            await bot.send_message(
                settings.telegram.owner_id,
                "🟢 Bot uruchomiony i gotowy do pracy."
            )
        except Exception as e:
            logger.warning(f"Could not notify owner: {e}")


async def on_shutdown(bot: Bot) -> None:
    """Actions to perform on bot shutdown."""
    settings = get_settings()
    logger.info("Bot shutting down...")

    if settings.telegram.owner_id:
        try:
            await bot.send_message(
                settings.telegram.owner_id,
                "🔴 Bot zatrzymany."
            )
        except Exception:
            pass


async def run_bot() -> None:
    """Initialize and run the bot."""
    settings = get_settings()

    # Validate token
    if settings.telegram.token == "YOUR_BOT_TOKEN_HERE" or not settings.telegram.token:
        logger.error("Bot token not configured! Edit config.yaml first.")
        sys.exit(1)

    # Create bot instance
    bot = Bot(
        token=settings.telegram.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Create dispatcher with FSM storage
    dp = Dispatcher(storage=MemoryStorage())

    # Register startup/shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Setup middlewares
    setup_middlewares(dp)

    # Register all routers
    register_routers(dp)

    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


def main() -> None:
    """Entry point for the bot."""
    setup_logging()
    logger.info("=" * 50)
    logger.info("Udziały Bot v0.1.0")
    logger.info("=" * 50)

    # Handle graceful shutdown on Windows
    if sys.platform == "win32":
        # Windows needs special signal handling
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    main()
