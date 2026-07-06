"""An implementation of the HttpRequestExecutorProtocol.

Provides caching, rate limiting, and pagination for ESI requests.
"""

import asyncio
import logging
from copy import deepcopy
from dataclasses import asdict, replace
from typing import cast

import httpx2
from aiolimiter import AsyncLimiter
from whenever import Instant

from esi_link.cache.models import (
    CacheAction,
    CachedResponse,
    CachedResponseStatus,
)
from esi_link.cache.sqlite_cache import CacheManagerSqlite
from esi_link.execution.models import HttpResponse, ResponseMetadata
from esi_link.helpers.timedelta_microseconds import in_microseconds
from esi_link.runtime.models import (
    CachedResponseMetrics,
    FailedRuntimeResponse,
    PagedResponseMetrics,
    RuntimeRequest,
    RuntimeRequestMetrics,
    RuntimeResponse,
)

logger = logging.getLogger(__name__)


def _update_stale_cache_headers(
    request: RuntimeRequest, cached_response: CachedResponse
) -> RuntimeRequest:
    """Update the headers of the request to include information about the stale cache response."""
    if not cached_response.is_expired:
        return request
    updated_headers = deepcopy(request.headers)
    etag = cached_response.http_response.etag
    last_modified = cached_response.http_response.last_modified
    if etag:
        updated_headers["If-None-Match"] = etag
    if last_modified:
        updated_headers["If-Modified-Since"] = last_modified

    return replace(request, headers=updated_headers)


async def _make_http_request(
    *,
    request: RuntimeRequest,
    session: httpx2.AsyncClient,
    rate_limiter: AsyncLimiter,
    metrics: RuntimeRequestMetrics,
) -> RuntimeResponse | FailedRuntimeResponse:
    """Execute the HTTP request with rate limiting."""
    metrics.http_request_started = Instant.now().timestamp_nanos()
    # We initialize the response data here so that if an exception is raised during the
    # HTTP request, we can still return a FailedRuntimeResponse with whatever response
    # data we were able to obtain.
    response_data = None
    response_text = ""
    async with rate_limiter:
        query_params = request.query_parameters | request.additional_query_parameters
        http_request = httpx2.Request(
            method=request.method,
            url=request.resolved_path_url,
            headers=request.headers,
            params=query_params,
            json=request.json_body,
        )

        try:
            network_response = await session.send(http_request)
            logger.info(
                f"Made HTTP request to {network_response.url} with method {request.method} and received status code {network_response.status_code}"
            )
            response_text = network_response.text
            headers = tuple(network_response.headers.items())
            response_metadata = ResponseMetadata(
                status_code=network_response.status_code,
                reason_phrase=network_response.reason_phrase,
                url=str(network_response.url),
                elapsed=in_microseconds(network_response.elapsed),
                bytes_downloaded=len(network_response.content),
                headers=headers,
                received_timestamp=Instant.now().timestamp_nanos(),
            )
            response_data = HttpResponse(
                metadata=response_metadata,
                text=network_response.text,
            )
            metrics.http_request_completed = Instant.now().timestamp_nanos()

        except Exception as e:
            logger.error(
                f"HTTP request failed: {e} with response content: {response_text}"
            )
            response = FailedRuntimeResponse(
                http_response=response_data,
                runtime_request=request,
                metrics=metrics,
                failure_msg=str(e),
            )
            return response
        response = RuntimeResponse(
            request_id=request.request_id,
            http_response=response_data,
            metrics=metrics,
        )
        return response


def _fail_on_client_server_errors(
    response: RuntimeResponse | FailedRuntimeResponse, request: RuntimeRequest
) -> RuntimeResponse | FailedRuntimeResponse:
    """Evaluate the HTTP status code of the response.

    This is a first pass detection of a failed HTTP response based on the status code.
    The calling functions are responsible for further narrowing of successful responses.

    We consider any 2xx or 3xx status code to be a successful response, and any 4xx or
    5xx status code to be a failed response. This is because some ESI endpoints return
    3xx status codes for valid responses, and we want to allow those to be treated as
    successful responses. However, we still want to log an error for any 4xx or 5xx
    status codes, and return a FailedRuntimeResponse to the caller so that they can
    handle it appropriately.

    """
    if isinstance(response, FailedRuntimeResponse):
        return response
    code = response.http_response.status_code
    match code:
        case code if 200 <= code < 300:
            # Successful response, we can proceed as normal
            return response
        case code if 300 <= code < 400:
            # Successful response, we can proceed as normal.
            return response
        case code if 400 <= code < 600:
            # Client error response, log an error but still return the response data to the caller
            logger.error(
                "Received %s - %s for request %s.",
                response.http_response.status_code,
                response.http_response.reason_phrase,
                response.http_response.url,
            )
            return FailedRuntimeResponse(
                http_response=response.http_response,
                runtime_request=request,
                metrics=response.metrics,
                failure_msg=f"Received {response.http_response.status_code} - {response.http_response.reason_phrase}",
            )
        case _:
            logger.error(
                "Received unexpected status code %s for request %s",
                response.http_response.status_code,
                response.http_response.url,
            )
            return FailedRuntimeResponse(
                http_response=response.http_response,
                runtime_request=request,
                metrics=response.metrics,
                failure_msg=f"Received unexpected status code {code}",
            )


async def _check_for_additional_pages_and_fetch(
    *,
    response: RuntimeResponse,
    request: RuntimeRequest,
    session: httpx2.AsyncClient,
    rate_limiter: AsyncLimiter,
) -> RuntimeResponse | FailedRuntimeResponse:
    """Check if the response indicates that there are additional pages of data to fetch, and if so, fetch them and combine them into a single response."""
    additional_requests = await _create_additional_page_requests(
        total_pages=response.http_response.pages, request=request
    )
    if not additional_requests:
        return response
    paged_metrics = PagedResponseMetrics(
        additional_pages_count=len(additional_requests)
    )
    response.metrics.page_metrics = paged_metrics
    paged_metrics.paged_requests_start = Instant.now().timestamp_nanos()

    additional_responses = await asyncio.gather(
        *[
            _make_http_request(
                request=request,
                session=session,
                rate_limiter=rate_limiter,
                metrics=RuntimeRequestMetrics(),
            )
            for request in additional_requests
        ]
    )
    paged_metrics.paged_requests_completed = Instant.now().timestamp_nanos()
    for paged_response in additional_responses:
        if isinstance(paged_response, FailedRuntimeResponse):
            logger.error(
                f"Failed to fetch additional page for request {request.resolved_path_url}: {paged_response.failure_msg}"
            )
            return FailedRuntimeResponse(
                http_response=response.http_response,
                runtime_request=request,
                metrics=response.metrics,
                failure_msg=f"Failed to fetch additional page: {paged_response.failure_msg}",
            )
    # At this point, we have successfully fetched all additional pages, so we
    # can combine the responses into a single response to return to the caller
    additional_responses = cast(list[RuntimeResponse], additional_responses)
    try:
        _check_for_valid_paged_responses(response, additional_responses)
        combined_response = _combine_paged_responses(response, additional_responses)
    except Exception as e:
        logger.error(
            "Invalid paged responses for request url %s: %s",
            request.resolved_path_url,
            e,
        )
        return FailedRuntimeResponse(
            http_response=response.http_response,
            runtime_request=request,
            metrics=response.metrics,
            failure_msg=f"Invalid paged responses: {str(e)}",
        )

    return combined_response


async def execute_http_request(
    request: RuntimeRequest,
    session: httpx2.AsyncClient,
    rate_limiter: AsyncLimiter,
    web_cache: CacheManagerSqlite | None,
) -> RuntimeResponse | FailedRuntimeResponse:
    """Execute the HTTP request with rate limiting and optional caching.

    Args:
        request: The RuntimeRequest to execute.
        session: The httpx2.AsyncClient to use for making the HTTP request.
        rate_limiter: The AsyncLimiter to use for rate limiting the HTTP request.
        web_cache: The CacheManagerSqlite to use for caching the HTTP response.
            If None, caching will be disabled and the request will be executed directly
            without checking the cache.

    Returns:
        A RuntimeResponse if the request was successful, or a FailedRuntimeResponse if the
        request failed.
    """
    metrics = RuntimeRequestMetrics()
    metrics.task_started = Instant.now().timestamp_nanos()
    if web_cache is None:
        response = await _fetch_response(
            request=request, session=session, rate_limiter=rate_limiter, metrics=metrics
        )
        return response
    if request.cache_key is not None:
        response = await _fetch_response_with_cache(
            request=request,
            session=session,
            rate_limiter=rate_limiter,
            metrics=metrics,
            web_cache=web_cache,
        )
    else:
        response = await _fetch_response(
            request=request, session=session, rate_limiter=rate_limiter, metrics=metrics
        )
    metrics.task_completed = Instant.now().timestamp_nanos()
    return response


async def _fetch_response(
    *,
    request: RuntimeRequest,
    session: httpx2.AsyncClient,
    rate_limiter: AsyncLimiter,
    metrics: RuntimeRequestMetrics,
) -> RuntimeResponse | FailedRuntimeResponse:
    """Execute the HTTP request with rate limiting, including handling of paged responses."""
    response = await _make_http_request(
        request=request, session=session, rate_limiter=rate_limiter, metrics=metrics
    )
    response = _fail_on_client_server_errors(response, request)
    if isinstance(response, FailedRuntimeResponse):
        return response
    if response.http_response.status_code == 200 and request.is_paged:
        # only 200 responses should be considered valid for pagination.
        response = await _check_for_additional_pages_and_fetch(
            response=response,
            request=request,
            session=session,
            rate_limiter=rate_limiter,
        )
    return response


async def _fetch_response_with_cache(
    *,
    request: RuntimeRequest,
    session: httpx2.AsyncClient,
    rate_limiter: AsyncLimiter,
    metrics: RuntimeRequestMetrics,
    web_cache: CacheManagerSqlite,
) -> RuntimeResponse | FailedRuntimeResponse:
    cache_key = request.cache_key
    if cache_key is None:
        raise ValueError(
            f"Cache key is None for request {request.resolved_path_url}, cannot execute with cache"
        )
    cache_metrics = CachedResponseMetrics()
    metrics.cache_metrics = cache_metrics

    # Check the cache for a cached response for this request
    cache_metrics.cache_check_started = Instant.now().timestamp_nanos()
    cached_response = await web_cache.get(cache_key)
    cache_metrics.cache_check_completed = Instant.now().timestamp_nanos()

    if cached_response is None:
        # Cache miss - no cached response found for this cache key
        metrics.cache_status = CachedResponseStatus.MISS
        logger.info(
            "Cache miss (not found) for request %s with cache key %s",
            request.resolved_path_url,
            cache_key,
        )
        response = await _fetch_response(
            request=request,
            session=session,
            rate_limiter=rate_limiter,
            metrics=metrics,
        )
        if isinstance(response, FailedRuntimeResponse):
            logger.error(
                f"HTTP request failed, cache not updated for {request.resolved_path_url} with cache key {cache_key}: {response.failure_msg}"
            )
            return response
        cache_metrics.cache_action_started = Instant.now().timestamp_nanos()
        metrics.cache_action = CacheAction.ADDED_TO_CACHE
        await web_cache.set(cache_key, response.http_response)
        cache_metrics.cache_action_completed = Instant.now().timestamp_nanos()
        logger.info(
            f"Cached response for request {response.http_response.url} with cache key {cache_key}, expires at {response.http_response.expires_at}"
        )
        return response

    if cached_response.is_expired:
        # Cache miss - cached response is expired
        logger.info(
            f"Cache miss (stale) for request {cached_response.http_response.url} with "
            f"cache key {cache_key}"
        )
        request = _update_stale_cache_headers(request, cached_response)
        metrics.cache_status = CachedResponseStatus.STALE
        response = await _fetch_response(
            request=request, session=session, rate_limiter=rate_limiter, metrics=metrics
        )
        if isinstance(response, FailedRuntimeResponse):
            logger.error(
                f"HTTP request failed when validating stale cache for {request.resolved_path_url} "
                f"with cache key {cache_key}: {response.failure_msg}."
            )
            return response
        if response.http_response.status_code == 304:
            # Cached response is still valid, refresh the cache with the new response data and return the cached response
            cache_metrics.cache_action_started = Instant.now().timestamp_nanos()
            metrics.cache_action = CacheAction.CACHE_304_REFRESH_METADATA
            cached_response = await web_cache.refresh(cache_key, response.http_response)
            cache_metrics.cache_action_completed = Instant.now().timestamp_nanos()
            logger.info(
                "Refreshed cache for request %s with new response, expires at %s",
                response.http_response.url,
                cached_response.expires_at,
            )
            return RuntimeResponse(
                request_id=request.request_id,
                http_response=cached_response.http_response,
                metrics=metrics,
            )
        elif response.http_response.status_code == 200:
            # We got a new valid response, so we update the cache with the new response and return it
            cache_metrics.cache_action_started = Instant.now().timestamp_nanos()
            metrics.cache_action = CacheAction.ADDED_TO_CACHE
            cached_response = await web_cache.set(cache_key, response.http_response)
            cache_metrics.cache_action_completed = Instant.now().timestamp_nanos()
            logger.info(
                f"Updated cache for request {response.http_response.url} with new response, expires at {cached_response.expires_at}"
            )
            return response
        else:
            logger.warning(
                "Received unexpected status code %s for request %s when validating stale cache.",
                response.http_response.status_code,
                response.http_response.url,
            )
            return FailedRuntimeResponse(
                runtime_request=request,
                http_response=response.http_response,
                metrics=metrics,
                failure_msg=f"Received unexpected status code {response.http_response.status_code} for request "
                f"{response.http_response.url} when validating stale cache.",
            )
    else:
        # Cache hit - cached response is valid
        logger.info(
            f"Cache hit for request {cached_response.http_response.url} with cache key {cache_key}"
        )
        metrics.cache_status = CachedResponseStatus.HIT
        return RuntimeResponse(
            request_id=request.request_id,
            http_response=cached_response.http_response,
            metrics=metrics,
        )


async def _create_additional_page_requests(
    total_pages: int, request: RuntimeRequest
) -> list[RuntimeRequest]:
    """Check if the response.http_response.pages indicates that there are additional pages of data to fetch."""
    if not request.is_paged:
        raise ValueError(
            f"Cannot check for additional pages for a request that is not marked as paged: {request.resolved_path_url}"
        )
    if total_pages <= 1:
        # This is a paged request, but there is only one page of data.
        return []
    additional_requests: list[RuntimeRequest] = []
    for page in range(2, total_pages + 1):
        new_request = deepcopy(request)
        additional_query_parameters = new_request.additional_query_parameters.copy()
        additional_query_parameters["page"] = page
        new_request = replace(
            new_request, additional_query_parameters=additional_query_parameters
        )
        additional_requests.append(new_request)
    return additional_requests


def _combine_paged_responses(
    first_page: RuntimeResponse, paged_responses: list[RuntimeResponse]
) -> RuntimeResponse:
    """Combine the responses from multiple pages of data into a single response."""
    paged_strings = _collect_paged_response_strings(paged_responses)
    combined_string = _combine_paged_response_strings(
        first_page.http_response.text, paged_strings
    )
    updated_http_response = replace(first_page.http_response, text=combined_string)
    return replace(first_page, http_response=updated_http_response)


def _combine_paged_response_strings(first_page: str, paged_strings: list[str]) -> str:
    """Combine the body text from the original response and the paged responses into a single string."""
    # This logic assumes that the body of the response is a JSON array of items,
    # which is true for many ESI endpoints, but may not be universally true.
    # We may need to make this logic more robust in the future.

    if first_page.startswith("[") and first_page.endswith("]"):
        return _combine_list_of_array_strings(first_page, paged_strings)
    else:
        raise ValueError(
            "Cannot combine paged response strings: original string is not a JSON array"
        )


def _combine_list_of_array_strings(first_page: str, paged_strings: list[str]) -> str:
    """Combine the body text from the original response and the paged responses into a single json string list of items."""
    fragments: list[str] = []
    if first_page.startswith("[") and first_page.endswith("]"):
        fragments.append(first_page[1:-1])  # Remove the brackets
        for page_num, paged_string in enumerate(paged_strings, start=2):
            if paged_string.startswith("[") and paged_string.endswith("]"):
                fragments.append(paged_string[1:-1])  # Remove the brackets
            else:
                raise ValueError(
                    f"Cannot combine paged response strings: paged string is not a JSON array: page {page_num}"
                )
        combined_string = f"[{','.join(fragments)}]"  # Add the brackets back
        return combined_string
    else:
        raise ValueError(
            "Cannot combine paged response strings: original string is not a JSON array"
        )


def _collect_paged_response_strings(
    paged_responses: list[RuntimeResponse],
) -> list[str]:
    """Collect the body text from a list of paged responses."""
    response_strings: list[str] = []
    for paged_response in paged_responses:
        if not paged_response.http_response.text:
            raise ValueError(
                f"Cannot collect response string from a paged response with no body text. "
                f"url: {paged_response.http_response.url}"
            )
        response_strings.append(paged_response.http_response.text)
    return response_strings


def _check_for_valid_paged_responses(
    response: RuntimeResponse, paged_responses: list[RuntimeResponse]
) -> None:
    """Check that the paged responses are valid and can be combined with the original response.

    Raises:
        ValueError: If any of the paged responses are invalid and cannot be combined with
            the original response.
    """
    for paged_response in paged_responses:
        if paged_response.http_response.status_code != 200:
            logger.error(
                f"Received unexpected status code {paged_response.http_response.status_code} "
                f"for paged response to request {response.request_id} "
                f"url: {paged_response.http_response.url}"
                f"\n{asdict(paged_response.http_response)}"
            )
            raise ValueError(
                f"Invalid paged response: url: {paged_response.http_response.url} has an "
                f"unexpected status code {paged_response.http_response.status_code}"
            )
        if (
            paged_response.http_response.last_modified
            != response.http_response.last_modified
        ):
            logger.error(
                f"Received paged response with different Last-Modified header for "
                f"request {response.request_id} url: {paged_response.http_response.url}. "
                f"Original Last-Modified: {response.http_response.last_modified}, "
                f"Paged Last-Modified: {paged_response.http_response.last_modified}"
            )
            raise ValueError(
                f"Invalid paged response: url: {paged_response.http_response.url} has a different Last-Modified "
                f"header than the original response. This may indicate that the data changed "
                f"between requests, and the paged responses may not be valid. Try again."
            )
