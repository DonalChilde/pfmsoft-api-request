"""Request orchestration module for batched API execution.

This module is the request-processing boundary for the package. It is responsible
for orchestrating cache access, rate-limited network execution, pagination, and
normalization into public response models.

Operational contracts:

1. Context lifecycle:
        - `ApiRequester` must be used as an async context manager.
        - Entering the context initializes HTTP client, cache, and rate limiter.
        - Exiting the context always closes cache and HTTP client resources.

2. Batch semantics:
        - `process_requests` accepts a mapping of request ids to `Request` instances.
        - Results are returned as a mapping with the same request ids.
        - A request-level failure should not fail unrelated requests unless the failure
            is classified as fatal.

3. Failure policy:
        - Mixed failure mode is used.
        - Recoverable or expected request failures are returned as `FailedResponse`.
        - Fatal infrastructure/configuration failures raise and abort batch processing.
        - Initial recoverable HTTP status seeds include 400, 404, and 429.
        - Initial unrecoverable HTTP status seeds include 401, 403, 500, 502,
            503, and 504.
        - Status and exception classification are centralized in helper methods.

4. HTTP status handling:
        - Success classification is implemented with `match` for easy policy changes.
        - In the initial policy, only 2xx status codes are treated as successful
            terminal responses.
        - 304 is handled as a special cache-revalidation outcome for stale cache flows.

5. Cache behavior:
        - Requests with `cache_key is None` bypass cache.
        - Requests with `cache_key` present are cacheable and may return from cache.
        - Stale cached entries are revalidated with conditional request headers.
        - Revalidation should send both `If-None-Match` and `If-Modified-Since` when
            source metadata is available.
        - 304 on revalidation keeps cached body and refreshes metadata/expiry.
        - 200 on revalidation replaces cached body and metadata.

6. Rate limiting:
        - Every network call is executed under `rate_limiter.limit(...)`.
        - Subject selection for limiter grouping is derived from request data and may
            include `None` depending on protocol evolution.

7. Pagination:
        - Pagination detection is metadata-driven (`X-Pages` semantics).
        - Additional pages are fetched only for successful page-eligible responses.
        - Page-body merge is delegated to a dedicated helper function so merge
            behavior can be replaced independently.
        - Initial merge policy concatenates JSON list payloads.
        - If source consistency checks fail during paging, the request is failed.

8. Source consistency checks:
        - Paged responses must be checked for source changes using response metadata
            (for example `Last-Modified` drift).
        - Source drift is treated as a request-level failure to avoid mixed snapshots.

9. Intermediate model usage:
        - Internal `_Intermediate*` models are implementation details and not part of
            the public package API.
        - Public output is always normalized to `Response` or `FailedResponse`.
"""

import asyncio
import logging
from collections.abc import Hashable
from dataclasses import replace
from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID

from httpx2 import AsyncClient
from httpx2 import Response as HttpResponse
from whenever import Instant

from api_request.cache.models import CachedResponse
from api_request.cache.protocols import CacheFactory, CacheProtocol
from api_request.helpers import json_io
from api_request.helpers.http_session_factory import config_async_http_client
from api_request.rate_limit.protocols import (
    RateLimiterFactoryProtocol,
    RateLimiterProtocol,
)
from api_request.request.intermediate_models import (
    CachableRequest,
    FailedRequestBase,
    FailNoResponse,
    FailWithResponse,
    IntermediateResponseBase,
    RequestFromStaleCache,
    Response200FromStaleCache,
    Response304FromStaleCache,
    SuccessfulResponse,
    SuccessfulResponseBase,
    UnprocessedRequest,
)
from api_request.request.models import (
    FailedResponse,
    Request,
    Response,
    ResponseMetadata,
    ResponseMetadataRoot,
    Source,
)
from api_request.request.protocols import (
    ApiRequesterProtocol,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ApiRequester[T: Hashable](ApiRequesterProtocol[T]):
    """Orchestrates cache-aware and rate-limited API request execution."""

    _RECOVERABLE_HTTP_STATUSES = frozenset({400, 404, 429})
    """Recoverable HTTP status seeds for request-level failures.

    Keep this intentionally small and explicit at first, then extend based on
    endpoint behavior and test coverage.
    """

    _UNRECOVERABLE_HTTP_STATUSES = frozenset({401, 403, 500, 502, 503, 504})
    """Unrecoverable HTTP status seeds for request-level failures.

    These statuses are considered non-retryable by the current request flow.
    They still map to request-scoped failures rather than process-wide fatal
    exceptions.
    """

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

    @classmethod
    def _is_success_status(cls, status_code: int) -> bool:
        """Return True when a status code is a terminal success for normal flow.

        This function intentionally uses `match` so policy can be altered with
        localized edits.
        """
        match status_code:
            case code if 200 <= code < 300:
                return True
            case _:
                return False

    @classmethod
    def _is_recoverable_status(cls, status_code: int) -> bool:
        """Return True when a status code should map to `FailedResponse`.

        The initial policy is explicit (`400`, `404`, `429`) and can be expanded
        by adding values to `_RECOVERABLE_HTTP_STATUSES`.
        """
        match status_code:
            case code if code in cls._RECOVERABLE_HTTP_STATUSES:
                return True
            case _:
                return False

    @classmethod
    def _is_unrecoverable_status(cls, status_code: int) -> bool:
        """Return True when a status code is a known unrecoverable failure.

        The initial policy is explicit (`401`, `403`, `500`, `502`, `503`,
        `504`) and can be expanded by adding values to
        `_UNRECOVERABLE_HTTP_STATUSES`.
        """
        match status_code:
            case code if code in cls._UNRECOVERABLE_HTTP_STATUSES:
                return True
            case _:
                return False

    @classmethod
    def _is_known_failure_status(cls, status_code: int) -> bool:
        """Return True when a status code is in the explicit failure policy."""
        match status_code:
            case code if cls._is_recoverable_status(code):
                return True
            case code if cls._is_unrecoverable_status(code):
                return True
            case _:
                return False

    @staticmethod
    def _is_fatal_exception(exc: Exception) -> bool:
        """Return True when an exception should fail-fast the whole batch.

        Fatal errors represent infrastructure/configuration/programming defects.
        Request-scoped network and HTTP problems should be converted to
        request-level failures instead.
        """
        match exc:
            case RuntimeError():
                return True
            case _:
                return False

    @staticmethod
    def _http_response_to_metadata(response: HttpResponse) -> ResponseMetadata:
        """Convert an HTTP client response to package response metadata."""
        bytes_downloaded = getattr(
            response,
            "num_bytes_downloaded",
            len(getattr(response, "content", b"")),
        )
        return ResponseMetadata(
            status_code=response.status_code,
            reason_phrase=response.reason_phrase,
            url=str(response.url),
            elapsed=int(response.elapsed.total_seconds() * 1_000_000),
            bytes_downloaded=bytes_downloaded,
            headers=tuple(response.headers.items()),
            received_timestamp=Instant.now().timestamp_nanos(),
        )

    @staticmethod
    def _cached_metadata(cached_response: CachedResponse) -> ResponseMetadata:
        """Decode cached metadata bytes into a ResponseMetadata model."""
        return ResponseMetadataRoot.model_validate_json(
            cached_response.response_metadata_json
        ).root

    @staticmethod
    def _updated_request_headers(request: Request[T], **headers: str) -> Request[T]:
        """Return a copy of request with additional/overridden headers."""
        merged_headers = dict(request.headers)
        merged_headers.update(headers)
        return replace(request, headers=merged_headers)

    @staticmethod
    def _as_cached_response(
        *,
        cache_key: UUID,
        text: str,
        metadata: ResponseMetadata,
        etag: str | None = None,
    ) -> CachedResponse:
        """Build a cache model from response primitives."""
        return CachedResponse(
            cache_key=cache_key,
            response_text=text,
            response_metadata_json=metadata.as_bytes,
            etag=etag if etag is not None else metadata.etag,
            expires_at=metadata.expires_at,
            timestamped=Instant.now().timestamp_nanos(),
        )

    @staticmethod
    def _merge_paged_json_lists(first_text: str, other_texts: list[str]) -> str:
        """Merge paged JSON list payloads by concatenating array elements."""
        merged: list[object] = []
        all_texts = [first_text, *other_texts]
        for text in all_texts:
            payload: Any = json_io.json_loads(text)
            if not isinstance(payload, list):
                raise ValueError("Paged response body is not a JSON list")
            merged.extend(cast(list[object], payload))
        return json_io.json_dumps(merged)

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

        responses: dict[UUID, Response[T] | FailedResponse[T]] = {}
        for request_id, intermediate in intermediate_responses.items():
            match intermediate:
                case SuccessfulResponseBase():
                    responses[request_id] = Response(
                        metadata=intermediate.metadata,
                        text=intermediate.text,
                        request=intermediate.request,
                        source=intermediate.source,
                    )
                case FailWithResponse():
                    responses[request_id] = FailedResponse(
                        metadata=intermediate.metadata,
                        text=intermediate.text,
                        request=intermediate.request,
                        error_messages=[
                            f"HTTP {intermediate.metadata.status_code} {intermediate.metadata.reason_phrase}"
                        ],
                    )
                case FailNoResponse():
                    responses[request_id] = FailedResponse(
                        request=intermediate.request,
                        error_messages=[intermediate.error_message],
                    )
                case _:
                    responses[request_id] = FailedResponse(
                        request=requests[request_id],
                        error_messages=["Unknown intermediate response type"],
                    )
        return responses

    async def _dispatch_requests(
        self,
        requests: dict[UUID, Request[T]],
    ) -> dict[UUID, IntermediateResponseBase[T]]:
        """Dispatch a batch of API requests and return their corresponding intermediate responses."""

        async def execute(request: Request[T]) -> IntermediateResponseBase[T]:
            try:
                if request.cache_key is None:
                    return await self._http_request(UnprocessedRequest(request=request))
                return await self._cacheable_request(
                    CachableRequest(request=request, cache_key=request.cache_key)
                )
            except Exception as exc:  # noqa: BLE001
                if self._is_fatal_exception(exc):
                    raise
                return FailNoResponse(request=request, error_message=str(exc))

        task_keys = list(requests.keys())
        task_values = [asyncio.create_task(execute(requests[k])) for k in task_keys]
        results = await asyncio.gather(*task_values)
        return {task_keys[i]: results[i] for i in range(len(task_keys))}

    async def _http_request(
        self,
        request: UnprocessedRequest[T],
        *,
        allow_pagination: bool = True,
        expected_success_statuses: set[int] | None = None,
    ) -> SuccessfulResponseBase[T] | FailedRequestBase[T]:
        """Perform an HTTP request and return the corresponding intermediate response."""
        session = await self.session
        rate_limiter = await self.rate_limiter
        outgoing_headers = request.request.headers
        if isinstance(request, RequestFromStaleCache):
            outgoing_headers = {
                **request.request.headers,
                **request.conditional_headers,
            }
        try:
            async with rate_limiter.limit(request.request.rate_key):
                http_response = await session.request(
                    method=request.request.method,
                    url=request.request.url,
                    headers=outgoing_headers,
                    params=request.request.parameters,
                    json=request.request.body,
                )
        except Exception as exc:  # noqa: BLE001
            if self._is_fatal_exception(exc):
                raise
            return FailNoResponse(request=request.request, error_message=str(exc))

        metadata = self._http_response_to_metadata(http_response)
        text = http_response.text
        status_code = metadata.status_code

        is_explicit_success = (
            expected_success_statuses is not None
            and status_code in expected_success_statuses
        )
        if is_explicit_success or self._is_success_status(status_code):
            success = SuccessfulResponse(
                request=request.request,
                metadata=metadata,
                text=text,
                source=Source.NETWORK,
            )
            if (
                allow_pagination
                and self._is_success_status(status_code)
                and self._is_paged_response(success)
            ):
                return await self._handle_paged_response(success)
            return success

        if self._is_known_failure_status(status_code):
            return FailWithResponse(
                request=request.request, metadata=metadata, text=text
            )

        return FailWithResponse(request=request.request, metadata=metadata, text=text)

    async def _cacheable_request(
        self, request: CachableRequest[T]
    ) -> SuccessfulResponseBase[T] | FailedRequestBase[T]:
        """Perform a cacheable HTTP request and return the corresponding intermediate response."""
        cache = await self.cache
        cached_response = await cache.get(request.cache_key)

        if cached_response is None:
            response = await self._http_request(
                UnprocessedRequest(request=request.request),
            )
            if isinstance(response, SuccessfulResponseBase):
                await cache.set(
                    request.cache_key,
                    self._as_cached_response(
                        cache_key=request.cache_key,
                        text=response.text,
                        metadata=response.metadata,
                    ),
                )
            return response

        cached_metadata = self._cached_metadata(cached_response)
        if not cached_response.is_expired:
            return SuccessfulResponse(
                request=request.request,
                metadata=cached_metadata,
                text=cached_response.response_text,
                source=Source.CACHE,
            )

        stale_request = RequestFromStaleCache(
            request=request.request,
            cache_key=request.cache_key,
            etag=cached_response.etag,
            last_modified=cached_metadata.last_modified,
        )
        refreshed = await self._http_request(
            stale_request,
            allow_pagination=True,
            expected_success_statuses={200, 304},
        )
        if isinstance(refreshed, FailedRequestBase):
            return refreshed

        match refreshed.metadata.status_code:
            case 304:
                metadata_refresh = self._as_cached_response(
                    cache_key=request.cache_key,
                    text=cached_response.response_text,
                    metadata=refreshed.metadata,
                    etag=cached_response.etag,
                )
                await cache.update(request.cache_key, metadata_refresh)
                return Response304FromStaleCache(
                    request=request.request,
                    metadata=refreshed.metadata,
                    text=cached_response.response_text,
                )
            case 200:
                replacement = self._as_cached_response(
                    cache_key=request.cache_key,
                    text=refreshed.text,
                    metadata=refreshed.metadata,
                )
                await cache.update(request.cache_key, replacement)
                return Response200FromStaleCache(
                    request=request.request,
                    metadata=refreshed.metadata,
                    text=refreshed.text,
                )
            case _:
                return FailWithResponse(
                    request=request.request,
                    metadata=refreshed.metadata,
                    text=refreshed.text,
                )

    def _is_paged_response(self, response: SuccessfulResponse[T]) -> bool:
        """Determine if the response is a paged response."""
        return response.metadata.status_code == 200 and response.metadata.pages > 1

    async def _handle_paged_response(
        self, response: SuccessfulResponse[T]
    ) -> SuccessfulResponseBase[T] | FailedRequestBase[T]:
        """Handle a paged response and return consolidated response."""
        total_pages = response.metadata.pages
        if total_pages <= 1:
            return response

        paged_responses: list[SuccessfulResponseBase[T]] = []
        page_responses = await self._gather_paged_responses(response)
        for page_response in page_responses:
            if isinstance(page_response, FailedRequestBase):
                return page_response
            paged_responses.append(page_response)

        if self._has_source_changed(response, paged_responses):
            return FailNoResponse(
                request=response.request,
                error_message=(
                    "Detected source data change while collecting paged response; "
                    "aborting merge"
                ),
            )

        try:
            merged_text = self._merge_paged_json_lists(
                response.text,
                [item.text for item in paged_responses],
            )
        except Exception as exc:  # noqa: BLE001
            return FailNoResponse(request=response.request, error_message=str(exc))

        return SuccessfulResponse(
            request=response.request,
            metadata=response.metadata,
            text=merged_text,
            source=response.source,
        )

    async def _gather_paged_responses(
        self, response: SuccessfulResponse[T]
    ) -> list[SuccessfulResponseBase[T] | FailedRequestBase[T]]:
        """Fetch all additional pages for a paged response concurrently."""
        return await asyncio.gather(
            *(
                self._http_request(
                    self._build_paged_request(response, page_number),
                    allow_pagination=False,
                )
                for page_number in range(2, response.metadata.pages + 1)
            )
        )

    @staticmethod
    def _build_paged_request(
        response: SuccessfulResponse[T],
        page_number: int,
    ) -> UnprocessedRequest[T]:
        """Build a request for one additional paged response."""
        return UnprocessedRequest(
            request=replace(
                response.request,
                parameters={
                    **response.request.parameters,
                    "page": page_number,
                },
            )
        )

    def _has_source_changed(
        self,
        first_response: SuccessfulResponseBase[T],
        paged_responses: list[SuccessfulResponseBase[T]],
    ) -> bool:
        """Check if the data on the server has changed between the first and subsequent paged responses."""
        # If the last-modified header for the first response does not match the last-modified header
        # for any of the subsequent paged responses, return True indicating that the data has changed.
        # Otherwise, return False.

        first_last_modified = first_response.metadata.last_modified
        for response in paged_responses:
            if response.metadata.last_modified != first_last_modified:
                return True
        return False
