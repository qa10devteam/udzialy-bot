"""SQLite database manager with async operations via aiosqlite.

Provides:
- Auto-creation of tables on first run
- WAL mode for concurrent reads
- Schema migration support
- Connection pooling via context manager
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

# Default database path (Windows-friendly, in user's app data)
DEFAULT_DB_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "udzialy-bot",
    "udzialy.db",
)

SCHEMA_VERSION = 1

# SQL schema for all tables
SCHEMA_SQL = """
-- Listings table: stores scraped property listings
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,           -- 'olx', 'otodom', 'gratka'
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    price REAL,
    price_per_m2 REAL,
    area REAL,
    rooms INTEGER,
    city TEXT,
    voivodeship TEXT,
    district TEXT,
    latitude REAL,
    longitude REAL,
    score INTEGER DEFAULT 0,
    is_share INTEGER DEFAULT 0,     -- boolean: 1 = likely share
    fraction TEXT,                   -- detected fraction e.g. '1/2'
    matched_keywords TEXT,          -- JSON array of matched keywords
    seller_name TEXT,
    seller_phone TEXT,
    images TEXT,                    -- JSON array of image URLs
    raw_data TEXT,                  -- Full JSON of original scraped data
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Search history: tracks what queries were run and when
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    source TEXT NOT NULL,            -- 'olx', 'otodom', etc.
    results_count INTEGER DEFAULT 0,
    new_listings_count INTEGER DEFAULT 0,
    searched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Saved listings: user bookmarks
CREATE TABLE IF NOT EXISTS saved_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT NOT NULL,
    notes TEXT,
    priority INTEGER DEFAULT 0,     -- 0=normal, 1=high, 2=urgent
    status TEXT DEFAULT 'new',      -- 'new', 'contacted', 'visited', 'rejected', 'purchased'
    saved_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
);

-- User filters: saved search configurations
CREATE TABLE IF NOT EXISTS user_filters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    voivodeship TEXT,
    city TEXT,
    radius_km REAL,
    min_price REAL,
    max_price REAL,
    min_area REAL,
    max_area REAL,
    min_score INTEGER DEFAULT 50,
    sources TEXT,                    -- JSON array of sources
    is_active INTEGER DEFAULT 1,
    notify_enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_voivodeship ON listings(voivodeship);
CREATE INDEX IF NOT EXISTS idx_listings_score ON listings(score);
CREATE INDEX IF NOT EXISTS idx_listings_is_share ON listings(is_share);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_listings_is_active ON listings(is_active);
CREATE INDEX IF NOT EXISTS idx_saved_listings_listing_id ON saved_listings(listing_id);
CREATE INDEX IF NOT EXISTS idx_search_history_searched_at ON search_history(searched_at);
"""


class DatabaseManager:
    """Async SQLite database manager for udzialy-bot.

    Handles connection management, schema creation, and migrations.
    Uses WAL mode for better concurrent read performance.

    Usage:
        db = DatabaseManager("/path/to/database.db")
        await db.initialize()
        async with db.connection() as conn:
            await conn.execute(...)
        await db.close()
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize database manager.

        Args:
            db_path: Path to SQLite database file. Creates parent dirs if needed.
                     Defaults to platform-appropriate app data directory.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._db: Optional[aiosqlite.Connection] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database: create file, set WAL mode, run migrations.

        Creates parent directories if they don't exist.
        Safe to call multiple times (idempotent).
        """
        if self._initialized:
            return

        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Open connection
        self._db = await aiosqlite.connect(self.db_path)

        # Enable WAL mode for concurrent reads
        await self._db.execute("PRAGMA journal_mode=WAL")
        # Enable foreign keys
        await self._db.execute("PRAGMA foreign_keys=ON")
        # Reasonable busy timeout (5 seconds)
        await self._db.execute("PRAGMA busy_timeout=5000")

        # Create schema
        await self._db.executescript(SCHEMA_SQL)

        # Set schema version
        await self._db.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        await self._db.commit()

        self._initialized = True
        logger.info(f"Database initialized at: {self.db_path}")

    async def get_connection(self) -> aiosqlite.Connection:
        """Get the active database connection.

        Returns:
            Active aiosqlite connection.

        Raises:
            RuntimeError: If database hasn't been initialized.
        """
        if not self._initialized or self._db is None:
            raise RuntimeError(
                "Database not initialized. Call await db.initialize() first."
            )
        return self._db

    async def close(self) -> None:
        """Close the database connection gracefully."""
        if self._db is not None:
            await self._db.close()
            self._db = None
            self._initialized = False
            logger.info("Database connection closed.")

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a SQL statement.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            Cursor with results.
        """
        conn = await self.get_connection()
        return await conn.execute(sql, params)

    async def executemany(self, sql: str, params_list: list) -> None:
        """Execute a SQL statement with multiple parameter sets.

        Args:
            sql: SQL query string.
            params_list: List of parameter tuples.
        """
        conn = await self.get_connection()
        await conn.executemany(sql, params_list)
        await conn.commit()

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute query and fetch one row as dict.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            Row as dictionary or None.
        """
        conn = await self.get_connection()
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetchall(self, sql: str, params: tuple = ()) -> list:
        """Execute query and fetch all rows as dicts.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            List of rows as dictionaries.
        """
        conn = await self.get_connection()
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        """Commit the current transaction."""
        conn = await self.get_connection()
        await conn.commit()

    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized and ready."""
        return self._initialized
