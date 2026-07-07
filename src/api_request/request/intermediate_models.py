"""Intermediate request and response models for request orchestration.

These models are used internally by the request pipeline to represent work in
progress and normalized intermediate outcomes before conversion into the public
response models.

They are importable across implementation modules and tests, but they are not
part of the stable public package API and may change during internal refactors.
"""

from collections.abc import Hashable
from dataclasses import dataclass
from uuid import UUID

from api_request.request.models import Request, ResponseMetadata, Source


@dataclass(slots=True, kw_only=True)
class IntermediateRequestBase[T: Hashable]:
    """Base model for intermediate request pipeline objects."""

    request: Request[T]
    """The original request that generated this intermediate object."""


@dataclass(slots=True, kw_only=True)
class IntermediateResponseBase[T: Hashable](IntermediateRequestBase[T]):
    """Base model for intermediate responses used during request processing."""


@dataclass(slots=True, kw_only=True)
class FailedRequestBase[T: Hashable](IntermediateResponseBase[T]):
    """Base model for failed intermediate responses."""


@dataclass(slots=True, kw_only=True)
class FailNoResponse[T: Hashable](FailedRequestBase[T]):
    """Intermediate failure used when no response was received."""

    error_message: str
    """An error message describing the failure."""


@dataclass(slots=True, kw_only=True)
class FailWithResponse[T: Hashable](FailedRequestBase[T]):
    """Intermediate failure used when a response indicates failure."""

    metadata: ResponseMetadata
    """The metadata of the response, including status code and headers."""
    text: str
    """The body of the response as a string."""


@dataclass(slots=True, kw_only=True)
class UnprocessedRequest[T: Hashable](IntermediateRequestBase[T]):
    """Intermediate request that has not yet been sent."""


@dataclass(slots=True, kw_only=True)
class SuccessfulResponseBase[T: Hashable](IntermediateResponseBase[T]):
    """Base model for successful intermediate responses."""

    metadata: ResponseMetadata
    """The metadata of the response, including status code and headers."""
    text: str
    """The body of the response as a string."""
    source: Source
    """The source of the response, for example cache or network."""


@dataclass(slots=True, kw_only=True)
class SuccessfulResponse[T: Hashable](SuccessfulResponseBase[T]):
    """Successful intermediate response used during request processing."""


@dataclass(slots=True, kw_only=True)
class CachableRequest[T: Hashable](UnprocessedRequest[T]):
    """Intermediate request that has an associated cache key."""

    cache_key: UUID
    """The cache key associated with this request."""


@dataclass(slots=True, kw_only=True)
class RequestFromStaleCache[T: Hashable](CachableRequest[T]):
    """A stale cached request that needs revalidation."""

    etag: str | None
    """The ETag of the cached response."""
    last_modified: str | None = None
    """The Last-Modified header of the cached response, if available."""

    @property
    def conditional_headers(self) -> dict[str, str]:
        """Return the conditional headers used to revalidate a stale cache entry."""
        headers: dict[str, str] = {}
        if not self.etag and not self.last_modified:
            raise ValueError(
                "At least one of ETag or Last-Modified must be provided for a stale cache request."
            )
        if self.etag:
            headers["If-None-Match"] = self.etag
        if self.last_modified:
            headers["If-Modified-Since"] = self.last_modified
        return headers


@dataclass(slots=True, kw_only=True)
class Response304FromStaleCache[T: Hashable](SuccessfulResponseBase[T]):
    """A cached-body response refreshed by an HTTP 304 revalidation."""

    source: Source = Source.CACHE_304


@dataclass(slots=True, kw_only=True)
class Response200FromStaleCache[T: Hashable](SuccessfulResponseBase[T]):
    """A refreshed cached response replaced by an HTTP 200 revalidation."""

    source: Source = Source.CACHE_200


__all__ = [
    "CachableRequest",
    "FailNoResponse",
    "FailWithResponse",
    "FailedRequestBase",
    "IntermediateRequestBase",
    "IntermediateResponseBase",
    "RequestFromStaleCache",
    "Response200FromStaleCache",
    "Response304FromStaleCache",
    "SuccessfulResponse",
    "SuccessfulResponseBase",
    "UnprocessedRequest",
]
