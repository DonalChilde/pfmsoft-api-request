"""SQLite persistence helpers for api-request Sqlite Cache.

This module contains SQL-backed helpers for storing and retrieving
CachedResponse and CacheInfo objects.
"""

import logging
import sqlite3
from uuid import UUID

from ..models import CachedResponse

logger = logging.getLogger(__name__)


def write_cached_response(
    connection: sqlite3.Connection, cache_key: str, cached_response: CachedResponse
) -> None:
    """Write or update a cached response in the SQLite database."""
    query = """
        INSERT INTO WebCache (
            cache_key,
            response_text,
            response_metadata_json,
            etag,
            last_modified,
            expires_at,
            timestamped
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            response_text = excluded.response_text,
            response_metadata_json = excluded.response_metadata_json,
            etag = excluded.etag,
            last_modified = excluded.last_modified,
            expires_at = excluded.expires_at,
            timestamped = excluded.timestamped
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
                cached_response.timestamped,
            ),
        )


def query_cached_response(
    connection: sqlite3.Connection, cache_key: str
) -> CachedResponse | None:
    """Query a cached response from the SQLite database."""
    query = """
        SELECT
            cache_key,
            response_text,
            response_metadata_json,
            etag,
            last_modified,
            expires_at,
            timestamped
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
        timestamped=row["timestamped"],
    )


def delete_cached_response(connection: sqlite3.Connection, cache_key: str) -> None:
    """Delete a cached response from the SQLite database."""
    query = "DELETE FROM WebCache WHERE cache_key = ?"
    with connection:
        connection.execute(query, (cache_key,))


# TODO querys as required for other operations. TBD
