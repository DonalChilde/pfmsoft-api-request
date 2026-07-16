"""SQLite-backed cache provider for request orchestration.

This module provides a `CacheProtocol` implementation backed by a `WebCache`
table and a small factory for dependency injection.
"""

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self
from uuid import UUID

from whenever import Instant

from ...request.models import ResponseMetadata
from ..metadata_helpers import merge_cached_revalidation_metadata
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
            closed automatically via the context manager.

            When initialized with an existing connection, that connection is never
            closed by this class.
        """
        self._connection: sqlite3.Connection | None = None
        self._close_connection_on_exit: bool = False
        if isinstance(db, sqlite3.Connection):
            self._connection = db
            self._close_connection_on_exit = False
            self._connection_path: Path | None = None
        else:
            self._connection_path = Path(db)

    async def __aenter__(self) -> Self:
        """Enter context and open path-owned connections when needed."""
        if self._connection_path is not None:
            self._connection = create_read_write_connection(self._connection_path)
            self._close_connection_on_exit = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit context and close only connections owned by this instance."""
        _ = exc_type, exc_value, traceback
        if self._connection is not None:
            if self._close_connection_on_exit:
                self._connection.close()

    def _ensure_connection(self) -> sqlite3.Connection:
        """Ensure an active SQLite connection is present."""
        if self._connection is None:
            raise RuntimeError("No active SQLite connection")
        return self._connection

    async def get(self, cache_key: UUID) -> CachedResponse | None:
        """Get a cached response by key, or None when missing."""
        connection = self._ensure_connection()
        return query_helpers.query_cached_response(connection, str(cache_key))

    @staticmethod
    def _ensure_validators(metadata: ResponseMetadata) -> None:
        """Ensure at least one cache validator is present."""
        if metadata.etag is None and metadata.last_modified is None:
            raise ValueError("Cached responses require etag or last_modified")

    @staticmethod
    def _build_cached_response(
        *,
        cache_key: UUID,
        text: str,
        metadata: ResponseMetadata,
    ) -> CachedResponse:
        """Build a CachedResponse from response text and metadata."""
        SqliteCache._ensure_validators(metadata)
        return CachedResponse(
            cache_key=cache_key,
            response_text=text,
            response_metadata_json=metadata.serialize(),
            etag=metadata.etag,
            last_modified=metadata.last_modified,
            expires_at=metadata.expires_at,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )

    async def set(
        self, cache_key: UUID, text: str, metadata: ResponseMetadata
    ) -> CachedResponse:
        """Create or replace a cached response entry.

        Raises:
            ValueError: If both metadata validators are absent.
        """
        cached_response = self._build_cached_response(
            cache_key=cache_key,
            text=text,
            metadata=metadata,
        )
        connection = self._ensure_connection()
        query_helpers.write_cached_response(
            connection,
            str(cache_key),
            cached_response,
        )
        return cached_response

    async def update_304(
        self, cache_key: UUID, metadata: ResponseMetadata
    ) -> CachedResponse:
        """Refresh a stale entry from 304 metadata while preserving body text.

        Raises:
            KeyError: If no existing entry is present.
            ValueError: If merged metadata lacks both validators.
        """
        existing = await self.get(cache_key)
        if existing is None:
            raise KeyError(f"No cached response found for key {cache_key}")

        existing_metadata = ResponseMetadata.deserialize(
            existing.response_metadata_json
        )
        merged_metadata = merge_cached_revalidation_metadata(
            cached=existing_metadata,
            refreshed=metadata,
        )

        cached_response = self._build_cached_response(
            cache_key=cache_key,
            text=existing.response_text,
            metadata=merged_metadata,
        )
        connection = self._ensure_connection()
        query_helpers.write_cached_response(
            connection,
            str(cache_key),
            cached_response,
        )
        return cached_response

    async def delete(self, cache_key: UUID) -> None:
        """Delete a cached response from the cache.

        This operation is idempotent and does not raise for missing keys.
        """
        connection = self._ensure_connection()
        query_helpers.delete_cached_response(connection, str(cache_key))

    async def clear(
        self, only_expired: bool = False, age_limit: int | None = None
    ) -> None:
        """Clear cached entries matching the requested filters.

        Args:
            only_expired: When true, remove only expired entries.
            age_limit: When provided, remove entries with `cache_age` greater
                than or equal to this nanosecond threshold.

        Notes:
            When both filters are provided, entries must satisfy both.
        """
        connection = self._ensure_connection()
        if not only_expired and age_limit is None:
            with connection:
                connection.execute("DELETE FROM WebCache")
            return

        clauses: list[str] = []
        params: list[int] = []

        if only_expired:
            clauses.append("(expires_at IS NOT NULL AND expires_at <= ?)")
            params.append(Instant.now().timestamp())

        if age_limit is not None:
            cutoff = Instant.now().timestamp_nanos() - age_limit
            clauses.append("cache_timestamp <= ?")
            params.append(cutoff)

        where_clause = " AND ".join(clauses)
        query = f"DELETE FROM WebCache WHERE {where_clause}"
        connection = self._ensure_connection()
        with connection:
            connection.execute(query, tuple(params))

    async def flush(self) -> None:
        """Commit pending writes on the active SQLite connection."""
        # hot cache not yet implememnted
        pass

    async def cache_info(self) -> CacheInfo:
        """Get summary information about the cache."""
        connection = self._ensure_connection()
        row = connection.execute("SELECT COUNT(*) AS size FROM WebCache").fetchone()
        size = 0 if row is None else int(row["size"])
        return CacheInfo(size=size)


class SqliteCacheFactory(CacheFactoryProtocol):
    """Factory for creating `SqliteCache` instances backed by a DB path."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize with the SQLite database path."""
        self._db_path = db_path

    def __call__(self) -> CacheProtocol:
        """Create and return a new SQLite-backed cache instance."""
        return SqliteCache(self._db_path)
