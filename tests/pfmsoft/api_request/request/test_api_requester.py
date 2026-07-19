"""Tests for request module orchestration behaviors."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace, TracebackType
from uuid import UUID, uuid4

import pytest
from whenever import Instant

from pfmsoft.api_request.cache.metadata_helpers import (
    merge_cached_revalidation_metadata,
)
from pfmsoft.api_request.cache.models import CachedResponse
from pfmsoft.api_request.request.api_requester import ApiRequester
from pfmsoft.api_request.request.intermediate_models import (
    CachableRequest,
    FailNoResponse,
    FailWithResponse,
    Response200FromStaleCache,
    Response304FromStaleCache,
    SuccessfulResponse,
    UnprocessedRequest,
)
from pfmsoft.api_request.request.models import (
    Request,
    ResponseMetadata,
    ResponseMetadataRoot,
    Source,
)


@dataclass(slots=True)
class _FakeHttpResponse:
    status_code: int
    reason_phrase: str
    url: str
    text: str
    headers: dict[str, str]
    content: bytes
    elapsed: timedelta


class _FakeAsyncClient:
    def __init__(self, responses: list[_FakeHttpResponse]):
        self._responses = responses
        self._index = 0
        self.calls: list[dict[str, object]] = []

    async def request(self, **_: object) -> _FakeHttpResponse:
        self.calls.append(dict(_))
        response = self._responses[self._index]
        self._index += 1
        return response


class _FakeCache:
    def __init__(self, cached_response: CachedResponse | None = None) -> None:
        self._cached_response = cached_response
        self.updated: list[tuple[UUID, CachedResponse]] = []

    async def __aenter__(self) -> _FakeCache:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type, exc_value, traceback

    async def get(self, cache_key: UUID) -> CachedResponse | None:
        _ = cache_key
        return self._cached_response

    async def set(
        self, cache_key: UUID, text: str, metadata: ResponseMetadata
    ) -> CachedResponse:
        cached_response = CachedResponse(
            cache_key=cache_key,
            response_text=text,
            response_metadata_json=metadata.serialize(),
            etag=metadata.etag,
            last_modified=metadata.last_modified,
            expires_at=metadata.expires_at,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )
        self._cached_response = cached_response
        self.updated.append((cache_key, cached_response))
        return cached_response

    async def update_304(
        self, cache_key: UUID, metadata: ResponseMetadata
    ) -> CachedResponse:
        if self._cached_response is None:
            raise KeyError(cache_key)

        existing_metadata = ResponseMetadataRoot.model_validate_json(
            self._cached_response.response_metadata_json
        ).root
        merged_metadata = merge_cached_revalidation_metadata(
            cached=existing_metadata,
            refreshed=metadata,
        )

        cached_response = CachedResponse(
            cache_key=cache_key,
            response_text=self._cached_response.response_text,
            response_metadata_json=merged_metadata.serialize(),
            etag=merged_metadata.etag,
            last_modified=merged_metadata.last_modified,
            expires_at=merged_metadata.expires_at,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )
        self._cached_response = cached_response
        self.updated.append((cache_key, cached_response))
        return cached_response

    async def delete(self, cache_key: UUID) -> None:
        _ = cache_key

    async def clear(
        self, only_expired: bool = False, age_limit: int | None = None
    ) -> None:
        _ = only_expired, age_limit

    async def flush(self) -> None:
        return None

    async def cache_info(self):
        return SimpleNamespace(size=0)


class _FakeRateLimiter:
    @asynccontextmanager
    async def limit(self, subject: str | None):
        _ = subject
        yield


def _build_request(*, cache_key: UUID | None = None) -> Request:
    return Request(
        request_key=uuid4(),
        url="https://example.invalid/data",
        method="GET",
        headers={"Accept": "application/json"},
        parameters={},
        cache_key=cache_key,
        rate_key="test-subject",
    )


def _build_requester(
    *,
    responses: list[_FakeHttpResponse],
    cached_response: CachedResponse | None = None,
    force_fail_on: set[int] | None = None,
) -> tuple[ApiRequester, _FakeCache]:
    cache = _FakeCache(cached_response=cached_response)
    requester = ApiRequester(
        cache_factory=lambda: cache,
        rate_limiter_factory=lambda: _FakeRateLimiter(),
        force_fail_on=force_fail_on,
    )
    requester._client = _FakeAsyncClient(responses)  # pyright: ignore[reportPrivateUsage]
    requester._cache = cache  # pyright: ignore[reportPrivateUsage]
    requester._rate_limit = _FakeRateLimiter()  # pyright: ignore[reportPrivateUsage]
    return requester, cache


def _build_metadata(
    *,
    status_code: int,
    text: str,
    last_modified: str,
    pages: int = 1,
    reason_phrase: str = "OK",
) -> tuple[str, object]:
    response = _FakeHttpResponse(
        status_code=status_code,
        reason_phrase=reason_phrase,
        url="https://example.invalid/data",
        text=text,
        headers={
            "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
            "Last-Modified": last_modified,
            "X-Pages": str(pages),
        },
        content=text.encode("utf-8"),
        elapsed=timedelta(milliseconds=5),
    )
    metadata = ApiRequester._http_response_to_metadata(response)  # pyright: ignore[reportPrivateUsage]
    return text, metadata


def test_http_request_uses_expected_success_statuses_for_304() -> None:
    """The HTTP helper should allow explicit success overrides for revalidation."""

    async def run() -> None:
        response_304 = _FakeHttpResponse(
            status_code=304,
            reason_phrase="Not Modified",
            url="https://example.invalid/data",
            text="",
            headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
            content=b"",
            elapsed=timedelta(milliseconds=12),
        )
        requester, _ = _build_requester(responses=[response_304])

        result = await requester._http_request(  # pyright: ignore[reportPrivateUsage]
            UnprocessedRequest(request=_build_request()),
            allow_pagination=False,
            expected_success_statuses={304},
        )

        assert result.metadata.status_code == 304
        assert result.source == Source.NETWORK

    asyncio.run(run())


def test_cacheable_request_refreshes_stale_entry_on_304() -> None:
    """A stale cache revalidation returning 304 should update metadata and keep body."""

    async def run() -> None:
        cache_key = uuid4()
        stale_metadata = ApiRequester._http_response_to_metadata(  # pyright: ignore[reportPrivateUsage]
            _FakeHttpResponse(
                status_code=200,
                reason_phrase="OK",
                url="https://example.invalid/data",
                text="[1]",
                headers={
                    "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                    "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                    "ETag": '"abc"',
                },
                content=b"[1]",
                elapsed=timedelta(milliseconds=10),
            )
        )
        stale_cached = CachedResponse(
            cache_key=cache_key,
            response_text="[1]",
            response_metadata_json=stale_metadata.serialize(),
            etag='"abc"',
            expires_at=Instant.now().timestamp() - 1,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )

        response_304 = _FakeHttpResponse(
            status_code=304,
            reason_phrase="Not Modified",
            url="https://example.invalid/data",
            text="",
            headers={
                "Date": "Mon, 06 Jul 2026 18:05:00 GMT",
                "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                "ETag": '"abc"',
            },
            content=b"",
            elapsed=timedelta(milliseconds=11),
        )

        requester, cache = _build_requester(
            responses=[response_304],
            cached_response=stale_cached,
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(
                request=_build_request(cache_key=cache_key), cache_key=cache_key
            )
        )

        assert isinstance(result, Response304FromStaleCache)
        assert result.metadata.status_code == 200
        assert result.json == [1]
        assert len(cache.updated) == 1
        assert cache.updated[0][0] == cache_key

    asyncio.run(run())


def test_cacheable_request_applies_stale_headers_without_mutating_request() -> None:
    """Stale-cache conditional headers should be injected at send time only."""

    async def run() -> None:
        cache_key = uuid4()
        original_request = _build_request(cache_key=cache_key)
        stale_metadata = ApiRequester._http_response_to_metadata(  # pyright: ignore[reportPrivateUsage]
            _FakeHttpResponse(
                status_code=200,
                reason_phrase="OK",
                url="https://example.invalid/data",
                text="[1]",
                headers={
                    "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                    "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                    "ETag": '"abc"',
                },
                content=b"[1]",
                elapsed=timedelta(milliseconds=10),
            )
        )
        stale_cached = CachedResponse(
            cache_key=cache_key,
            response_text="[1]",
            response_metadata_json=stale_metadata.serialize(),
            etag='"abc"',
            expires_at=Instant.now().timestamp() - 1,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )
        response_304 = _FakeHttpResponse(
            status_code=304,
            reason_phrase="Not Modified",
            url="https://example.invalid/data",
            text="",
            headers={
                "Date": "Mon, 06 Jul 2026 18:05:00 GMT",
                "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                "ETag": '"abc"',
            },
            content=b"",
            elapsed=timedelta(milliseconds=11),
        )

        requester, _ = _build_requester(
            responses=[response_304],
            cached_response=stale_cached,
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(request=original_request, cache_key=cache_key)
        )

        assert isinstance(result, Response304FromStaleCache)
        assert result.metadata.status_code == 200
        assert original_request.headers == {"Accept": "application/json"}
        assert len(requester._client.calls) == 1  # pyright: ignore[reportPrivateUsage]
        assert requester._client.calls[0]["headers"] == {  # pyright: ignore[reportPrivateUsage]
            "Accept": "application/json",
            "If-None-Match": '"abc"',
            "If-Modified-Since": "Mon, 06 Jul 2026 17:00:00 GMT",
        }

    asyncio.run(run())


def test_cacheable_request_returns_fresh_cache_hit() -> None:
    """An unexpired cached response should return directly without network refresh."""

    async def run() -> None:
        cache_key = uuid4()
        response_text, metadata = _build_metadata(
            status_code=200,
            text="[1]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=1,
        )
        cached_response = CachedResponse(
            cache_key=cache_key,
            response_text=response_text,
            response_metadata_json=metadata.serialize(),
            etag='"abc"',
            expires_at=Instant.now().timestamp() + 60,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )
        requester, cache = _build_requester(
            responses=[],
            cached_response=cached_response,
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(
                request=_build_request(cache_key=cache_key), cache_key=cache_key
            )
        )

        assert isinstance(result, SuccessfulResponse)
        assert result.source == Source.CACHE
        assert result.json == [1]
        assert len(cache.updated) == 0

    asyncio.run(run())


def test_cacheable_request_refreshes_stale_entry_on_200() -> None:
    """A stale cache revalidation returning 200 should replace cached content."""

    async def run() -> None:
        cache_key = uuid4()
        stale_text, stale_metadata = _build_metadata(
            status_code=200,
            text="[1]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=1,
        )
        stale_cached = CachedResponse(
            cache_key=cache_key,
            response_text=stale_text,
            response_metadata_json=stale_metadata.serialize(),
            etag='"abc"',
            expires_at=Instant.now().timestamp() - 1,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )

        response_text, response_metadata = _build_metadata(
            status_code=200,
            text="[2]",
            last_modified="Mon, 06 Jul 2026 17:30:00 GMT",
            pages=1,
        )
        requester, cache = _build_requester(
            responses=[
                _FakeHttpResponse(
                    status_code=200,
                    reason_phrase="OK",
                    url="https://example.invalid/data",
                    text=response_text,
                    headers={
                        "Date": "Mon, 06 Jul 2026 18:05:00 GMT",
                        "Last-Modified": "Mon, 06 Jul 2026 17:30:00 GMT",
                        "X-Pages": "1",
                    },
                    content=response_text.encode("utf-8"),
                    elapsed=timedelta(milliseconds=11),
                )
            ],
            cached_response=stale_cached,
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(
                request=_build_request(cache_key=cache_key), cache_key=cache_key
            )
        )

        assert isinstance(result, Response200FromStaleCache)
        assert result.json == [2]
        assert len(cache.updated) == 1
        assert cache.updated[0][0] == cache_key

    asyncio.run(run())


def test_cacheable_request_refreshes_stale_paged_entry_on_200() -> None:
    """A stale paged cache revalidation returning 200 should cache the merged body."""

    async def run() -> None:
        cache_key = uuid4()
        stale_text, stale_metadata = _build_metadata(
            status_code=200,
            text="[1]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=2,
        )
        stale_cached = CachedResponse(
            cache_key=cache_key,
            response_text=stale_text,
            response_metadata_json=stale_metadata.serialize(),
            etag='"abc"',
            expires_at=Instant.now().timestamp() - 1,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )

        first_page_response = _FakeHttpResponse(
            status_code=200,
            reason_phrase="OK",
            url="https://example.invalid/data",
            text="[2]",
            headers={
                "Date": "Mon, 06 Jul 2026 18:05:00 GMT",
                "Last-Modified": "Mon, 06 Jul 2026 17:30:00 GMT",
                "X-Pages": "2",
            },
            content=b"[2]",
            elapsed=timedelta(milliseconds=11),
        )
        second_page_response = _FakeHttpResponse(
            status_code=200,
            reason_phrase="OK",
            url="https://example.invalid/data",
            text="[3]",
            headers={
                "Date": "Mon, 06 Jul 2026 18:05:00 GMT",
                "Last-Modified": "Mon, 06 Jul 2026 17:30:00 GMT",
                "X-Pages": "1",
            },
            content=b"[3]",
            elapsed=timedelta(milliseconds=11),
        )

        requester, cache = _build_requester(
            responses=[first_page_response, second_page_response],
            cached_response=stale_cached,
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(
                request=_build_request(cache_key=cache_key), cache_key=cache_key
            )
        )

        assert isinstance(result, Response200FromStaleCache)
        assert result.json == [2, 3]
        assert len(cache.updated) == 1
        assert cache.updated[0][0] == cache_key
        assert cache.updated[0][1].response_text == "[2,3]"

    asyncio.run(run())


def test_http_request_uses_fail_with_response_for_404() -> None:
    """Configured recoverable statuses should map to failure-with-response."""

    async def run() -> None:
        response_404 = _FakeHttpResponse(
            status_code=404,
            reason_phrase="Not Found",
            url="https://example.invalid/data",
            text='{"error": "missing"}',
            headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
            content=b'{"error": "missing"}',
            elapsed=timedelta(milliseconds=8),
        )
        requester, _ = _build_requester(responses=[response_404])

        result = await requester._http_request(  # pyright: ignore[reportPrivateUsage]
            UnprocessedRequest(request=_build_request()),
            allow_pagination=False,
        )

        assert isinstance(result, FailWithResponse)
        assert result.metadata.status_code == 404

    asyncio.run(run())


def test_http_request_short_circuits_when_force_flag_is_set() -> None:
    """A pre-set force-failure flag should skip the network call and fail locally."""

    async def run() -> None:
        response_200 = _FakeHttpResponse(
            status_code=200,
            reason_phrase="OK",
            url="https://example.invalid/data",
            text='{"ok": true}',
            headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
            content=b'{"ok": true}',
            elapsed=timedelta(milliseconds=8),
        )
        requester, _ = _build_requester(responses=[response_200])
        requester._force_failure = True  # pyright: ignore[reportPrivateUsage]

        result = await requester._http_request(  # pyright: ignore[reportPrivateUsage]
            UnprocessedRequest(request=_build_request()),
            allow_pagination=False,
        )

        assert isinstance(result, FailNoResponse)
        assert "ForcedFailureError" in result.error_message
        assert len(requester._client.calls) == 0  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())


def test_process_requests_maps_forced_failure_to_fail_no_response() -> None:
    """A configured forced-failure status should map to FailNoResponse in batch output."""

    async def run() -> None:
        response_503 = _FakeHttpResponse(
            status_code=503,
            reason_phrase="Service Unavailable",
            url="https://example.invalid/data",
            text='{"error": "busy"}',
            headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
            content=b'{"error": "busy"}',
            elapsed=timedelta(milliseconds=8),
        )
        requester, _ = _build_requester(responses=[response_503], force_fail_on={503})
        request = _build_request()

        results = await requester.process_requests({request.request_key: request})

        assert request.request_key in results.failed
        failed = results.failed[request.request_key]
        assert failed.metadata is None
        assert failed.json is None
        assert any("ForcedFailureError" in message for message in failed.error_messages)

    asyncio.run(run())


def test_process_requests_resets_force_failure_between_batches() -> None:
    """Each process_requests call should clear prior force-failure state."""

    async def run() -> None:
        response_503 = _FakeHttpResponse(
            status_code=503,
            reason_phrase="Service Unavailable",
            url="https://example.invalid/data",
            text='{"error": "busy"}',
            headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
            content=b'{"error": "busy"}',
            elapsed=timedelta(milliseconds=8),
        )
        response_200 = _FakeHttpResponse(
            status_code=200,
            reason_phrase="OK",
            url="https://example.invalid/data",
            text='{"ok": true}',
            headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
            content=b'{"ok": true}',
            elapsed=timedelta(milliseconds=8),
        )

        requester, _ = _build_requester(
            responses=[response_503, response_200],
            force_fail_on={503},
        )
        first_request = _build_request()
        second_request = _build_request()

        first_results = await requester.process_requests({
            first_request.request_key: first_request
        })
        assert first_request.request_key in first_results.failed

        second_results = await requester.process_requests({
            second_request.request_key: second_request
        })
        assert second_request.request_key in second_results.successful
        assert not second_results.failed

    asyncio.run(run())


def test_http_request_uses_fail_with_response_for_503() -> None:
    """Configured unrecoverable statuses should still map to request failure."""

    async def run() -> None:
        response_503 = _FakeHttpResponse(
            status_code=503,
            reason_phrase="Service Unavailable",
            url="https://example.invalid/data",
            text='{"error": "busy"}',
            headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
            content=b'{"error": "busy"}',
            elapsed=timedelta(milliseconds=8),
        )
        requester, _ = _build_requester(responses=[response_503])

        result = await requester._http_request(  # pyright: ignore[reportPrivateUsage]
            UnprocessedRequest(request=_build_request()),
            allow_pagination=False,
        )

        assert isinstance(result, FailWithResponse)
        assert result.metadata.status_code == 503

    asyncio.run(run())


def test_handle_paged_response_merges_json_lists() -> None:
    """Paged responses should merge JSON list bodies in order."""

    async def run() -> None:
        first_text, first_metadata = _build_metadata(
            status_code=200,
            text="[1]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=2,
        )
        second_text, second_metadata = _build_metadata(
            status_code=200,
            text="[2]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=1,
        )
        requester, _ = _build_requester(
            responses=[
                _FakeHttpResponse(
                    status_code=200,
                    reason_phrase="OK",
                    url="https://example.invalid/data",
                    text=second_text,
                    headers={
                        "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                        "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                        "X-Pages": "1",
                    },
                    content=second_text.encode("utf-8"),
                    elapsed=timedelta(milliseconds=5),
                )
            ]
        )
        request = _build_request()
        paged = SuccessfulResponse(
            request=request,
            metadata=first_metadata,
            json=[1],
            source=Source.NETWORK,
        )

        result = await requester._handle_paged_response(paged)  # pyright: ignore[reportPrivateUsage]

        assert isinstance(result, SuccessfulResponse)
        assert result.json == [1, 2]

    asyncio.run(run())


def test_handle_paged_response_fails_on_source_drift() -> None:
    """Paged responses should fail when later pages change source metadata."""

    async def run() -> None:
        first_text, first_metadata = _build_metadata(
            status_code=200,
            text="[1]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=2,
        )
        requester, _ = _build_requester(
            responses=[
                _FakeHttpResponse(
                    status_code=200,
                    reason_phrase="OK",
                    url="https://example.invalid/data",
                    text="[2]",
                    headers={
                        "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                        "Last-Modified": "Mon, 06 Jul 2026 17:30:00 GMT",
                        "X-Pages": "1",
                    },
                    content=b"[2]",
                    elapsed=timedelta(milliseconds=5),
                )
            ]
        )
        request = _build_request()
        paged = SuccessfulResponse(
            request=request,
            metadata=first_metadata,
            json=[1],
            source=Source.NETWORK,
        )

        result = await requester._handle_paged_response(paged)  # pyright: ignore[reportPrivateUsage]

        assert isinstance(result, FailNoResponse)

    asyncio.run(run())


def test_process_requests_maps_intermediate_results() -> None:
    """Intermediate response models should map to public response models by key."""

    async def run() -> None:
        request_key = uuid4()
        request = _build_request()
        request_map = {request_key: request}

        requester, _ = _build_requester(responses=[])

        metadata = ApiRequester._http_response_to_metadata(  # pyright: ignore[reportPrivateUsage]
            _FakeHttpResponse(
                status_code=200,
                reason_phrase="OK",
                url="https://example.invalid/data",
                text="[1]",
                headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
                content=b"[1]",
                elapsed=timedelta(milliseconds=3),
            )
        )

        async def fake_dispatch(_: dict[UUID, Request]):
            return {
                request_key: Response304FromStaleCache(
                    request=request,
                    metadata=metadata,
                    json=[1],
                )
            }

        requester._dispatch_requests = fake_dispatch  # pyright: ignore[reportPrivateUsage]

        results = await requester.process_requests(request_map)
        assert request_key in results.successful
        assert results.successful[request_key].request == request
        assert not results.failed

    asyncio.run(run())


def test_process_requests_maps_failures_and_unknown_intermediate() -> None:
    """Failing and unknown intermediate results should map to failed outputs."""

    async def run() -> None:
        first_key = uuid4()
        second_key = uuid4()
        third_key = uuid4()
        first_request = _build_request()
        second_request = _build_request()
        third_request = _build_request()
        request_map = {
            first_key: first_request,
            second_key: second_request,
            third_key: third_request,
        }

        metadata = ApiRequester._http_response_to_metadata(  # pyright: ignore[reportPrivateUsage]
            _FakeHttpResponse(
                status_code=404,
                reason_phrase="Not Found",
                url="https://example.invalid/data",
                text='{"error": "missing"}',
                headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
                content=b'{"error": "missing"}',
                elapsed=timedelta(milliseconds=3),
            )
        )

        requester, _ = _build_requester(responses=[])

        async def fake_dispatch(_: dict[UUID, Request]):
            return {
                first_key: FailWithResponse(
                    request=first_request,
                    metadata=metadata,
                    json={"error": "missing"},
                ),
                second_key: FailNoResponse(
                    request=second_request,
                    error_message="transport error",
                ),
                third_key: UnprocessedRequest(request=third_request),
            }

        requester._dispatch_requests = fake_dispatch  # pyright: ignore[reportPrivateUsage]

        results = await requester.process_requests(request_map)

        assert first_key in results.failed
        assert results.failed[first_key].error_messages == ["HTTP 404 Not Found"]
        assert second_key in results.failed
        assert results.failed[second_key].error_messages == ["transport error"]
        assert third_key in results.failed
        assert results.failed[third_key].error_messages == [
            "Unknown intermediate response type"
        ]

    asyncio.run(run())


def test_cacheable_request_cache_miss_caches_successful_network_result() -> None:
    """Cache-miss success should persist the response in cache before returning."""

    async def run() -> None:
        cache_key = uuid4()
        requester, cache = _build_requester(
            responses=[
                _FakeHttpResponse(
                    status_code=200,
                    reason_phrase="OK",
                    url="https://example.invalid/data",
                    text='{"ok": true}',
                    headers={
                        "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                        "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                        "ETag": '"abc"',
                    },
                    content=b'{"ok": true}',
                    elapsed=timedelta(milliseconds=6),
                )
            ]
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(
                request=_build_request(cache_key=cache_key), cache_key=cache_key
            )
        )

        assert isinstance(result, SuccessfulResponse)
        assert len(cache.updated) == 1
        assert cache.updated[0][0] == cache_key

    asyncio.run(run())


def test_cacheable_request_returns_failed_refresh_result_directly() -> None:
    """Stale-cache revalidation failures should be returned unchanged."""

    async def run() -> None:
        cache_key = uuid4()
        stale_metadata = ApiRequester._http_response_to_metadata(  # pyright: ignore[reportPrivateUsage]
            _FakeHttpResponse(
                status_code=200,
                reason_phrase="OK",
                url="https://example.invalid/data",
                text='{"ok": true}',
                headers={
                    "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                    "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                    "ETag": '"abc"',
                },
                content=b'{"ok": true}',
                elapsed=timedelta(milliseconds=5),
            )
        )
        stale_cached = CachedResponse(
            cache_key=cache_key,
            response_text='{"ok": true}',
            response_metadata_json=stale_metadata.serialize(),
            etag='"abc"',
            expires_at=Instant.now().timestamp() - 1,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )
        requester, _ = _build_requester(
            responses=[
                _FakeHttpResponse(
                    status_code=404,
                    reason_phrase="Not Found",
                    url="https://example.invalid/data",
                    text='{"error": "missing"}',
                    headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
                    content=b'{"error": "missing"}',
                    elapsed=timedelta(milliseconds=7),
                )
            ],
            cached_response=stale_cached,
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(
                request=_build_request(cache_key=cache_key), cache_key=cache_key
            )
        )

        assert isinstance(result, FailWithResponse)
        assert result.metadata.status_code == 404

    asyncio.run(run())


def test_cacheable_request_marks_unexpected_2xx_revalidation_as_failed() -> None:
    """Stale-cache 2xx statuses other than 200 should map to failed response."""

    async def run() -> None:
        cache_key = uuid4()
        stale_metadata = ApiRequester._http_response_to_metadata(  # pyright: ignore[reportPrivateUsage]
            _FakeHttpResponse(
                status_code=200,
                reason_phrase="OK",
                url="https://example.invalid/data",
                text='{"ok": true}',
                headers={
                    "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                    "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                    "ETag": '"abc"',
                },
                content=b'{"ok": true}',
                elapsed=timedelta(milliseconds=5),
            )
        )
        stale_cached = CachedResponse(
            cache_key=cache_key,
            response_text='{"ok": true}',
            response_metadata_json=stale_metadata.serialize(),
            etag='"abc"',
            expires_at=Instant.now().timestamp() - 1,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )
        requester, _ = _build_requester(
            responses=[
                _FakeHttpResponse(
                    status_code=206,
                    reason_phrase="Partial Content",
                    url="https://example.invalid/data",
                    text='{"ok": true}',
                    headers={
                        "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                        "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
                    },
                    content=b'{"ok": true}',
                    elapsed=timedelta(milliseconds=7),
                )
            ],
            cached_response=stale_cached,
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(
                request=_build_request(cache_key=cache_key), cache_key=cache_key
            )
        )

        assert isinstance(result, FailWithResponse)
        assert result.metadata.status_code == 206

    asyncio.run(run())


def test_http_request_raises_for_fatal_transport_errors() -> None:
    """RuntimeError transport failures should be re-raised as fatal."""

    async def run() -> None:
        requester, _ = _build_requester(responses=[])

        async def raising_request(**_: object) -> _FakeHttpResponse:
            raise RuntimeError("fatal transport")

        requester._client.request = raising_request  # pyright: ignore[reportPrivateUsage]

        with pytest.raises(RuntimeError, match="fatal transport"):
            await requester._http_request(  # pyright: ignore[reportPrivateUsage]
                UnprocessedRequest(request=_build_request()),
                allow_pagination=False,
            )

    asyncio.run(run())


def test_http_request_returns_fail_no_response_for_invalid_json() -> None:
    """Invalid JSON payloads should return FailNoResponse parse failures."""

    async def run() -> None:
        response = _FakeHttpResponse(
            status_code=200,
            reason_phrase="OK",
            url="https://example.invalid/data",
            text="{invalid-json",
            headers={
                "Date": "Mon, 06 Jul 2026 18:00:00 GMT",
                "Last-Modified": "Mon, 06 Jul 2026 17:00:00 GMT",
            },
            content=b"{invalid-json",
            elapsed=timedelta(milliseconds=5),
        )
        requester, _ = _build_requester(responses=[response])

        result = await requester._http_request(  # pyright: ignore[reportPrivateUsage]
            UnprocessedRequest(request=_build_request()),
            allow_pagination=False,
        )

        assert isinstance(result, FailNoResponse)
        assert "Failed to parse response JSON" in result.error_message

    asyncio.run(run())


def test_handle_paged_response_returns_original_for_single_page() -> None:
    """Single-page successful responses should pass through unchanged."""

    async def run() -> None:
        requester, _ = _build_requester(responses=[])
        _, metadata = _build_metadata(
            status_code=200,
            text="[1]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=1,
        )
        request = _build_request()
        response = SuccessfulResponse(
            request=request,
            metadata=metadata,
            json=[1],
            source=Source.NETWORK,
        )

        result = await requester._handle_paged_response(response)  # pyright: ignore[reportPrivateUsage]

        assert result is response

    asyncio.run(run())


def test_handle_paged_response_short_circuits_on_failed_page() -> None:
    """Paged merge should stop immediately when any page request fails."""

    async def run() -> None:
        requester, _ = _build_requester(responses=[])
        _, metadata = _build_metadata(
            status_code=200,
            text="[1]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=2,
        )
        request = _build_request()
        response = SuccessfulResponse(
            request=request,
            metadata=metadata,
            json=[1],
            source=Source.NETWORK,
        )
        failed_page = FailNoResponse(request=request, error_message="page failed")

        async def fake_gather(_: SuccessfulResponse):
            return [failed_page]

        requester._gather_paged_responses = fake_gather  # pyright: ignore[reportPrivateUsage]

        result = await requester._handle_paged_response(response)  # pyright: ignore[reportPrivateUsage]

        assert result is failed_page

    asyncio.run(run())


def test_handle_paged_response_returns_fail_when_merge_raises() -> None:
    """Non-list payloads in paged merge should return FailNoResponse."""

    async def run() -> None:
        requester, _ = _build_requester(responses=[])
        _, metadata = _build_metadata(
            status_code=200,
            text="[1]",
            last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
            pages=2,
        )
        request = _build_request()
        first_response = SuccessfulResponse(
            request=request,
            metadata=metadata,
            json={"not": "a list"},
            source=Source.NETWORK,
        )
        next_page = SuccessfulResponse(
            request=request,
            metadata=metadata,
            json=[2],
            source=Source.NETWORK,
        )

        async def fake_gather(_: SuccessfulResponse):
            return [next_page]

        requester._gather_paged_responses = fake_gather  # pyright: ignore[reportPrivateUsage]

        result = await requester._handle_paged_response(first_response)  # pyright: ignore[reportPrivateUsage]

        assert isinstance(result, FailNoResponse)
        assert "Paged response body is not a JSON list" in result.error_message

    asyncio.run(run())


def test_dispatch_requests_re_raises_fatal_exceptions() -> None:
    """Dispatch should re-raise fatal exceptions from request execution."""

    async def run() -> None:
        requester, _ = _build_requester(responses=[])

        async def fatal_http_request(
            request: UnprocessedRequest,
            *,
            allow_pagination: bool = True,
            expected_success_statuses: set[int] | None = None,
        ) -> SuccessfulResponseBase | FailedRequestBase:
            _ = request, allow_pagination, expected_success_statuses
            raise RuntimeError("fatal dispatch")

        requester._http_request = fatal_http_request  # pyright: ignore[reportPrivateUsage]
        request = _build_request()

        with pytest.raises(RuntimeError, match="fatal dispatch"):
            await requester._dispatch_requests({request.request_key: request})  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())


def test_session_cache_and_rate_limiter_checks_raise_when_uninitialized() -> None:
    """Internal dependency guards should fail before context initialization."""

    async def run() -> None:
        requester = ApiRequester(
            cache_factory=lambda: _FakeCache(),
            rate_limiter_factory=lambda: _FakeRateLimiter(),
        )

        with pytest.raises(RuntimeError, match="HTTP client is not initialized"):
            await requester._session_check()  # pyright: ignore[reportPrivateUsage]
        with pytest.raises(RuntimeError, match="Cache is not initialized"):
            await requester._cache_check()  # pyright: ignore[reportPrivateUsage]
        with pytest.raises(RuntimeError, match="Rate limiter is not initialized"):
            await requester._rate_limit_check()  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())


def test_static_request_header_and_paged_json_helpers_cover_edge_cases() -> None:
    """Static helper methods should merge headers and validate paged payload types."""
    request = _build_request()

    updated = ApiRequester._updated_request_headers(  # pyright: ignore[reportPrivateUsage]
        request,
        Authorization="Bearer token",
    )

    assert updated.headers["Authorization"] == "Bearer token"
    assert "Authorization" not in request.headers

    with pytest.raises(ValueError, match="not a JSON list"):
        ApiRequester._merge_paged_json_lists(  # pyright: ignore[reportPrivateUsage]
            [1],
            [{"not": "a list"}],
        )


def test_api_requester_context_manager_initializes_and_cleans_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Context manager should initialize client/cache and cleanly tear them down."""

    class _FakeManagedClient:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    class _ManagedCache(_FakeCache):
        def __init__(self) -> None:
            super().__init__()
            self.entered = False
            self.exited = False

        async def __aenter__(self) -> _ManagedCache:
            self.entered = True
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            _ = exc_type, exc_value, traceback
            self.exited = True

    async def run() -> None:
        fake_client = _FakeManagedClient()
        cache = _ManagedCache()

        async def fake_config_async_http_client() -> _FakeManagedClient:
            return fake_client

        monkeypatch.setattr(
            "pfmsoft.api_request.request.api_requester.config_async_http_client",
            fake_config_async_http_client,
        )

        requester = ApiRequester(
            cache_factory=lambda: cache,
            rate_limiter_factory=lambda: _FakeRateLimiter(),
        )

        async with requester as active:
            assert active._client is fake_client  # pyright: ignore[reportPrivateUsage]
            assert active._cache is cache  # pyright: ignore[reportPrivateUsage]
            assert cache.entered is True

        assert fake_client.closed is True
        assert cache.exited is True
        assert requester._client is None  # pyright: ignore[reportPrivateUsage]
        assert requester._cache is None  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())


def test_dispatch_requests_uses_cacheable_path_for_cache_key_requests() -> None:
    """Requests with cache keys should be routed to _cacheable_request."""

    async def run() -> None:
        requester, _ = _build_requester(responses=[])
        request = _build_request(cache_key=uuid4())
        seen_cacheable_calls: list[UUID] = []
        metadata = ApiRequester._http_response_to_metadata(  # pyright: ignore[reportPrivateUsage]
            _FakeHttpResponse(
                status_code=200,
                reason_phrase="OK",
                url=request.url,
                text='{"ok": true}',
                headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
                content=b'{"ok": true}',
                elapsed=timedelta(milliseconds=3),
            )
        )

        async def fake_cacheable_request(
            cacheable_request: CachableRequest,
        ) -> SuccessfulResponseBase | FailedRequestBase:
            seen_cacheable_calls.append(cacheable_request.cache_key)
            return SuccessfulResponse(
                request=cacheable_request.request,
                metadata=metadata,
                json={"ok": True},
                source=Source.NETWORK,
            )

        requester._cacheable_request = fake_cacheable_request  # pyright: ignore[reportPrivateUsage]

        results = await requester._dispatch_requests({request.request_key: request})  # pyright: ignore[reportPrivateUsage]

        assert seen_cacheable_calls == [request.cache_key]
        assert isinstance(results[request.request_key], SuccessfulResponse)

    asyncio.run(run())


def test_api_requester_aexit_handles_cache_only_state() -> None:
    """__aexit__ should clean cache without requiring an active client."""

    class _CacheOnly(_FakeCache):
        def __init__(self) -> None:
            super().__init__()
            self.exited = False

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            _ = exc_type, exc_value, traceback
            self.exited = True

    async def run() -> None:
        requester = ApiRequester(
            cache_factory=lambda: _FakeCache(),
            rate_limiter_factory=lambda: _FakeRateLimiter(),
        )
        cache = _CacheOnly()
        requester._cache = cache  # pyright: ignore[reportPrivateUsage]
        requester._client = None  # pyright: ignore[reportPrivateUsage]

        await requester.__aexit__(None, None, None)

        assert cache.exited is True
        assert requester._cache is None  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())


def test_api_requester_aexit_handles_client_only_state() -> None:
    """__aexit__ should close client even when cache is already absent."""

    class _ClientOnly:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    async def run() -> None:
        requester = ApiRequester(
            cache_factory=lambda: _FakeCache(),
            rate_limiter_factory=lambda: _FakeRateLimiter(),
        )
        client = _ClientOnly()
        requester._cache = None  # pyright: ignore[reportPrivateUsage]
        requester._client = client  # pyright: ignore[reportPrivateUsage]

        await requester.__aexit__(None, None, None)

        assert client.closed is True
        assert requester._client is None  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())


def test_cacheable_request_cache_miss_returns_failure_without_cache_write() -> None:
    """Cache-miss failures should return directly without writing cache."""

    async def run() -> None:
        cache_key = uuid4()
        requester, cache = _build_requester(
            responses=[
                _FakeHttpResponse(
                    status_code=404,
                    reason_phrase="Not Found",
                    url="https://example.invalid/data",
                    text='{"error": "missing"}',
                    headers={"Date": "Mon, 06 Jul 2026 18:00:00 GMT"},
                    content=b'{"error": "missing"}',
                    elapsed=timedelta(milliseconds=6),
                )
            ]
        )

        result = await requester._cacheable_request(  # pyright: ignore[reportPrivateUsage]
            CachableRequest(
                request=_build_request(cache_key=cache_key), cache_key=cache_key
            )
        )

        assert isinstance(result, FailWithResponse)
        assert cache.updated == []

    asyncio.run(run())
