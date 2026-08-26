"""
Udziały Bot — Main entry point.

Sets up the aiogram Bot + Dispatcher, registers all routers, configures middleware,
initializes DB on startup, closes on shutdown, and runs polling.

Usage:
    cd /home/ubuntu/udzialy-bot && .venv/bin/python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import signal
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings, PROJECT_ROOT
from bot.middlewares import setup_middlewares
from bot.routers import register_routers


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging based on settings."""
    settings = get_settings()

    # Ensure log directory exists
    log_path = PROJECT_ROOT / settings.logging.file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.logging.level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.handlers.RotatingFileHandler(
                log_path, encoding="utf-8", maxBytes=5*1024*1024, backupCount=3
            ),
        ],
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


async def on_startup(bot: Bot) -> None:
    """Actions to perform on bot startup — init DB, notify owner."""
    settings = get_settings()
    logger.info("Bot starting up...")

    # Ensure data directory exists
    db_path = PROJECT_ROOT / settings.database.path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize database
    try:
        from storage.database import DatabaseManager
        db = DatabaseManager(str(db_path))
        await db.initialize()
        await db.close()
        logger.info(f"Database initialized at: {db_path}")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")

    # Notify owner that bot is up
    if settings.owner_id and settings.owner_id != 0:
        try:
            await bot.send_message(
                settings.owner_id,
                "🟢 Bot uruchomiony i gotowy do pracy."
            )
        except Exception as e:
            logger.warning(f"Could not notify owner: {e}")


async def on_shutdown(bot: Bot) -> None:
    """Actions to perform on bot shutdown — close DB, notify owner."""
    settings = get_settings()
    logger.info("Bot shutting down...")

    # Close database connections
    try:
        from storage.database import DatabaseManager
        db_path = PROJECT_ROOT / settings.database.path
        db = DatabaseManager(str(db_path))
        await db.close()
    except Exception:
        pass

    # Notify owner
    if settings.owner_id and settings.owner_id != 0:
        try:
            await bot.send_message(
                settings.owner_id,
                "🔴 Bot zatrzymany."
            )
        except Exception:
            pass


async def run_bot() -> None:
    """Initialize and run the bot with polling."""
    settings = get_settings()

    # Validate token
    if settings.telegram_token in ("YOUR_BOT_TOKEN_HERE", ""):
        logger.error(
            "❌ Bot token not configured!\n"
            "   Edit config.yaml and set telegram.token to your BotFather token."
        )
        sys.exit(1)

    # Create bot instance
    bot = Bot(
        token=settings.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Create dispatcher with in-memory FSM storage
    dp = Dispatcher(storage=MemoryStorage())

    # Register startup/shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Setup middlewares (throttle)
    setup_middlewares(dp)

    # Register all routers
    register_routers(dp)

    logger.info("Starting polling...")
    logger.info("Tip: Keep this window open. Bot stops when you close it.")

    # Check Tor connectivity (non-blocking)
    import socket
    _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _sock.settimeout(2)
    if _sock.connect_ex(("127.0.0.1", 9050)) == 0:
        logger.info("✓ Tor connected (port 9050)")
    else:
        logger.warning("⚠ Tor not running — scrapers will use direct connection (some portals may block)")
    _sock.close()
    try:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        if "Unauthorized" in str(e) or "401" in str(e):
            logger.error("❌ Token odrzucony! Sprawdź token w config lub uruchom: udzialy setup")
        else:
            logger.error(f"❌ Bot crashed: {e}")
            raise
    finally:
        await bot.session.close()


def main() -> None:
    """Entry point for the bot."""
    # Add project root to path so storage/scraper/geo modules are importable
    project_root_str = str(PROJECT_ROOT)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    setup_logging()
    logger.info("=" * 50)
    logger.info("Udziały Bot v0.1.0")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info("=" * 50)

    # Handle graceful shutdown on Windows
    if sys.platform == "win32":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    main()
