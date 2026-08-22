"""CRUD async query functions for the storage layer.

All functions operate on the DatabaseManager instance and use
Pydantic models for input/output validation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from storage.database import DatabaseManager
from storage.models import Listing, SavedListing, UserFilter, SearchResult

logger = logging.getLogger(__name__)


async def upsert_listing(db: DatabaseManager, listing: Listing) -> bool:
    """Insert or update a listing in the database.

    If a listing with the same ID exists, updates it and refreshes last_seen_at.
    Otherwise inserts a new record.

    Args:
        db: Database manager instance.
        listing: Listing model to upsert.

    Returns:
        True if a new record was inserted, False if existing was updated.
    """
    now = datetime.utcnow().isoformat()

    # Check if exists
    existing = await db.fetchone(
        "SELECT id FROM listings WHERE id = ?", (listing.id,)
    )

    if existing:
        # Update existing
        await db.execute(
            """
            UPDATE listings SET
                title = ?, description = ?, price = ?, price_per_m2 = ?,
                area = ?, rooms = ?, city = ?, voivodeship = ?, district = ?,
                latitude = ?, longitude = ?, score = ?, is_share = ?,
                fraction = ?, matched_keywords = ?, seller_name = ?,
                seller_phone = ?, images = ?, raw_data = ?,
                last_seen_at = ?, is_active = 1, updated_at = ?
            WHERE id = ?
            """,
            (
                listing.title,
                listing.description,
                listing.price,
                listing.price_per_m2,
                listing.area,
                listing.rooms,
                listing.city,
                listing.voivodeship,
                listing.district,
                listing.latitude,
                listing.longitude,
                listing.score,
                1 if listing.is_share else 0,
                listing.fraction,
                json.dumps(listing.matched_keywords, ensure_ascii=False),
                listing.seller_name,
                listing.seller_phone,
                json.dumps(listing.images, ensure_ascii=False),
                listing.raw_data,
                now,
                now,
                listing.id,
            ),
        )
        await db.commit()
        logger.debug(f"Updated listing: {listing.id}")
        return False
    else:
        # Insert new
        await db.execute(
            """
            INSERT INTO listings (
                id, source, url, title, description, price, price_per_m2,
                area, rooms, city, voivodeship, district, latitude, longitude,
                score, is_share, fraction, matched_keywords, seller_name,
                seller_phone, images, raw_data, first_seen_at, last_seen_at,
                is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                listing.id,
                listing.source,
                listing.url,
                listing.title,
                listing.description,
                listing.price,
                listing.price_per_m2,
                listing.area,
                listing.rooms,
                listing.city,
                listing.voivodeship,
                listing.district,
                listing.latitude,
                listing.longitude,
                listing.score,
                1 if listing.is_share else 0,
                listing.fraction,
                json.dumps(listing.matched_keywords, ensure_ascii=False),
                listing.seller_name,
                listing.seller_phone,
                json.dumps(listing.images, ensure_ascii=False),
                listing.raw_data,
                now,
                now,
                now,
                now,
            ),
        )
        await db.commit()
        logger.debug(f"Inserted new listing: {listing.id}")
        return True


async def get_listings(
    db: DatabaseManager,
    *,
    source: Optional[str] = None,
    city: Optional[str] = None,
    voivodeship: Optional[str] = None,
    min_score: Optional[int] = None,
    is_share: Optional[bool] = None,
    is_active: Optional[bool] = True,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    order_by: str = "score DESC",
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get listings with optional filters and pagination.

    Args:
        db: Database manager instance.
        source: Filter by portal source.
        city: Filter by city name.
        voivodeship: Filter by voivodeship.
        min_score: Minimum score threshold.
        is_share: Filter only likely shares (True) or non-shares (False).
        is_active: Filter active/inactive listings (None = all).
        min_price: Minimum price filter.
        max_price: Maximum price filter.
        order_by: SQL ORDER BY clause (default: score DESC).
        limit: Max results to return (default 50).
        offset: Pagination offset (default 0).

    Returns:
        List of listing dictionaries.
    """
    conditions: List[str] = []
    params: List[Any] = []

    if source:
        conditions.append("source = ?")
        params.append(source)
    if city:
        conditions.append("LOWER(city) = LOWER(?)")
        params.append(city)
    if voivodeship:
        conditions.append("LOWER(voivodeship) = LOWER(?)")
        params.append(voivodeship)
    if min_score is not None:
        conditions.append("score >= ?")
        params.append(min_score)
    if is_share is not None:
        conditions.append("is_share = ?")
        params.append(1 if is_share else 0)
    if is_active is not None:
        conditions.append("is_active = ?")
        params.append(1 if is_active else 0)
    if min_price is not None:
        conditions.append("price >= ?")
        params.append(min_price)
    if max_price is not None:
        conditions.append("price <= ?")
        params.append(max_price)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Sanitize order_by to prevent SQL injection
    allowed_orders = {
        "score DESC", "score ASC", "price DESC", "price ASC",
        "last_seen_at DESC", "last_seen_at ASC",
        "first_seen_at DESC", "first_seen_at ASC",
        "created_at DESC", "created_at ASC",
    }
    if order_by not in allowed_orders:
        order_by = "score DESC"

    sql = f"""
        SELECT * FROM listings
        {where_clause}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    return await db.fetchall(sql, tuple(params))


async def save_listing(
    db: DatabaseManager,
    listing_id: str,
    notes: Optional[str] = None,
    priority: int = 0,
) -> int:
    """Save/bookmark a listing for the user.

    Args:
        db: Database manager instance.
        listing_id: ID of the listing to save.
        notes: Optional user notes.
        priority: Priority level (0=normal, 1=high, 2=urgent).

    Returns:
        ID of the saved_listings record.

    Raises:
        ValueError: If listing_id doesn't exist.
    """
    # Verify listing exists
    existing = await db.fetchone(
        "SELECT id FROM listings WHERE id = ?", (listing_id,)
    )
    if not existing:
        raise ValueError(f"Listing '{listing_id}' not found in database.")

    # Check if already saved
    already_saved = await db.fetchone(
        "SELECT id FROM saved_listings WHERE listing_id = ?", (listing_id,)
    )
    if already_saved:
        # Update existing save
        await db.execute(
            """
            UPDATE saved_listings SET notes = ?, priority = ?, saved_at = datetime('now')
            WHERE listing_id = ?
            """,
            (notes, priority, listing_id),
        )
        await db.commit()
        return already_saved["id"]

    cursor = await db.execute(
        """
        INSERT INTO saved_listings (listing_id, notes, priority, saved_at)
        VALUES (?, ?, ?, datetime('now'))
        """,
        (listing_id, notes, priority),
    )
    await db.commit()
    return cursor.lastrowid


async def unsave_listing(db: DatabaseManager, listing_id: str) -> bool:
    """Remove a listing from saved/bookmarks.

    Args:
        db: Database manager instance.
        listing_id: ID of the listing to unsave.

    Returns:
        True if a record was deleted, False if not found.
    """
    cursor = await db.execute(
        "DELETE FROM saved_listings WHERE listing_id = ?", (listing_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_saved_listings(
    db: DatabaseManager,
    status: Optional[str] = None,
    priority: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Get all saved listings with their full listing data.

    Args:
        db: Database manager instance.
        status: Optional filter by status.
        priority: Optional filter by priority level.

    Returns:
        List of saved listings joined with listing data.
    """
    conditions: List[str] = []
    params: List[Any] = []

    if status:
        conditions.append("s.status = ?")
        params.append(status)
    if priority is not None:
        conditions.append("s.priority = ?")
        params.append(priority)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT s.*, l.title, l.url, l.price, l.city, l.voivodeship,
               l.score, l.fraction, l.source, l.area
        FROM saved_listings s
        JOIN listings l ON s.listing_id = l.id
        {where_clause}
        ORDER BY s.priority DESC, s.saved_at DESC
    """

    return await db.fetchall(sql, tuple(params))


async def create_filter(db: DatabaseManager, user_filter: UserFilter) -> int:
    """Create a new search filter.

    Args:
        db: Database manager instance.
        user_filter: UserFilter model with filter configuration.

    Returns:
        ID of the created filter.
    """
    now = datetime.utcnow().isoformat()

    cursor = await db.execute(
        """
        INSERT INTO user_filters (
            name, voivodeship, city, radius_km, min_price, max_price,
            min_area, max_area, min_score, sources, is_active,
            notify_enabled, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_filter.name,
            user_filter.voivodeship,
            user_filter.city,
            user_filter.radius_km,
            user_filter.min_price,
            user_filter.max_price,
            user_filter.min_area,
            user_filter.max_area,
            user_filter.min_score,
            json.dumps(user_filter.sources, ensure_ascii=False),
            1 if user_filter.is_active else 0,
            1 if user_filter.notify_enabled else 0,
            now,
            now,
        ),
    )
    await db.commit()
    logger.info(f"Created filter: {user_filter.name} (id={cursor.lastrowid})")
    return cursor.lastrowid


async def get_filters(
    db: DatabaseManager, active_only: bool = True
) -> List[Dict[str, Any]]:
    """Get all user filters.

    Args:
        db: Database manager instance.
        active_only: If True, return only active filters.

    Returns:
        List of filter dictionaries.
    """
    if active_only:
        return await db.fetchall(
            "SELECT * FROM user_filters WHERE is_active = 1 ORDER BY name"
        )
    return await db.fetchall("SELECT * FROM user_filters ORDER BY name")


async def search_history_add(
    db: DatabaseManager,
    query: str,
    source: str,
    results_count: int = 0,
    new_listings_count: int = 0,
) -> int:
    """Add a search execution record to history.

    Args:
        db: Database manager instance.
        query: Search query that was executed.
        source: Portal source (e.g., 'olx').
        results_count: Total results returned.
        new_listings_count: New (previously unseen) listings found.

    Returns:
        ID of the history record.
    """
    cursor = await db.execute(
        """
        INSERT INTO search_history (query, source, results_count, new_listings_count, searched_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (query, source, results_count, new_listings_count),
    )
    await db.commit()
    return cursor.lastrowid


async def get_search_history(
    db: DatabaseManager, limit: int = 20
) -> List[Dict[str, Any]]:
    """Get recent search history.

    Args:
        db: Database manager instance.
        limit: Max records to return.

    Returns:
        List of search history records, newest first.
    """
    return await db.fetchall(
        "SELECT * FROM search_history ORDER BY searched_at DESC LIMIT ?",
        (limit,),
    )


async def mark_listings_inactive(
    db: DatabaseManager, older_than_hours: int = 72
) -> int:
    """Mark listings as inactive if not seen recently.

    Args:
        db: Database manager instance.
        older_than_hours: Hours since last_seen_at to consider stale.

    Returns:
        Number of listings marked inactive.
    """
    cursor = await db.execute(
        """
        UPDATE listings SET is_active = 0, updated_at = datetime('now')
        WHERE is_active = 1
        AND last_seen_at < datetime('now', ? || ' hours')
        """,
        (f"-{older_than_hours}",),
    )
    await db.commit()
    return cursor.rowcount


async def get_listing_stats(db: DatabaseManager) -> Dict[str, Any]:
    """Get summary statistics about stored listings.

    Args:
        db: Database manager instance.

    Returns:
        Dictionary with stats (total, active, shares, by_source, etc.).
    """
    total = await db.fetchone("SELECT COUNT(*) as count FROM listings")
    active = await db.fetchone(
        "SELECT COUNT(*) as count FROM listings WHERE is_active = 1"
    )
    shares = await db.fetchone(
        "SELECT COUNT(*) as count FROM listings WHERE is_share = 1"
    )
    saved = await db.fetchone("SELECT COUNT(*) as count FROM saved_listings")

    by_source = await db.fetchall(
        "SELECT source, COUNT(*) as count FROM listings GROUP BY source"
    )

    return {
        "total_listings": total["count"] if total else 0,
        "active_listings": active["count"] if active else 0,
        "share_listings": shares["count"] if shares else 0,
        "saved_listings": saved["count"] if saved else 0,
        "by_source": {row["source"]: row["count"] for row in by_source},
    }
