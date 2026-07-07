"""A sqlite3 based cache provider with factory function for use with ApiRequester."""

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self
from uuid import UUID

from whenever import Instant

from ..models import CachedResponse, CacheInfo
from ..protocols import CacheFactoryProtocol, CacheProtocol
from . import query_helpers
from .connection_helpers import create_read_write_connection


class SqliteCache(CacheProtocol):
    """SQLite-backed cache implementation.

    This cache persists entries in the `WebCache` table and maps CRUD operations
    to SQL statements through query helpers.
    """

    def __init__(
        self,
        db: str | Path | sqlite3.Connection,
    ) -> None:
        """Initialize cache with a database path or active SQLite connection.

        Args:
            db: Either a filesystem path to the SQLite database or an existing
                sqlite3 connection.

        Notes:
            When initialized with a path, a read-write connection is created and
            closed automatically on context manager exit. When initialized with
            an existing connection, that connection is never closed by this class.
        """
        if isinstance(db, sqlite3.Connection):
            self._connection = db
            self._close_connection_on_exit = False
        else:
            self._connection = create_read_write_connection(db)
            self._close_connection_on_exit = True

    async def __aenter__(self) -> Self:
        """Enter the asynchronous context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the asynchronous context manager."""
        _ = exc_type, exc_value, traceback
        if self._close_connection_on_exit:
            self._connection.close()

    async def get(self, cache_key: UUID) -> CachedResponse | None:
        """Get a cached response by cache key."""
        return query_helpers.query_cached_response(self._connection, str(cache_key))

    async def set(self, cache_key: UUID, cached_response: CachedResponse) -> None:
        """Set a cached response in the cache."""
        query_helpers.write_cached_response(
            self._connection,
            str(cache_key),
            cached_response,
        )

    async def update(self, cache_key: UUID, cached_response: CachedResponse) -> None:
        """Update an existing cached response in the cache."""
        query_helpers.write_cached_response(
            self._connection,
            str(cache_key),
            cached_response,
        )

    async def delete(self, cache_key: UUID) -> None:
        """Delete a cached response from the cache."""
        query_helpers.delete_cached_response(self._connection, str(cache_key))

    async def clear(
        self, only_expired: bool = False, age_limit: int | None = None
    ) -> None:
        """Clear cached entries matching the requested filters.

        Args:
            only_expired: When true, remove only expired entries.
            age_limit: When provided, remove entries with `cache_age` greater
                than or equal to this nanosecond threshold.
        """
        if not only_expired and age_limit is None:
            with self._connection:
                self._connection.execute("DELETE FROM WebCache")
            return

        clauses: list[str] = []
        params: list[int] = []

        if only_expired:
            clauses.append("(expires_at IS NOT NULL AND expires_at <= ?)")
            params.append(Instant.now().timestamp())

        if age_limit is not None:
            cutoff = Instant.now().timestamp_nanos() - age_limit
            clauses.append("timestamped <= ?")
            params.append(cutoff)

        where_clause = " OR ".join(clauses)
        query = f"DELETE FROM WebCache WHERE {where_clause}"
        with self._connection:
            self._connection.execute(query, tuple(params))

    async def flush(self) -> None:
        """Flush pending writes to disk."""
        self._connection.commit()

    async def cache_info(self) -> CacheInfo:
        """Get summary information about the cache."""
        row = self._connection.execute(
            "SELECT COUNT(*) AS size FROM WebCache"
        ).fetchone()
        size = 0 if row is None else int(row["size"])
        return CacheInfo(size=size)


class SqliteCacheFactory(CacheFactoryProtocol):
    """Factory for creating `SqliteCache` instances backed by a DB path."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize with the SQLite database path."""
        self._db_path = db_path

    def __call__(self) -> CacheProtocol:
        """Create a new SQLite-backed cache instance."""
        return SqliteCache(self._db_path)
