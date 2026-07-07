"""Tests for the SQLite-backed cache implementation."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from uuid import uuid4

from whenever import Instant

from api_request.cache.sqlite_cache.connection_helpers import (
    create_read_write_connection,
)
from api_request.cache.sqlite_cache.sqlite_cache import SqliteCache, SqliteCacheFactory
from api_request.request.models import ResponseMetadata, ResponseMetadataRoot


def _build_metadata(
    *,
    status_code: int = 200,
    reason_phrase: str = "OK",
    etag: str | None = '"abc"',
    last_modified: str | None = "Mon, 06 Jul 2026 17:00:00 GMT",
    date: str = "Mon, 06 Jul 2026 18:00:00 GMT",
    cache_control: str | None = "max-age=60",
    received_timestamp: int | None = None,
    bytes_downloaded: int = 2,
) -> ResponseMetadata:
    """Build response metadata for cache tests."""
    headers: list[tuple[str, str]] = [("Date", date)]
    if last_modified is not None:
        headers.append(("Last-Modified", last_modified))
    if etag is not None:
        headers.append(("ETag", etag))
    if cache_control is not None:
        headers.append(("Cache-Control", cache_control))
    return ResponseMetadata(
        status_code=status_code,
        reason_phrase=reason_phrase,
        url="https://example.invalid/data",
        elapsed=10,
        bytes_downloaded=bytes_downloaded,
        headers=tuple(headers),
        received_timestamp=(
            received_timestamp
            if received_timestamp is not None
            else Instant.now().timestamp_nanos()
        ),
    )


def _build_db_path(tmp_path: Path, *, name: str = "cache.sqlite3") -> Path:
    """Build a test database path under pytest's temporary directory."""
    return tmp_path / name


def test_sqlite_cache_supports_basic_crud_and_factory(tmp_path: Path) -> None:
    """Entries should persist through create, replace, read, and delete."""

    async def run() -> None:
        cache = SqliteCacheFactory(_build_db_path(tmp_path))()
        metadata = _build_metadata()

        async with cache:
            original = await cache.set(uuid4(), "[]", metadata)
            assert await cache.get(original.cache_key) == original
            assert await cache.cache_info() == type(await cache.cache_info())(size=1)

            updated = await cache.set(original.cache_key, "[1]", metadata)
            assert await cache.get(original.cache_key) == updated

            await cache.delete(original.cache_key)
            assert await cache.get(original.cache_key) is None
            assert await cache.cache_info() == type(await cache.cache_info())(size=0)

    asyncio.run(run())


def test_sqlite_cache_update_304_preserves_body_and_success_metadata(
    tmp_path: Path,
) -> None:
    """A 304 refresh should keep the cached body while storing merged success metadata."""

    async def run() -> None:
        cache = SqliteCache(_build_db_path(tmp_path))
        original_metadata = _build_metadata(
            status_code=200,
            reason_phrase="OK",
            etag='"etag-1"',
            date="Mon, 06 Jul 2026 18:00:00 GMT",
            cache_control="max-age=60",
            received_timestamp=1_000,
            bytes_downloaded=99,
        )
        refreshed_metadata = _build_metadata(
            status_code=304,
            reason_phrase="Not Modified",
            etag='"etag-2"',
            date="Mon, 06 Jul 2026 18:05:00 GMT",
            cache_control="max-age=120",
            received_timestamp=2_000,
            bytes_downloaded=0,
        )

        async with cache:
            stored = await cache.set(uuid4(), '{"ok":true}', original_metadata)
            updated = await cache.update_304(stored.cache_key, refreshed_metadata)

            assert updated.response_text == stored.response_text
            assert updated.etag == '"etag-2"'
            assert updated.cache_timestamp >= stored.cache_timestamp

            merged = ResponseMetadataRoot.model_validate_json(
                updated.response_metadata_json
            ).root
            assert merged.status_code == 200
            assert merged.reason_phrase == "OK"
            assert merged.bytes_downloaded == 99
            assert merged.etag == '"etag-2"'
            assert merged.cache_control == "max-age=120"
            assert merged.received_timestamp == 2_000

            persisted = await cache.get(stored.cache_key)
            assert persisted == updated

    asyncio.run(run())


def test_sqlite_cache_clear_filters_by_expiry_and_age(tmp_path: Path) -> None:
    """Clear should remove only entries matching the requested filters."""

    async def run() -> None:
        db_path = _build_db_path(tmp_path)
        cache_key_expired = uuid4()
        cache_key_old = uuid4()
        cache_key_fresh = uuid4()
        metadata = _build_metadata()

        async with SqliteCache(db_path) as cache:
            expired = await cache.set(cache_key_expired, "expired", metadata)
            old_but_unexpired = await cache.set(cache_key_old, "old", metadata)
            fresh = await cache.set(cache_key_fresh, "fresh", metadata)

            now_seconds = Instant.now().timestamp()
            now_nanos = Instant.now().timestamp_nanos()
            connection = cache._connection  # pyright: ignore[reportPrivateUsage]
            connection.execute(
                "UPDATE WebCache SET expires_at = ?, cache_timestamp = ? WHERE cache_key = ?",
                (now_seconds - 1, now_nanos - 2_000_000, str(expired.cache_key)),
            )
            connection.execute(
                "UPDATE WebCache SET expires_at = ?, cache_timestamp = ? WHERE cache_key = ?",
                (
                    now_seconds + 60,
                    now_nanos - 2_000_000,
                    str(old_but_unexpired.cache_key),
                ),
            )
            connection.execute(
                "UPDATE WebCache SET expires_at = ?, cache_timestamp = ? WHERE cache_key = ?",
                (now_seconds + 60, now_nanos + 1_000_000_000, str(fresh.cache_key)),
            )
            connection.commit()

            await cache.clear(only_expired=True)
            assert await cache.get(cache_key_expired) is None
            assert await cache.get(cache_key_old) is not None
            assert await cache.get(cache_key_fresh) is not None

            await cache.clear(age_limit=1_000_000)
            assert await cache.get(cache_key_old) is None
            assert await cache.get(cache_key_fresh) is not None

    asyncio.run(run())


def test_sqlite_cache_context_manager_respects_connection_ownership(
    tmp_path: Path,
) -> None:
    """Path-owned connections should close on exit, but external ones should remain open."""

    async def run() -> None:
        path_cache = SqliteCache(_build_db_path(tmp_path, name="owned.sqlite3"))
        async with path_cache:
            await path_cache.set(uuid4(), "[]", _build_metadata())
            owned_connection = path_cache._connection  # pyright: ignore[reportPrivateUsage]

        try:
            owned_connection.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            pass
        else:
            raise AssertionError("Path-owned SQLite connection should be closed")

        external_connection = create_read_write_connection(
            _build_db_path(tmp_path, name="external.sqlite3")
        )
        external_cache = SqliteCache(external_connection)
        async with external_cache:
            await external_cache.set(uuid4(), "[]", _build_metadata())

        assert external_connection.execute("SELECT 1").fetchone() is not None
        external_connection.close()

    asyncio.run(run())
