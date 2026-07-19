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
        - Non-success HTTP responses are returned as request-scoped
            `FailedResponse` values by default.
        - Fatal infrastructure/configuration failures raise and abort batch
            processing.
        - Optional `force_fail_on` status codes trigger a shared fail flag that
            causes subsequent/in-flight requests to short-circuit as
            request-level failures.

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
from dataclasses import replace
from time import perf_counter
from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID

from httpx2 import AsyncClient
from httpx2 import Response as HttpResponse
from whenever import Instant

from pfmsoft.api_request.cache.models import CachedResponse
from pfmsoft.api_request.cache.protocols import CacheFactory, CacheProtocol
from pfmsoft.api_request.helpers import json_io
from pfmsoft.api_request.helpers.http_session_factory import config_async_http_client
from pfmsoft.api_request.rate_limit.protocols import (
    RateLimiterFactoryProtocol,
    RateLimiterProtocol,
)
from pfmsoft.api_request.request.intermediate_models import (
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
from pfmsoft.api_request.request.models import (
    FailedResponse,
    Request,
    Requests,
    Response,
    ResponseMetadata,
    ResponseMetadataRoot,
    Responses,
    Source,
)
from pfmsoft.api_request.request.protocols import (
    ApiRequesterProtocol,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ForcedFailureError(Exception):
    """Internal control-flow error used by forced-failure signaling.

    This exception communicates that request processing should short-circuit
    because a force-fail status condition was reached.
    """

    def __init__(
        self,
        request: Request,
        response_json: Any | None = None,
        response_metadata: ResponseMetadata | None = None,
        from_flag: bool = False,
    ) -> None:
        """Initialize forced-failure error state with request context."""
        self.request = request
        self.response_json = response_json
        self.response_metadata = response_metadata
        self.from_other_failure_flag = from_flag
        if self.from_other_failure_flag:
            super().__init__(
                f"ForcedFailureError: Forced failure triggered for request "
                f"{request.request_key} due to failure of another request."
            )
        else:
            super().__init__(
                f"ForcedFailureError: Forced failure triggered for request "
                f"{request.request_key} with response status code: "
                f"{response_metadata.status_code if response_metadata else None}."
            )


class ApiRequester(ApiRequesterProtocol):
    """Orchestrates cache-aware and rate-limited API request execution."""

    def __init__(
        self,
        cache_factory: CacheFactory,
        rate_limiter_factory: RateLimiterFactoryProtocol,
        force_fail_on: set[int] | None = None,
    ) -> None:
        """Initialize requester dependencies and optional forced-failure policy.

        Args:
            cache_factory: Callable that builds one cache instance per requester
                context.
            rate_limiter_factory: Callable that builds one rate-limiter instance
                per requester context.
            force_fail_on: Optional set of HTTP status codes that trigger the
                shared forced-failure flag.
        """
        self._client: AsyncClient | None = None
        self._cache: CacheProtocol | None = None
        self._rate_limit: RateLimiterProtocol | None = None
        self._cache_factory = cache_factory
        self._rate_limiter_factory = rate_limiter_factory
        self._force_fail_on = force_fail_on or set()
        """A set of HTTP status codes that will trigger a forced failure for the entire batch."""
        self._force_failure: bool = False

    def _check_force_failure_flag(self, request: Request) -> None:
        """Raise forced-failure control-flow error when shared flag is set."""
        if self._force_failure:
            raise ForcedFailureError(request=request, from_flag=True)

    def _check_response_for_force_failure(
        self, request: Request, response_json: Any, response_metadata: ResponseMetadata
    ) -> None:
        """Activate forced-failure signaling when configured status is observed."""
        if response_metadata.status_code in self._force_fail_on:
            self._force_failure = True
            raise ForcedFailureError(
                request=request,
                response_json=response_json,
                response_metadata=response_metadata,
            )

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

    def _is_fatal_exception(self, exc: Exception) -> bool:
        """Return True when an exception should fail-fast the whole batch.

        Fatal errors represent infrastructure/configuration/programming defects.
        Request-scoped network and HTTP problems should be converted to
        request-level failures instead.
        """
        match exc:
            case RuntimeError():
                self._force_failure = True
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
        """Decode cached metadata JSON text into a ResponseMetadata model."""
        return ResponseMetadataRoot.model_validate_json(
            cached_response.response_metadata_json
        ).root

    @staticmethod
    def _updated_request_headers(request: Request, **headers: str) -> Request:
        """Return a copy of request with additional/overridden headers."""
        merged_headers = dict(request.headers)
        merged_headers.update(headers)
        return replace(request, headers=merged_headers)

    @staticmethod
    def _merge_paged_json_lists(first_json: Any, other_jsons: list[Any]) -> list[Any]:
        """Merge paged JSON list payloads by concatenating array elements."""
        merged: list[object] = []
        all_payloads = [first_json, *other_jsons]
        for payload in all_payloads:
            if not isinstance(payload, list):
                raise ValueError("Paged response body is not a JSON list")
            merged.extend(cast(list[object], payload))
        return merged

    async def __aenter__(self) -> Self:
        """Enter context and initialize HTTP client, cache, and rate limiter."""
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
        """Exit context and release managed resources."""
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

    async def _rate_limit_check(self) -> RateLimiterProtocol:
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
    async def rate_limiter(self) -> RateLimiterProtocol:
        """Get the rate limiter instance."""
        return await self._rate_limit_check()

    @property
    async def session(self) -> AsyncClient:
        """Get the HTTP client instance."""
        return await self._session_check()

    async def process_requests(
        self,
        requests: Requests,
        purge_secrets: bool = True,
    ) -> Responses:
        """Process a request batch and normalize outcomes into public models.

        The input mapping keys are preserved across output `successful` and
        `failed` maps.

        Access tokens are optionally purged from all responses for security purposes
        before returning.

        Args:
            requests: Mapping of request ids to `Request` instances.
            purge_secrets: Whether to purge access tokens from response metadata
                before returning. Defaults to True.

        Returns:
            Responses: A mapping of request ids to either `Response` or `FailedResponse`
                instances.
        """
        self._force_failure = False
        intermediate_responses = await self._dispatch_requests(requests)

        successful: dict[UUID, Response] = {}
        failed: dict[UUID, FailedResponse] = {}
        for request_id, intermediate in intermediate_responses.items():
            match intermediate:
                case SuccessfulResponseBase():
                    response = Response(
                        metadata=intermediate.metadata,
                        json=intermediate.json,
                        request=intermediate.request,
                        source=intermediate.source,
                    )
                    self._check_purge_secrets(purge_secrets, response)
                    successful[request_id] = response

                case FailWithResponse():
                    response = FailedResponse(
                        metadata=intermediate.metadata,
                        json=intermediate.json,
                        request=intermediate.request,
                        error_messages=[
                            f"HTTP {intermediate.metadata.status_code} {intermediate.metadata.reason_phrase}"
                        ],
                    )
                    self._check_purge_secrets(purge_secrets, response)
                    failed[request_id] = response
                case FailNoResponse():
                    response = FailedResponse(
                        request=intermediate.request,
                        error_messages=[intermediate.error_message],
                    )
                    self._check_purge_secrets(purge_secrets, response)
                    failed[request_id] = response
                case _:
                    response = FailedResponse(
                        request=requests[request_id],
                        error_messages=["Unknown intermediate response type"],
                    )
                    self._check_purge_secrets(purge_secrets, response)
                    failed[request_id] = response
        return Responses(successful=successful, failed=failed)

    def _check_purge_secrets(
        self, do_purge: bool, response: Response | FailedResponse
    ) -> None:
        """Purge access tokens from response metadata for security purposes."""
        if do_purge:
            response.purge_secrets()

    async def _dispatch_requests(
        self,
        requests: Requests,
    ) -> dict[UUID, IntermediateResponseBase]:
        """Dispatch batch requests concurrently and collect intermediate results."""

        async def execute(request: Request) -> IntermediateResponseBase:
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
        request: UnprocessedRequest,
        *,
        allow_pagination: bool = True,
        expected_success_statuses: set[int] | None = None,
    ) -> SuccessfulResponseBase | FailedRequestBase:
        """Perform one network request and classify the intermediate outcome.

        Args:
            request: Request wrapper to execute.
            allow_pagination: Whether page fan-out is allowed for successful
                page-eligible responses.
            expected_success_statuses: Optional explicit success status override
                set (for example `{304}` during stale-cache revalidation).
        """
        session = await self.session
        rate_limiter = await self.rate_limiter
        outgoing_headers = request.request.headers
        if isinstance(request, RequestFromStaleCache):
            outgoing_headers = {
                **request.request.headers,
                **request.conditional_headers,
            }
        try:
            # Check for forced failure before making the request
            self._check_force_failure_flag(request.request)
            async with rate_limiter.limit(request.request.rate_key):
                # Check for forced failure after passing the rate limit gate
                self._check_force_failure_flag(request.request)
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
        response_text = http_response.text
        parsed_json: Any | None = None
        if response_text != "":
            try:
                parsed_json = json_io.json_loads(response_text)
            except Exception as exc:  # noqa: BLE001
                return FailNoResponse(
                    request=request.request,
                    error_message=f"Failed to parse response JSON: {exc}",
                )
        status_code = metadata.status_code

        is_explicit_success = (
            expected_success_statuses is not None
            and status_code in expected_success_statuses
        )
        if is_explicit_success or self._is_success_status(status_code):
            success = SuccessfulResponse(
                request=request.request,
                metadata=metadata,
                json=parsed_json,
                source=Source.NETWORK,
            )
            if (
                allow_pagination
                and self._is_success_status(status_code)
                and self._is_paged_response(success)
            ):
                return await self._handle_paged_response(success)
            return success
        # Check for the need for forced failure based on the response status code and
        # the configured force_fail_on set
        self._check_response_for_force_failure(
            request.request, response_json=parsed_json, response_metadata=metadata
        )

        return FailWithResponse(
            request=request.request,
            metadata=metadata,
            json=parsed_json,
        )

    async def _cacheable_request(
        self, request: CachableRequest
    ) -> SuccessfulResponseBase | FailedRequestBase:
        """Perform one cache-aware request flow.

        Behavior:
            - Missing cache entry: execute network request and cache success.
            - Fresh cache entry: return cached body/metadata.
            - Stale cache entry: revalidate with conditional headers and update
              cache on `304` or `200` outcomes.
        """
        cache = await self.cache
        cached_response = await cache.get(request.cache_key)

        if cached_response is None:
            response = await self._http_request(
                UnprocessedRequest(request=request.request),
            )
            if isinstance(response, SuccessfulResponseBase):
                await cache.set(
                    request.cache_key,
                    json_io.json_dumps(response.json),
                    response.metadata,
                )
            return response

        cached_metadata = self._cached_metadata(cached_response)
        if not cached_response.is_expired:
            return SuccessfulResponse(
                request=request.request,
                metadata=cached_metadata,
                json=json_io.json_loads(cached_response.response_text),
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
                refreshed_cached_response = await cache.update_304(
                    request.cache_key,
                    refreshed.metadata,
                )
                return Response304FromStaleCache(
                    request=request.request,
                    metadata=self._cached_metadata(refreshed_cached_response),
                    json=json_io.json_loads(refreshed_cached_response.response_text),
                )
            case 200:
                await cache.set(
                    request.cache_key,
                    json_io.json_dumps(refreshed.json),
                    refreshed.metadata,
                )
                return Response200FromStaleCache(
                    request=request.request,
                    metadata=refreshed.metadata,
                    json=refreshed.json,
                )
            case _:
                return FailWithResponse(
                    request=request.request,
                    metadata=refreshed.metadata,
                    json=refreshed.json,
                )

    def _is_paged_response(self, response: SuccessfulResponse) -> bool:
        """Return True when response is a successful multi-page payload."""
        return response.metadata.status_code == 200 and response.metadata.pages > 1

    async def _handle_paged_response(
        self, response: SuccessfulResponse
    ) -> SuccessfulResponseBase | FailedRequestBase:
        """Collect additional pages and return a merged successful response.

        If any page fetch fails, or source consistency checks fail, a
        request-scoped failure is returned.
        """
        total_pages = response.metadata.pages
        if total_pages <= 1:
            return response

        paged_responses: list[SuccessfulResponseBase] = []
        pages_start = perf_counter()
        page_responses = await self._gather_paged_responses(response)
        pages_end = perf_counter()
        logger.info(
            "Fetched %d pages for request %s in %.2f seconds",
            total_pages,
            response.request.url,
            pages_end - pages_start,
        )
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
            merged_json = self._merge_paged_json_lists(
                response.json,
                [item.json for item in paged_responses],
            )
        except Exception as exc:  # noqa: BLE001
            return FailNoResponse(request=response.request, error_message=str(exc))

        return SuccessfulResponse(
            request=response.request,
            metadata=response.metadata,
            json=merged_json,
            source=response.source,
        )

    async def _gather_paged_responses(
        self, response: SuccessfulResponse
    ) -> list[SuccessfulResponseBase | FailedRequestBase]:
        """Fetch page 2..N responses concurrently for a paged first response."""
        tasks = (
            self._http_request(
                self._build_paged_request(response, page_number),
                allow_pagination=False,
            )
            for page_number in range(2, response.metadata.pages + 1)
        )
        return await asyncio.gather(*tasks)

    @staticmethod
    def _build_paged_request(
        response: SuccessfulResponse,
        page_number: int,
    ) -> UnprocessedRequest:
        """Build one follow-up paged request by injecting `page` parameter."""
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
        first_response: SuccessfulResponseBase,
        paged_responses: list[SuccessfulResponseBase],
    ) -> bool:
        """Check for paged-source drift using `Last-Modified` consistency."""
        first_last_modified = first_response.metadata.last_modified
        for response in paged_responses:
            if response.metadata.last_modified != first_last_modified:
                return True
        return False
