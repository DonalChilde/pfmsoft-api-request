"""Tests for the in-memory cache implementation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from whenever import Instant

from api_request.cache.memory_cache import InMemoryCache
from api_request.cache.models import CachedResponse
from api_request.request.models import ResponseMetadata


def _build_cached_response(
    *,
    expires_at: int | None = None,
    cache_timestamp: int | None = None,
) -> CachedResponse:
    """Build a cached response for tests."""
    cache_key = uuid4()
    return CachedResponse(
        cache_key=cache_key,
        response_text="[]",
        response_metadata_json="{}",
        expires_at=expires_at,
        cache_timestamp=(
            cache_timestamp
            if cache_timestamp is not None
            else Instant.now().timestamp_nanos()
        ),
    )


def _build_metadata(*, etag: str | None = '"abc"') -> ResponseMetadata:
    """Build response metadata with at least one cache validator."""
    headers: list[tuple[str, str]] = [
        ("Date", "Mon, 06 Jul 2026 18:00:00 GMT"),
        ("Last-Modified", "Mon, 06 Jul 2026 17:00:00 GMT"),
    ]
    if etag is not None:
        headers.append(("ETag", etag))
    return ResponseMetadata(
        status_code=200,
        reason_phrase="OK",
        url="https://example.invalid/data",
        elapsed=10,
        bytes_downloaded=2,
        headers=tuple(headers),
        received_timestamp=Instant.now().timestamp_nanos(),
    )


def test_in_memory_cache_supports_basic_crud() -> None:
    """Entries should be retrievable, replaceable, and removable."""

    async def run() -> None:
        cache = InMemoryCache()
        metadata = _build_metadata()

        original = await cache.set(uuid4(), "[]", metadata)
        assert await cache.get(original.cache_key) == original

        updated = await cache.set(original.cache_key, "[1]", metadata)

        assert await cache.get(original.cache_key) == updated

        await cache.delete(original.cache_key)
        assert await cache.get(original.cache_key) is None

    asyncio.run(run())


def test_in_memory_cache_clear_filters_by_expiry_and_age() -> None:
    """Clear should remove only entries matching the requested filters."""

    async def run() -> None:
        cache = InMemoryCache()
        now_timestamp = Instant.now().timestamp()
        now_nanos = Instant.now().timestamp_nanos()
        age_limit = 500_000

        expired = _build_cached_response(
            expires_at=now_timestamp - 1,
            cache_timestamp=now_nanos - 1_000_000,
        )
        old_but_unexpired = _build_cached_response(
            expires_at=now_timestamp + 60,
            cache_timestamp=now_nanos - 1_000_000,
        )
        fresh = _build_cached_response(
            expires_at=now_timestamp + 60,
            cache_timestamp=now_nanos + 1_000_000_000,
        )

        cache._entries[expired.cache_key] = expired  # pyright: ignore[reportPrivateUsage]
        cache._entries[old_but_unexpired.cache_key] = old_but_unexpired  # pyright: ignore[reportPrivateUsage]
        cache._entries[fresh.cache_key] = fresh  # pyright: ignore[reportPrivateUsage]

        await cache.clear(only_expired=True)
        assert await cache.get(expired.cache_key) is None
        assert await cache.get(old_but_unexpired.cache_key) == old_but_unexpired
        assert await cache.get(fresh.cache_key) == fresh

        await cache.clear(age_limit=age_limit)
        assert await cache.get(old_but_unexpired.cache_key) is None
        assert await cache.get(fresh.cache_key) == fresh

    asyncio.run(run())


def test_in_memory_cache_reports_size_and_full_clear() -> None:
    """Cache info should reflect the current number of stored entries."""

    async def run() -> None:
        cache = InMemoryCache()
        first = await cache.set(uuid4(), "[]", _build_metadata())
        second = await cache.set(uuid4(), "[]", _build_metadata())
        assert await cache.cache_info() == type(await cache.cache_info())(size=2)

        await cache.flush()
        await cache.clear()
        assert await cache.cache_info() == type(await cache.cache_info())(size=0)

    asyncio.run(run())
