"""Tests for cache model dataclasses and enums."""

from __future__ import annotations

from uuid import uuid4

from whenever import Instant

from api_request.cache.models import (
    CacheAction,
    CachedResponse,
    CachedResponseStatus,
    CacheInfo,
)


def test_cached_response_is_expired_and_cache_age() -> None:
    """CachedResponse should report expiration and non-negative age."""
    now_seconds = Instant.now().timestamp()
    now_nanos = Instant.now().timestamp_nanos()

    no_expiry = CachedResponse(
        cache_key=uuid4(),
        response_text="[]",
        response_metadata_json="{}",
        expires_at=None,
        cache_timestamp=now_nanos,
    )
    expired = CachedResponse(
        cache_key=uuid4(),
        response_text="[]",
        response_metadata_json="{}",
        expires_at=now_seconds - 1,
        cache_timestamp=now_nanos - 1_000,
    )

    assert no_expiry.is_expired is False
    assert expired.is_expired is True
    assert no_expiry.cache_age >= 0


def test_cache_model_enums_and_info_defaults() -> None:
    """Cache enums and CacheInfo default should stay stable."""
    assert CachedResponseStatus.HIT == "HIT"
    assert CachedResponseStatus.MISS == "MISS"
    assert CachedResponseStatus.STALE == "STALE"

    assert CacheAction.ADDED_TO_CACHE == "ADDED_TO_CACHE"
    assert CacheAction.CACHED_RESPONSE_USED == "CACHED_RESPONSE_USED"
    assert CacheAction.CACHE_304_REFRESH_METADATA == "CACHE_304_REFRESH_METADATA"
    assert CacheAction.CACHE_304_UPDATE_RESPONSE == "CACHE_304_UPDATE_RESPONSE"

    assert CacheInfo().size == -1
