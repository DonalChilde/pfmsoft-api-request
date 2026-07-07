"""Cache models for API requests."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from whenever import Instant


@dataclass(slots=True, kw_only=True, frozen=True)
class CachedResponse:
    """Represents a cached response for a Request."""

    cache_key: UUID
    """The UUID key for the cached response."""
    response_text: str
    """The text of the HTTP response."""
    response_metadata_json: str
    """The JSON-encoded string of the HTTP response metadata."""
    etag: str | None = None
    """The ETag header value of the HTTP response, if present."""
    last_modified: str | None = None
    """The Last-Modified header value of the HTTP response, if present."""
    expires_at: int | None = None
    """The instant in seconds when the cached response expires and should be considered stale."""
    cache_timestamp: int
    """The instant in nanoseconds when the response was cached."""

    @property
    def is_expired(self) -> bool:
        """Determine if the cached response is expired based on the current time and the expires_at instant."""
        if self.expires_at is None:
            return False
        return Instant.now().timestamp() >= self.expires_at

    @property
    def cache_age(self) -> int:
        """Calculate the age of the cached response in nanoseconds."""
        return Instant.now().timestamp_nanos() - self.cache_timestamp


class CachedResponseStatus(StrEnum):
    HIT = "HIT"
    MISS = "MISS"
    STALE = "STALE"


class CacheAction(StrEnum):
    ADDED_TO_CACHE = "ADDED_TO_CACHE"
    CACHED_RESPONSE_USED = "CACHED_RESPONSE_USED"
    CACHE_304_REFRESH_METADATA = "CACHE_304_REFRESH_METADATA"
    CACHE_304_UPDATE_RESPONSE = "CACHE_304_UPDATE_RESPONSE"


@dataclass(slots=True, kw_only=True, frozen=True)
class CacheInfo:
    """Represents information about the cache."""

    size: int = -1
    """The number of entries in the cache."""
