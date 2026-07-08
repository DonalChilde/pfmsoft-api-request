"""Models for API requests."""

import logging
from collections.abc import Hashable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import RootModel
from whenever import Instant

logger = logging.getLogger(__name__)

type PARAMETER = str | int | float


#######################################################################################
# Request Models
#######################################################################################


@dataclass(slots=True, kw_only=True, frozen=True)
class Request[T: Hashable]:
    """Represents an API request."""

    request_key: UUID = field(default_factory=uuid4)
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
    rate_key: T | None = None
    """Optional key used by rate-limiter implementations to group requests."""


#######################################################################################
# Response Models
#######################################################################################
class Source(StrEnum):
    """Enumeration of possible sources for a response."""

    CACHE = "cache"
    """The response was retrieved from the cache."""
    CACHE_304 = "cache-304"
    """The cached response was revalidated and remained current."""
    CACHE_200 = "cache-200"
    """The cached response was revalidated and replaced by fresh content."""
    NETWORK = "network"
    """The response was retrieved from the network."""


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
    def as_string(self) -> str:
        """Get the response metadata as a JSON string."""
        return ResponseMetadataRoot(self).model_dump_json()

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
class Response[T: Hashable]:
    """Represents an ESI response."""

    metadata: ResponseMetadata
    """The metadata of the response, including status code, headers, etc."""
    json: Any
    """The parsed JSON body of the response."""
    request: Request[T]
    """The original request that generated this response."""
    source: Source
    """The source of the response, for example cache or network."""

    def to_string(self, indent: int) -> str:
        """Return a string representation of the Response with the specified indentation."""
        root_model = RootModel[Response[Hashable]](cast(Response[Hashable], self))
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> Response[T]:
        """Parse the Response from a JSON string."""
        value = RootModel[Response[Hashable]].model_validate_json(json_str).root
        return cast(Response[T], value)

    @property
    def json_loads(self) -> Any:
        """Get the parsed JSON body.

        Returns:
            The parsed JSON object.
        """
        return self.json


@dataclass(slots=True, kw_only=True, frozen=True)
class FailedResponse[T: Hashable]:
    """Represents a failed ESI response, typically due to an error status code."""

    metadata: ResponseMetadata | None = None
    """The metadata of the response, including status code, headers, etc. May be None 
    if the request failed before receiving a response."""
    json: Any | None = None
    """The parsed JSON body of the response. May be None if unavailable."""
    request: Request[T]
    """The original request that generated this failed response."""
    error_messages: list[str] = field(default_factory=list[str])
    """An optional list of error messages describing the failure."""


@dataclass(slots=True, kw_only=True, frozen=True)
class Responses[T: Hashable]:
    successful: dict[UUID, Response[T]] = field(default_factory=dict[UUID, Response[T]])
    """A dictionary of successful responses, keyed by request UUID."""
    failed: dict[UUID, FailedResponse[T]] = field(
        default_factory=dict[UUID, FailedResponse[T]]
    )
    """A dictionary of failed responses, keyed by request UUID."""


type Requests[T: Hashable] = dict[UUID, Request[T]]

#######################################################################################
# Root Models
#######################################################################################
ResponseMetadataRoot = RootModel[ResponseMetadata]
ResponseRoot = RootModel[Response[Hashable]]
RequestsRoot = RootModel[Requests[Hashable]]
ResponsesRoot = RootModel[Responses[Hashable]]
