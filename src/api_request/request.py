"""API request context manager."""

from collections.abc import Hashable
from dataclasses import dataclass
from enum import StrEnum
from types import TracebackType
from typing import Any, Self
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
    CACHE_304 = "cache-304"
    """The response was retrieved from the cache and indicates that the cached response 
    was still valid (HTTP 304 Not Modified)."""
    CACHE_200 = "cache-200"
    """The response was retrieved from the cache and indicates that the cached response 
    was stale and has been refreshed (HTTP 200 OK)."""
    NETWORK = "network"
    """The response was retrieved from the network."""


@dataclass(slots=True, kw_only=True)
class _IntermediateRequestBase[T: Hashable]:
    """An intermediate request used during request processing.

    Used a base class for various intermediate request and response types during the
    processing of API requests. Not directly instantiated, but serves as a common
    interface for the different stages of request handling.
    """

    request: Request[T]
    """The original request that generated this intermediate response."""


@dataclass(slots=True, kw_only=True)
class _FailedRequestBase[T: Hashable](_IntermediateRequestBase[T]):
    """A failed request used during request processing.

    Used as a base class for various intermediate request and response types that
    represent failed requests during the processing of API requests. Not directly
    instantiated, but serves as a common interface for the different stages of request
    handling.
    """

    pass


@dataclass(slots=True, kw_only=True)
class _FailNoResponse[T: Hashable](_FailedRequestBase[T]):
    """An intermediate response used during request processing.

    Used when no response was received.
    """

    error_message: str
    """An error message describing the failure."""


@dataclass(slots=True, kw_only=True)
class _FailWithResponse[T: Hashable](_FailedRequestBase[T]):
    """An intermediate response used during request processing.

    Used when a response was received but indicates failure.
    """

    metadata: ResponseMetadata
    """The metadata of the response, including status code, headers, etc."""
    text: str
    """The body of the response as a string."""


@dataclass(slots=True, kw_only=True)
class _UnprocessedRequest[T: Hashable](_IntermediateRequestBase[T]):
    """An unprocessed response used during request processing."""

    pass


@dataclass(slots=True, kw_only=True)
class _IntermediateResponseBase[T: Hashable](_IntermediateRequestBase[T]):
    """An intermediate response used during request processing.

    Used as a base class for various intermediate request and response types during the
    processing of API requests. Not directly instantiated, but serves as a common
    interface for the different stages of request handling.
    """

    pass


class _SuccessfulResponseBase[T: Hashable](_IntermediateResponseBase[T]):
    """A successful response used during request processing.

    Used when a response was received and indicates success.
    """

    metadata: ResponseMetadata
    """The metadata of the response, including status code, headers, etc."""
    text: str
    """The body of the response as a string."""
    source: Source
    """The source of the response, e.g., 'cache' or 'network'."""


@dataclass(slots=True, kw_only=True)
class _SuccessfulResponse[T: Hashable](_SuccessfulResponseBase[T]):
    """A successful response used during request processing.

    Used when a response was received and indicates success.
    """


@dataclass(slots=True, kw_only=True)
class _CachableRequest[T: Hashable](_UnprocessedRequest[T]):
    """A cachable request used during request processing."""

    cache_key: UUID
    """The cache key associated with this request, used for caching responses."""


@dataclass(slots=True, kw_only=True)
class _RequestFromStaleCache[T: Hashable](_CachableRequest[T]):
    """A request from the cache that is stale and needs to be refreshed."""

    etag: str
    """The ETag of the cached response."""


@dataclass(slots=True, kw_only=True)
class _Response_304_FromStaleCache[T: Hashable](_SuccessfulResponseBase[T]):
    """A response indicating that the cached response is still valid (HTTP 304 Not Modified).

    This should come from the response to `_RequestFromStaleCache` and indicates that
    the cached response is still valid, but the metadata may have been updated (e.g.,
    headers like Cache-Control, Expires, etc.).
    """

    source: Source = Source.CACHE_304


@dataclass(slots=True, kw_only=True)
class _Response_200_FromStaleCache[T: Hashable](_SuccessfulResponseBase[T]):
    """A response indicating that the cached response is stale and has been refreshed (HTTP 200 OK).

    This should come from the response to `_RequestFromStaleCache` and indicates that
    the cached response needs to be updated with the new response data. The metadata
    and text of the new response are included.
    """

    source: Source = Source.CACHE_200


class ApiRequester[T: Hashable](ApiRequesterProtocol[T]):
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

    async def _session_check(self) -> AsyncClient:
        """Check if the HTTP client is initialized and return it."""
        if self._client is None:
            raise RuntimeError(
                "HTTP client is not initialized. Use 'async with ApiRequest()' to initialize."
            )
        return self._client

    async def _cache_check(self) -> CacheProtocol:
        """Check if the cache is initialized and return it."""
        if self._cache is None:
            raise RuntimeError(
                "Cache is not initialized. Use 'async with ApiRequest()' to initialize."
            )
        return self._cache

    async def _rate_limit_check(self) -> RateLimiterProtocol[T]:
        """Check if the rate limiter is initialized and return it."""
        if self._rate_limit is None:
            raise RuntimeError(
                "Rate limiter is not initialized. Use 'async with ApiRequest()' to initialize."
            )
        return self._rate_limit

    @property
    async def cache(self) -> CacheProtocol:
        """Get the cache instance."""
        return await self._cache_check()

    @property
    async def rate_limiter(self) -> RateLimiterProtocol[T]:
        """Get the rate limiter instance."""
        return await self._rate_limit_check()

    @property
    async def session(self) -> AsyncClient:
        """Get the HTTP client instance."""
        return await self._session_check()

    async def process_requests(
        self,
        requests: dict[UUID, Request[T]],
    ) -> dict[UUID, Response[T] | FailedResponse[T]]:
        """Process a batch of API requests and return their corresponding cached responses."""
        intermediate_responses = await self._dispatch_requests(requests)

        _ = intermediate_responses  # Placeholder to avoid unused variable warning
        # Process the intermediate responses to produce final responses
        responses: dict[UUID, Response[T] | FailedResponse[T]] = {}
        return responses

    async def _dispatch_requests(
        self,
        requests: dict[UUID, Request[T]],
    ) -> dict[UUID, _IntermediateResponseBase[T]]:
        """Dispatch a batch of API requests and return their corresponding intermediate responses."""
        # This method would handle the logic for dispatching requests, including:
        # - turning requests into _UnprocessedRequest[T] and _CachableRequest[T]
        # - assembling the async tasks for each request
        #   - _unprocessed_request for non-cacheable requests can go to _http_request
        #   - _cachable_request for cacheable requests can go to _cacheable_request
        # - gathering the results of the async tasks

        # can TaskGroup be used to manage the tasks? or just asyncio.gather?
        # Some failures may be recoverable, and passed back as _FailWithResponse[T] or _FailNoResponse[T],
        # while other failures should stop the entire process and raise an exception.
        # Explain ways to do this.

        intermediate_responses: dict[UUID, _IntermediateResponseBase[T]] = {}
        # requests are turned into list[_UnprocessedRequest[T]] and list[_CachableRequest[T]]

        return intermediate_responses

    async def _http_request(
        self, request: _UnprocessedRequest[T]
    ) -> _SuccessfulResponse[T] | _FailedRequestBase[T]:
        """Perform an HTTP request and return the corresponding intermediate response."""
        # This method would use:
        # self.session to perform the HTTP request, and self.rate_limiter to enforce rate limiting.
        # detect paged responses and handle them appropriately.

        # It would then return an appropriate _IntermediateRequest[T] based on the
        # type of the request and the result.

        pass

    async def _cacheable_request(
        self, request: _CachableRequest[T]
    ) -> _SuccessfulResponse[T] | _FailedRequestBase[T]:
        """Perform a cacheable HTTP request and return the corresponding intermediate response."""
        # This method would use:
        # self.cache to check for cached responses
        #  - return _SuccessfulResponse[T] if a valid cached response is found
        #  - call self._http_request(request) if no valid cached response is found
        #    - use _RequestFromStaleCache[T] if the cached response is stale and needs to be refreshed
        #  - process the response to determine if it should be cached or if it indicates a failure

        pass

    def _is_paged_response(self, response: _SuccessfulResponse[T]) -> bool:
        """Determine if the response is a paged response."""
        # This method would inspect the response to determine if it is a paged response.
        # It would return True if the response indicates that there are additional pages
        # of data to be retrieved, and False otherwise.

        pass

    async def _handle_paged_response(
        self, response: _SuccessfulResponse[T]
    ) -> _SuccessfulResponse[T] | _FailedRequestBase[T]:
        """Handle a paged response and return consolidated response."""
        # This method would handle the logic for retrieving additional pages of data
        # if the response is a paged response. It would use self._http_request to
        # retrieve additional pages and consolidate the results into a single response.
        # It also checks for source change in the middle of retrieving pages.
        #  - if the source changes during requests, it should return a _FailedRequestBase[T]
        #  - check method to be defined later.

        pass
