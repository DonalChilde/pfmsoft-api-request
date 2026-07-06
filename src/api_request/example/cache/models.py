"""Models for caching responses in esi-link."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from whenever import Instant

from esi_link.execution.models import (
    HttpResponse,
    ResponseMetadata,
    ResponseMetadataRoot,
)


@dataclass(slots=True, kw_only=True, frozen=True)
class CachedResponse:
    """Represents a cached response for a Request."""

    cache_key: UUID
    """The UUID key for the cached response."""
    response_text: str
    """The text of the HTTP response."""
    response_metadata_json: bytes
    """The JSON-encoded bytes of the HTTP response metadata."""
    etag: str | None = None
    """The ETag header value of the HTTP response, if present."""
    expires_at: int | None = None
    """The instant when the cached response expires and should be considered stale."""
    timestamped: int
    """The instant when the response was cached."""

    @property
    def is_expired(self) -> bool:
        """Determine if the cached response is expired based on the current time and the expires_at instant."""
        if self.expires_at is None:
            return False
        return Instant.now().timestamp() >= self.expires_at

    @property
    def cache_age(self) -> int:
        """Calculate the age of the cached response in nanoseconds."""
        return Instant.now().timestamp_nanos() - self.timestamped

    @property
    def metadata(self) -> ResponseMetadata:
        """Get the response metadata as a ResponseMetadata object."""
        return ResponseMetadataRoot.model_validate_json(
            self.response_metadata_json
        ).root

    @property
    def http_response(self) -> HttpResponse:
        """Get the HTTP response as an HttpResponse object."""
        return HttpResponse(
            metadata=self.metadata,
            text=self.response_text,
        )


class CachedResponseStatus(StrEnum):
    HIT = "HIT"
    MISS = "MISS"
    STALE = "STALE"


class CacheAction(StrEnum):
    ADDED_TO_CACHE = "ADDED_TO_CACHE"
    CACHED_RESPONSE_USED = "CACHED_RESPONSE_USED"
    CACHE_304_REFRESH_METADATA = "CACHE_304_REFRESH_METADATA"
    CACHE_304_UPDATED = "CACHE_304_UPDATED"
