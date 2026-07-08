"""SQLite persistence helpers for the cache backend.

This module contains SQL-backed helpers for storing and retrieving
`CachedResponse` rows in the `WebCache` table.
"""

import logging
import sqlite3
from uuid import UUID

from ..models import CachedResponse

logger = logging.getLogger(__name__)


def write_cached_response(
    connection: sqlite3.Connection, cache_key: str, cached_response: CachedResponse
) -> None:
    """Insert or replace a cached response row by key.

    Args:
        connection: Active SQLite connection.
        cache_key: Cache key string (UUID text representation).
        cached_response: Normalized cache model to persist.
    """
    query = """
        INSERT INTO WebCache (
            cache_key,
            response_text,
            response_metadata_json,
            etag,
            last_modified,
            expires_at,
            cache_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            response_text = excluded.response_text,
            response_metadata_json = excluded.response_metadata_json,
            etag = excluded.etag,
            last_modified = excluded.last_modified,
            expires_at = excluded.expires_at,
            cache_timestamp = excluded.cache_timestamp
    """

    with connection:
        connection.execute(
            query,
            (
                cache_key,
                cached_response.response_text,
                cached_response.response_metadata_json,
                cached_response.etag,
                cached_response.last_modified,
                cached_response.expires_at,
                cached_response.cache_timestamp,
            ),
        )


def query_cached_response(
    connection: sqlite3.Connection, cache_key: str
) -> CachedResponse | None:
    """Query one cached response row by key.

    Args:
        connection: Active SQLite connection.
        cache_key: Cache key string (UUID text representation).

    Returns:
        Matching cached response, or None when no row exists.
    """
    query = """
        SELECT
            cache_key,
            response_text,
            response_metadata_json,
            etag,
            last_modified,
            expires_at,
            cache_timestamp
        FROM WebCache
        WHERE cache_key = ?
    """

    row = connection.execute(query, (cache_key,)).fetchone()
    if row is None:
        return None

    return CachedResponse(
        cache_key=UUID(row["cache_key"]),
        response_text=row["response_text"],
        response_metadata_json=row["response_metadata_json"],
        etag=row["etag"],
        last_modified=row["last_modified"],
        expires_at=row["expires_at"],
        cache_timestamp=row["cache_timestamp"],
    )


def delete_cached_response(connection: sqlite3.Connection, cache_key: str) -> None:
    """Delete a cached response row by key.

    This operation is idempotent and does not raise for missing keys.
    """
    query = "DELETE FROM WebCache WHERE cache_key = ?"
    with connection:
        connection.execute(query, (cache_key,))
