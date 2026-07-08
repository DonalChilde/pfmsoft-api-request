"""These are requests that are made to the live API.

They are not run by default, but can be run with the `--runlive` flag.


Usage should mirror what a user would do with the API client, and should not use any internal methods or classes.
"""

import asyncio
import logging
from typing import Any
from uuid import uuid4

import pytest

from api_request import ApiRequester, Request, Response, Source
from api_request.cache import InMemoryCache
from api_request.rate_limit import AiolimiterRateLimiterFactory

logger = logging.getLogger(__name__)
_shared_live_status_response: Response[str] | None = None
"""Shared response for the live status request, to avoid making multiple requests during tests."""


def build_live_status_request() -> Request[str]:
    """This request demonstrates a simple GET request to the ESI status endpoint.

    It is used to test the live request functionality of the API client.

    It can test the following:
    - The request is made successfully and returns a 200 status code.
    - The response is a valid JSON object.
    - The response contains the expected keys and values.
    - The request is cachable and can be retrieved from the cache.

    The response should look like this:
    ```json
    {
    "players": 0,
    "server_version": "string",
    "start_time": "2019-08-24T14:15:22Z",
    }
    ```
    and may include a "vip" key with a boolean value.
    """
    return Request(
        request_key=uuid4(),
        method="GET",
        url="https://esi.evetech.net/status/",
        headers={"Accept": "application/json"},
        cache_key=uuid4(),  # A cache key only used for testing this request, not a real cache key
        rate_key="esi-status-request",  # A rate key only used for testing this request, not a real rate key
    )


async def _fetch_live_status_response(*, reuse_shared: bool = True) -> Response[str]:
    """Fetch the live status response, optionally reusing a shared result."""
    global _shared_live_status_response

    if reuse_shared and _shared_live_status_response is not None:
        logger.info(
            "Reusing shared live status response: status=%s source=%s",
            _shared_live_status_response.metadata.status_code,
            _shared_live_status_response.source,
        )
        return _shared_live_status_response

    request = build_live_status_request()
    request_id = request.request_key

    async with ApiRequester[str](
        cache_factory=InMemoryCache,
        rate_limiter_factory=AiolimiterRateLimiterFactory[str](
            max_rate=5.0,
            time_period=1.0,
        ),
    ) as requester:
        responses = await requester.process_requests({request_id: request})

    assert request_id in responses.successful
    assert request_id not in responses.failed
    response = responses.successful[request_id]
    assert isinstance(response, Response)
    logger.info(
        "Fetched live status response: status=%s source=%s bytes=%s",
        response.metadata.status_code,
        response.source,
        response.metadata.bytes_downloaded,
    )

    if reuse_shared:
        _shared_live_status_response = response
    return response


@pytest.mark.live
def test_live_status_request_returns_success_response() -> None:
    """The live ESI status request should return a successful public response."""
    response = asyncio.run(_fetch_live_status_response(reuse_shared=True))
    assert response.metadata.status_code == 200
    logger.info(
        "Live success test passed: status=%s source=%s url=%s",
        response.metadata.status_code,
        response.source,
        response.metadata.url,
    )


@pytest.mark.live
def test_live_status_request_response_has_expected_keys() -> None:
    """The live ESI status payload should contain stable top-level keys."""
    response = asyncio.run(_fetch_live_status_response(reuse_shared=True))

    payload: dict[str, Any] = response.json_loads
    assert isinstance(payload, dict)
    assert "players" in payload
    assert "server_version" in payload
    assert "start_time" in payload
    logger.info(
        "Live payload keys test passed: keys=%s",
        sorted(payload.keys()),
    )


@pytest.mark.live
def test_live_status_request_cache_behavior_reuses_cached_entry() -> None:
    """Two status requests with the same cache key should keep one cache entry."""

    async def run() -> None:
        cache = InMemoryCache()
        shared_cache_key = uuid4()
        seed = build_live_status_request()

        request_one = Request(
            request_key=uuid4(),
            method=seed.method,
            url=seed.url,
            headers=dict(seed.headers),
            parameters=dict(seed.parameters),
            cache_key=shared_cache_key,
            rate_key=seed.rate_key,
        )
        request_two = Request(
            request_key=uuid4(),
            method=seed.method,
            url=seed.url,
            headers=dict(seed.headers),
            parameters=dict(seed.parameters),
            cache_key=shared_cache_key,
            rate_key=seed.rate_key,
        )

        async with ApiRequester[str](
            cache_factory=lambda: cache,
            rate_limiter_factory=AiolimiterRateLimiterFactory[str](
                max_rate=5.0,
                time_period=1.0,
            ),
        ) as requester:
            first = await requester.process_requests({
                request_one.request_key: request_one
            })
            second = await requester.process_requests({
                request_two.request_key: request_two
            })

        assert request_one.request_key in first.successful
        assert request_one.request_key not in first.failed
        assert request_two.request_key in second.successful
        assert request_two.request_key not in second.failed

        first_response = first.successful[request_one.request_key]
        second_response = second.successful[request_two.request_key]
        assert isinstance(first_response, Response)
        assert isinstance(second_response, Response)
        assert first_response.metadata.status_code == 200
        assert second_response.metadata.status_code == 200
        assert first_response.json == second_response.json
        assert first_response.source == Source.NETWORK
        assert second_response.source in {
            Source.CACHE,
            Source.CACHE_200,
            Source.CACHE_304,
        }

        cache_info = await cache.cache_info()
        assert cache_info == type(cache_info)(size=1)
        logger.info(
            "Live cache behavior test passed: first_source=%s second_source=%s cache_size=%s",
            first_response.source,
            second_response.source,
            cache_info.size,
        )

    asyncio.run(run())
