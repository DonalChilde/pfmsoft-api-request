"""Tests for the in-memory cache implementation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from whenever import Instant

from api_request.cache.memory_cache import InMemoryCache
from api_request.cache.models import CachedResponse


def _build_cached_response(
    *,
    expires_at: int | None = None,
    timestamped: int | None = None,
) -> CachedResponse:
    """Build a cached response for tests."""
    cache_key = uuid4()
    return CachedResponse(
        cache_key=cache_key,
        response_text="[]",
        response_metadata_json="{}",
        expires_at=expires_at,
        timestamped=(
            timestamped if timestamped is not None else Instant.now().timestamp_nanos()
        ),
    )


def test_in_memory_cache_supports_basic_crud() -> None:
    """Entries should be retrievable, replaceable, and removable."""

    async def run() -> None:
        cache = InMemoryCache()
        original = _build_cached_response()
        updated = _build_cached_response(timestamped=original.timestamped + 1)

        await cache.set(original.cache_key, original)
        assert await cache.get(original.cache_key) == original

        await cache.update(original.cache_key, updated)
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
            timestamped=now_nanos - 1_000_000,
        )
        old_but_unexpired = _build_cached_response(
            expires_at=now_timestamp + 60,
            timestamped=now_nanos - 1_000_000,
        )
        fresh = _build_cached_response(
            expires_at=now_timestamp + 60,
            timestamped=now_nanos + 1_000_000_000,
        )

        await cache.set(expired.cache_key, expired)
        await cache.set(old_but_unexpired.cache_key, old_but_unexpired)
        await cache.set(fresh.cache_key, fresh)

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
        first = _build_cached_response()
        second = _build_cached_response()

        await cache.set(first.cache_key, first)
        await cache.set(second.cache_key, second)
        assert await cache.cache_info() == type(await cache.cache_info())(size=2)

        await cache.flush()
        await cache.clear()
        assert await cache.cache_info() == type(await cache.cache_info())(size=0)

    asyncio.run(run())
