"""SQLite persistence helpers for api-request Sqlite Cache.

This module contains SQL-backed helpers for storing and retrieving
CachedResponse and CacheInfo objects.
"""

import logging
import sqlite3

from ..models import CachedResponse, CacheInfo

logger = logging.getLogger(__name__)


def write_cached_response(
    connection: sqlite3.Connection, cache_key: str, cached_response: CachedResponse
) -> None:
    """Write or update a cached response in the SQLite database."""
    ...


def query_cached_response(
    connection: sqlite3.Connection, cache_key: str
) -> CachedResponse | None:
    """Query a cached response from the SQLite database."""
    ...


def delete_cached_response(connection: sqlite3.Connection, cache_key: str) -> None:
    """Delete a cached response from the SQLite database."""
    ...
