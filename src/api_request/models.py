"""Models for API requests."""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import RootModel
from pydantic_core import from_json
from whenever import Instant

logger = logging.getLogger(__name__)

type PARAMETER = str | int | float

#######################################################################################
# Request Models
#######################################################################################


@dataclass(slots=True, kw_only=True, frozen=True)
class Request:
    """Represents an API request."""

    request_key: UUID
    """The UUID key for the request."""
    url: str
    """The URL of the API request."""
    method: str
    """The HTTP method of the API request (e.g., GET, POST)."""
    headers: dict[str, str] = field(default_factory=dict[str, str])
    """The headers of the API request."""
    body: Any | None = None
    """The body of the API request, if applicable."""
    parameters: dict[str, PARAMETER] = field(default_factory=dict[str, PARAMETER])
    """The query parameters of the API request."""
    cache_key: UUID | None = None
    """The UUID key for the cached response. If None, the response is not cached."""


#######################################################################################
# Response Models
#######################################################################################


@dataclass(slots=True, kw_only=True, frozen=True)
class X_ratelimit:
    group: str
    limit: str
    remaining: str
    used: str


@dataclass(slots=True, kw_only=True, frozen=True)
class ResponseMetadata:
    """Represents the metadata of an ESI response, including status code, headers, etc."""

    status_code: int
    """The HTTP status code of the response."""
    reason_phrase: str
    """The reason phrase associated with the status code."""
    url: str
    """The URL that was requested to obtain this response."""
    elapsed: int
    """The time taken to receive the response, in microseconds, because the source is a timedelta."""
    bytes_downloaded: int
    """The number of bytes downloaded in the response body."""
    headers: tuple[tuple[str, str], ...] = field(
        default_factory=tuple[tuple[str, str], ...]
    )
    """The headers of the response as a tuple of key-value pairs."""
    received_timestamp: int = -1
    """The timestamp when the response was received, as a Unix timestamp in nanoseconds."""
    _headers_lower: dict[str, str] = field(
        init=False, repr=False, default_factory=dict[str, str]
    )
    """A lower case version of the headers for easier access to common headers like ETag and Last-Modified."""

    def __post_init__(self):
        """Create a lower case version of the headers for easier access to common headers like ETag and Last-Modified."""
        self._headers_lower.update({k.lower(): v for k, v in self.headers})
        if len(self.headers) != len(self._headers_lower):
            logger.warning(
                "Duplicate headers found when converting to lower case. This may lead to "
                "unexpected behavior when accessing headers. Original headers: %s, Lower "
                "case headers: %s",
                self.headers,
                self._headers_lower,
            )

    @property
    def as_bytes(self) -> bytes:
        """Get the response metadata as JSON-encoded bytes."""
        return ResponseMetadataRoot(self).model_dump_json().encode("utf-8")

    @property
    def headers_lower(self) -> dict[str, str]:
        """Get the lower case version of the headers for easier access to common headers like ETag and Last-Modified."""
        return self._headers_lower

    @property
    def received_at(self) -> Instant:
        """Convert the received_timestamp to an Instant, if possible."""
        if self.received_timestamp != -1:
            return Instant.from_timestamp_nanos(self.received_timestamp)
        raise ValueError("Received timestamp is not set.")

    @property
    def etag(self) -> str | None:
        """Extract the ETag from the response headers, if present."""
        return self.headers_lower.get("etag")

    @property
    def last_modified(self) -> str | None:
        """Extract the Last-Modified header from the response headers, if present."""
        return self.headers_lower.get("last-modified")

    @property
    def expires(self) -> str | None:
        """Extract the Expires header from the response headers, if present."""
        return self.headers_lower.get("expires")

    @property
    def date(self) -> str | None:
        """Extract the Date header from the response headers, if present."""
        return self.headers_lower.get("date")

    @property
    def date_as_instant(self) -> Instant | None:
        """Convert the Date header to an Instant, if possible."""
        date_str = self.date
        if date_str:
            try:
                return Instant.parse_rfc2822(date_str)
            except ValueError:
                pass
        return None

    @property
    def cache_control(self) -> str | None:
        """Extract the Cache-Control header from the response headers, if present."""
        return self.headers_lower.get("cache-control")

    @property
    def max_age(self) -> int | None:
        """Extract the max-age directive from the Cache-Control header, if present."""
        cache_control = self.cache_control
        if cache_control:
            directives = cache_control.split(",")
            for directive in directives:
                if "max-age" in directive:
                    try:
                        return int(directive.split("=")[1].strip())
                    except IndexError, ValueError:
                        pass
        return None

    @property
    def expires_at(self) -> int | None:
        """Calculate the expiration time of the response based on the Expires header or Cache-Control max-age."""
        if self.max_age is not None and self.date is not None:
            try:
                response_date = Instant.parse_rfc2822(self.date)
                return response_date.add(seconds=self.max_age).timestamp()
            except ValueError:
                pass
        if self.expires:
            try:
                return Instant.parse_rfc2822(self.expires).timestamp()
            except ValueError:
                pass
        return None

    @property
    def pages(self) -> int:
        """Extract the number of pages from the X-Pages header, if present."""
        pages = self.headers_lower.get("x-pages", 1)
        return int(pages)

    @property
    def ratelimit(self) -> X_ratelimit:
        """Extract the rate limit information from the X-RateLimit headers, if present."""
        group = self.headers_lower.get("x-ratelimit-group", "unknown")
        limit = self.headers_lower.get("x-ratelimit-limit", "unknown")
        remaining = self.headers_lower.get("x-ratelimit-remaining", "unknown")
        used = self.headers_lower.get("x-ratelimit-used", "unknown")
        return X_ratelimit(group=group, limit=limit, remaining=remaining, used=used)


@dataclass(slots=True, kw_only=True, frozen=True)
class Response:
    """Represents an ESI response."""

    metadata: ResponseMetadata
    """The metadata of the response, including status code, headers, etc."""
    text: str
    """The body of the response as a string."""
    request: Request
    """The original request that generated this response."""

    def to_string(self, indent: int) -> str:
        """Return a string representation of the Response with the specified indentation."""
        root_model = ResponseRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> Response:
        """Parse the Response from a JSON string."""
        value = ResponseRoot.model_validate_json(json_str).root
        return value

    @property
    def json_loads(self) -> Any:
        """Parse the body text as JSON, if possible.

        Returns:
            The parsed JSON object.
        """
        return from_json(self.text)


@dataclass(slots=True, kw_only=True, frozen=True)
class FailedResponse:
    """Represents a failed ESI response, typically due to an error status code."""

    metadata: ResponseMetadata | None = None
    """The metadata of the response, including status code, headers, etc. May be None 
    if the request failed before receiving a response."""
    text: str | None = None
    """The body of the response as a string. May be None if the request failed before receiving a response."""
    request: Request
    """The original request that generated this failed response."""
    error_message: str | None = None
    """An optional error message describing the failure."""


#######################################################################################
# Cache Models
#######################################################################################


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


#######################################################################################
# Root Models
#######################################################################################
ResponseMetadataRoot = RootModel[ResponseMetadata]
ResponseRoot = RootModel[Response]
