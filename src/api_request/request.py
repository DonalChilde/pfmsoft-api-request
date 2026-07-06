"""API request context manager."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from types import TracebackType
from typing import Self, TypeVar
from uuid import UUID

from httpx2 import AsyncClient

from api_request.helpers.http_session_factory import config_async_http_client
from api_request.models import FailedResponse, Request, Response, ResponseMetadata
from api_request.protocols import (
    ApiRequesterProtocol,
    CacheFactory,
    CacheProtocol,
)
from api_request.rate_limiter import RateLimiterFactoryProtocol, RateLimiterProtocol


class Source(StrEnum):
    """Enumeration of possible sources for a response."""

    CACHE = "cache"
    """The response was retrieved from the cache."""
    NETWORK = "network"
    """The response was retrieved from the network."""


@dataclass(slots=True, kw_only=True)
class _IntermediateRequest:
    """An intermediate response used during request processing."""

    request: Request
    """The original request that generated this intermediate response."""


@dataclass(slots=True, kw_only=True)
class _FailedRequest(_IntermediateRequest):
    """A failed response used during request processing."""

    pass


@dataclass(slots=True, kw_only=True)
class _FailNoResponse(_FailedRequest):
    """An intermediate response used during request processing.

    Used when no response was received.
    """

    error_message: str
    """An error message describing the failure."""


@dataclass(slots=True, kw_only=True)
class _FailWithResponse(_FailedRequest):
    """An intermediate response used during request processing.

    Used when a response was received but indicates failure.
    """

    metadata: ResponseMetadata
    """The metadata of the response, including status code, headers, etc."""
    text: str
    """The body of the response as a string."""


@dataclass(slots=True, kw_only=True)
class _UnprocessedRequest(_IntermediateRequest):
    """An unprocessed response used during request processing."""

    pass


@dataclass(slots=True, kw_only=True)
class _SuccessfulResponse(_IntermediateRequest):
    """A successful response used during request processing."""

    metadata: ResponseMetadata
    """The metadata of the response, including status code, headers, etc."""
    text: str
    """The body of the response as a string."""
    source: Source
    """The source of the response, e.g., 'cache' or 'network'."""


@dataclass(slots=True, kw_only=True)
class _CachableRequest(_IntermediateRequest):
    """A cachable response used during request processing."""


@dataclass(slots=True, kw_only=True)
class _RequestFromStaleCache(_CachableRequest):
    """A response from the cache that is stale and needs to be refreshed."""

    etag: str
    """The ETag of the cached response."""


@dataclass(slots=True, kw_only=True)
class _Response_Stale_304(_SuccessfulResponse):
    """A response indicating that the cached response is still valid (HTTP 304 Not Modified).

    This should come from the response to `_RequestFromStaleCache` and indicates that
    the cached response is still valid, but the metadata may have been updated (e.g.,
    headers like Cache-Control, Expires, etc.).
    """

    pass


@dataclass(slots=True, kw_only=True)
class _Response_Stale_200(_SuccessfulResponse):
    """A response indicating that the cached response is stale and has been refreshed (HTTP 200 OK).

    This should come from the response to `_RequestFromStaleCache` and indicates that
    the cached response needs to be updated with the new response data. The metadata
    and text of the new response are included.
    """

    pass


T = TypeVar("T", bound=_UnprocessedRequest)


class ApiRequester(ApiRequesterProtocol):
    def __init__(
        self,
        cache_factory: CacheFactory,
        rate_limiter_factory: RateLimiterFactoryProtocol[T],
    ) -> None:
        """Initialize the ApiRequester with a cache factory."""
        self._client: AsyncClient | None = None
        self._cache: CacheProtocol | None = None
        self._rate_limit: RateLimiterProtocol[T] | None = None
        self._cache_factory = cache_factory
        self._rate_limiter_factory = rate_limiter_factory

    async def __aenter__(self) -> Self:
        """Enter the asynchronous context manager."""
        self._client = await config_async_http_client()
        self._cache = self._cache_factory()
        await self._cache.__aenter__()
        self._rate_limit = self._rate_limiter_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the asynchronous context manager."""
        if self._cache is not None:
            await self._cache.__aexit__(exc_type, exc_value, traceback)
            self._cache = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def process_requests(
        self,
        requests: dict[UUID, Request],
    ) -> dict[UUID, Response | FailedResponse]:
        """Process a batch of API requests and return their corresponding cached responses."""
        if self._client is None:
            raise RuntimeError(
                "HTTP client is not initialized. Use 'async with ApiRequest()' to initialize."
            )
        responses: dict[UUID, Response | FailedResponse] = {}

        return responses

    async def _dispatch_requests(
        self,
        requests: dict[UUID, Request],
    ) -> dict[UUID, _IntermediateRequest]:
        """Dispatch a batch of API requests and return their corresponding intermediate responses."""
        if self._client is None:
            raise RuntimeError(
                "HTTP client is not initialized. Use 'async with ApiRequest()' to initialize."
            )
        intermediate_responses: dict[UUID, _IntermediateRequest] = {}

        return intermediate_responses
