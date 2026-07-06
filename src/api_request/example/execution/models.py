"""Models for representing the http response data."""

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import RootModel
from pydantic_core import from_json
from whenever import Instant

logger = logging.getLogger(__name__)


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


ResponseMetadataRoot = RootModel[ResponseMetadata]


@dataclass(slots=True, kw_only=True, frozen=True)
class HttpResponse:
    """Represents an ESI response."""

    metadata: ResponseMetadata
    """The metadata of the response, including status code, headers, etc."""
    text: str
    """The body of the response as a string."""

    def to_string(self, indent: int) -> str:
        """Return a string representation of the HttpResponse with the specified indentation."""
        root_model = HttpResponseRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> HttpResponse:
        """Parse the HttpResponse from a JSON string."""
        value = HttpResponseRoot.model_validate_json(json_str).root
        return value

    @property
    def url(self) -> str:
        """Get the URL from the response metadata."""
        return self.metadata.url

    @property
    def status_code(self) -> int:
        """Get the status code from the response metadata."""
        return self.metadata.status_code

    @property
    def reason_phrase(self) -> str:
        """Get the reason phrase from the response metadata."""
        return self.metadata.reason_phrase

    @property
    def received_at(self) -> Instant:
        """Convert the received_timestamp to an Instant, if possible."""
        if self.metadata.received_timestamp != -1:
            return Instant.from_timestamp_nanos(self.metadata.received_timestamp)
        raise ValueError("Received timestamp is not set.")

    @property
    def etag(self) -> str | None:
        """Extract the ETag from the response headers, if present."""
        return self.metadata._headers_lower.get("etag")  # pyright: ignore[reportPrivateUsage]

    @property
    def last_modified(self) -> str | None:
        """Extract the Last-Modified header from the response headers, if present."""
        return self.metadata._headers_lower.get("last-modified")  # pyright: ignore[reportPrivateUsage]

    @property
    def expires(self) -> str | None:
        """Extract the Expires header from the response headers, if present."""
        return self.metadata._headers_lower.get("expires")  # pyright: ignore[reportPrivateUsage]

    @property
    def date(self) -> str | None:
        """Extract the Date header from the response headers, if present."""
        return self.metadata._headers_lower.get("date")  # pyright: ignore[reportPrivateUsage]

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
        return self.metadata._headers_lower.get("cache-control")  # pyright: ignore[reportPrivateUsage]

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
                    except (IndexError, ValueError):
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
        pages = self.metadata._headers_lower.get("x-pages", 1)  # pyright: ignore[reportPrivateUsage]
        return int(pages)

    @property
    def json(self) -> Any:
        """Parse the body text as JSON, if possible.

        Returns:
            The parsed JSON object.
        """
        return from_json(self.text)

    @property
    def ratelimit(self) -> X_ratelimit | None:
        """Extract the rate limit information from the X-RateLimit headers, if present."""
        group = self.metadata._headers_lower.get("x-ratelimit-group", "unknown")  # pyright: ignore[reportPrivateUsage]
        limit = self.metadata._headers_lower.get("x-ratelimit-limit", "unknown")  # pyright: ignore[reportPrivateUsage]
        remaining = self.metadata._headers_lower.get("x-ratelimit-remaining", "unknown")  # pyright: ignore[reportPrivateUsage]
        used = self.metadata._headers_lower.get("x-ratelimit-used", "unknown")  # pyright: ignore[reportPrivateUsage]
        # if any(value == "unknown" for value in (group, limit, remaining, used)):
        #     return None
        return X_ratelimit(group=group, limit=limit, remaining=remaining, used=used)


HttpResponseRoot = RootModel[HttpResponse]
