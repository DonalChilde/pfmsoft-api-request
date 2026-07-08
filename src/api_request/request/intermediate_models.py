"""Intermediate request and response models for request orchestration.

These models are used internally by the request pipeline to represent work in
progress and normalized intermediate outcomes before conversion into the public
response models.

They are importable across implementation modules and tests, but they are not
part of the stable public package API and may change during internal refactors.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from api_request.request.models import Request, ResponseMetadata, Source


@dataclass(slots=True, kw_only=True)
class IntermediateRequestBase:
    """Base model for intermediate request pipeline objects."""

    request: Request
    """The original request that generated this intermediate object."""


@dataclass(slots=True, kw_only=True)
class IntermediateResponseBase(IntermediateRequestBase):
    """Base model for intermediate responses used during request processing."""


@dataclass(slots=True, kw_only=True)
class FailedRequestBase(IntermediateResponseBase):
    """Base model for failed intermediate responses."""


@dataclass(slots=True, kw_only=True)
class FailNoResponse(FailedRequestBase):
    """Intermediate failure used when no response was received."""

    error_message: str
    """An error message describing the failure."""


@dataclass(slots=True, kw_only=True)
class FailWithResponse(FailedRequestBase):
    """Intermediate failure used when a response indicates failure."""

    metadata: ResponseMetadata
    """The metadata of the response, including status code and headers."""
    json: Any
    """The parsed JSON body of the response."""


@dataclass(slots=True, kw_only=True)
class UnprocessedRequest(IntermediateRequestBase):
    """Intermediate request that has not yet been sent."""


@dataclass(slots=True, kw_only=True)
class SuccessfulResponseBase(IntermediateResponseBase):
    """Base model for successful intermediate responses."""

    metadata: ResponseMetadata
    """The metadata of the response, including status code and headers."""
    json: Any
    """The parsed JSON body of the response."""
    source: Source
    """The source of the response, for example cache or network."""


@dataclass(slots=True, kw_only=True)
class SuccessfulResponse(SuccessfulResponseBase):
    """Successful intermediate response used during request processing."""


@dataclass(slots=True, kw_only=True)
class CachableRequest(UnprocessedRequest):
    """Intermediate request that has an associated cache key."""

    cache_key: UUID
    """The cache key associated with this request."""


@dataclass(slots=True, kw_only=True)
class RequestFromStaleCache(CachableRequest):
    """A stale cached request that needs revalidation."""

    etag: str | None
    """The ETag of the cached response."""
    last_modified: str | None = None
    """The Last-Modified header of the cached response, if available."""

    @property
    def conditional_headers(self) -> dict[str, str]:
        """Build conditional request headers for stale-cache revalidation.

        Returns:
            A dictionary containing `If-None-Match` and/or
            `If-Modified-Since`.

        Raises:
            ValueError: If both validators are missing.
        """
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
class Response304FromStaleCache(SuccessfulResponseBase):
    """A cached-body response refreshed by an HTTP 304 revalidation."""

    source: Source = Source.CACHE_304


@dataclass(slots=True, kw_only=True)
class Response200FromStaleCache(SuccessfulResponseBase):
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
