"""Live tests for paged API requests.

These tests are gated behind the ``--runlive`` flag and should use only public
API surfaces.
"""

import asyncio
import logging
from time import perf_counter
from uuid import uuid4

import pytest

from api_request import ApiRequester, Request, Response, Source
from api_request.cache import InMemoryCache
from api_request.rate_limit import AiolimiterRateLimiterFactory

logger = logging.getLogger(__name__)
_shared_live_universe_types_response: Response[str] | None = None
"""Shared response for universe types, to avoid repeated live requests."""
max_rate = 20
"""Maximum number of requests per time period for the rate limiter."""
time_period = 0.1
"""Time period in seconds for the rate limiter."""


def build_universe_types_request() -> Request[str]:
    """This request demonstrates a simple paged GET request to the ESI universe types endpoint.

    It is used to test the live request functionality of the API client.

    It can test the following:
    - The request is made successfully and returns a 200 status code.
    - The response is a valid JSON array of ints.
    - The response contains the expected values.
    - The request is cachable and can be retrieved from the cache.
    - The entire paged response can be retrieved from the cache.

    The response should look like this:
    ```json
    [1, 2, 3, 4, 5]
    ```
    """
    return Request(
        request_key=uuid4(),
        method="GET",
        url="https://esi.evetech.net/universe/types/",
        headers={"Accept": "application/json"},
        cache_key=uuid4(),  # A cache key only used for testing this request, not a real cache key
        rate_key="esi-universe-types",  # A rate key only used for testing this request, not a real rate key
    )


async def _fetch_live_universe_types_response(
    *, reuse_shared: bool = True
) -> Response[str]:
    """Fetch the live universe types response, optionally reusing a shared result."""
    global _shared_live_universe_types_response

    if reuse_shared and _shared_live_universe_types_response is not None:
        logger.info(
            "Reusing shared universe types response: status=%s source=%s",
            _shared_live_universe_types_response.metadata.status_code,
            _shared_live_universe_types_response.source,
        )
        return _shared_live_universe_types_response

    request = build_universe_types_request()
    request_id = request.request_key

    async with ApiRequester[str](
        cache_factory=InMemoryCache,
        rate_limiter_factory=AiolimiterRateLimiterFactory[str](
            max_rate=max_rate,
            time_period=time_period,
        ),
    ) as requester:
        start = perf_counter()
        responses = await requester.process_requests({request_id: request})
        end = perf_counter()
        logger.info(
            "Fetched universe types response in %.3f seconds",
            end - start,
        )

    assert request_id in responses.successful
    assert request_id not in responses.failed
    response = responses.successful[request_id]
    assert isinstance(response, Response)
    logger.info(
        "Fetched universe types response: status=%s source=%s bytes=%s",
        response.metadata.status_code,
        response.source,
        response.metadata.bytes_downloaded,
    )

    if reuse_shared:
        _shared_live_universe_types_response = response
    return response


@pytest.mark.live
def test_live_universe_types_request_returns_success_response() -> None:
    """The live universe types request should return a successful response."""
    response = asyncio.run(_fetch_live_universe_types_response(reuse_shared=True))
    assert response.metadata.status_code == 200
    logger.info(
        "Live paged success test passed: status=%s source=%s url=%s",
        response.metadata.status_code,
        response.source,
        response.metadata.url,
    )


@pytest.mark.live
def test_live_universe_types_response_is_json_array_of_ints() -> None:
    """The live universe types payload should be a non-empty int array."""
    response = asyncio.run(_fetch_live_universe_types_response(reuse_shared=True))

    payload: list[int] = response.json
    assert isinstance(payload, list)
    assert len(payload) > 0
    assert all(isinstance(item, int) for item in payload)
    logger.info(
        "Live paged payload test passed: entries=%s first=%s last=%s",
        len(payload),
        payload[0],
        payload[-1],
    )


@pytest.mark.live
def test_live_universe_types_cache_data_matches_original_response() -> None:
    """A cached paged response should match the original network response body."""

    async def run() -> None:
        cache = InMemoryCache()
        shared_cache_key = uuid4()
        seed = build_universe_types_request()

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
                max_rate=max_rate,
                time_period=time_period,
            ),
        ) as requester:
            start = perf_counter()
            first = await requester.process_requests({
                request_one.request_key: request_one
            })
            mid = perf_counter()
            second = await requester.process_requests({
                request_two.request_key: request_two
            })
            end = perf_counter()
            # format the timings to 3 decimal places for logging
            logger.info(
                "Live paged request timings with cache: first_request=%.3f second_request=%.3f total=%.3f",
                mid - start,
                end - mid,
                end - start,
            )

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
        assert first_response.source == Source.NETWORK
        assert second_response.source in {
            Source.CACHE,
            Source.CACHE_200,
            Source.CACHE_304,
        }

        # Primary check for this live-paged test: cache data equals original data.
        assert second_response.json == first_response.json
        first_payload = first_response.json
        second_payload = second_response.json
        assert first_payload == second_payload

        cache_info = await cache.cache_info()
        assert cache_info == type(cache_info)(size=1)
        logger.info(
            "Live paged cache match test passed: payload_size=%s first_source=%s second_source=%s cache_size=%s",
            len(first_payload),
            first_response.source,
            second_response.source,
            cache_info.size,
        )

    asyncio.run(run())
