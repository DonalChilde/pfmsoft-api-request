"""Immutable cache model types used by cache implementations.

Time unit conventions:
    - `expires_at` uses Unix seconds.
    - `cache_timestamp` and `cache_age` use Unix nanoseconds.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from whenever import Instant


@dataclass(slots=True, kw_only=True, frozen=True)
class CachedResponse:
    """Represents one cached HTTP response payload and metadata snapshot.

    Instances are immutable so cache providers can safely return shared values
    without defensive copies.
    """

    cache_key: UUID
    """Unique cache key associated with the stored response."""
    response_text: str
    """Serialized response body text."""
    response_metadata_json: str
    """JSON-encoded ResponseMetadata document for the cached body."""
    etag: str | None = None
    """Cached ETag validator, if present."""
    last_modified: str | None = None
    """Cached Last-Modified validator, if present."""
    expires_at: int | None = None
    """Expiration instant in Unix seconds, or None when unknown."""
    cache_timestamp: int
    """Write/update instant in Unix nanoseconds."""

    @property
    def is_expired(self) -> bool:
        """Return True when the cached entry is expired.

        Entries with `expires_at=None` are treated as not expired.
        """
        if self.expires_at is None:
            return False
        return Instant.now().timestamp() >= self.expires_at

    @property
    def cache_age(self) -> int:
        """Return cache entry age in nanoseconds."""
        return Instant.now().timestamp_nanos() - self.cache_timestamp


class CachedResponseStatus(StrEnum):
    """Categorization for cache lookup outcomes."""

    HIT = "HIT"
    """A cache entry existed and was used without revalidation."""
    MISS = "MISS"
    """No cache entry existed for the requested key."""
    STALE = "STALE"
    """A cache entry existed but required revalidation."""


class CacheAction(StrEnum):
    """Lifecycle actions emitted by cache-aware request flows."""

    ADDED_TO_CACHE = "ADDED_TO_CACHE"
    """A response was written to cache for the first time or as replacement."""
    CACHED_RESPONSE_USED = "CACHED_RESPONSE_USED"
    """A previously cached response was returned directly."""
    CACHE_304_REFRESH_METADATA = "CACHE_304_REFRESH_METADATA"
    """A stale cache entry was refreshed from a 304 revalidation."""
    CACHE_304_UPDATE_RESPONSE = "CACHE_304_UPDATE_RESPONSE"
    """A stale cache entry was replaced by fresh response content."""


@dataclass(slots=True, kw_only=True, frozen=True)
class CacheInfo:
    """Summary information returned by cache providers."""

    size: int = -1
    """Number of stored entries, or -1 when unavailable."""
