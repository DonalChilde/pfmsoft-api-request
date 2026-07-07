"""Rate-limiter protocols and aiolimiter-backed implementations.

This module defines a reusable protocol shape for request gating and provides a
concrete implementation backed by `aiolimiter.AsyncLimiter`.

Protocol contract:
        - Each `limit(subject)` call returns an async context manager used to gate one
            operation.
        - Implementations may choose how `subject` influences behavior.

Concrete behavior in this module:
        - `AiolimiterRateLimiter` uses one shared `AsyncLimiter` bucket for all calls.
        - `subject` is accepted for API compatibility but ignored by the concrete
            implementation.

Typical usage:
        limiter = AiolimiterRateLimiterFactory[str](max_rate=100.0, time_period=60.0)()
        async with limiter.limit("market/orders"):
                # perform one rate-limited operation
                ...

Typed construction with ApiRequester:
    from uuid import UUID, uuid4

    from api_request.models import Request
    from api_request.rate_limiter import AiolimiterRateLimiterFactory
    from api_request.request import ApiRequester

    # Replace with your concrete cache factory.
    cache_factory = ...
    rate_limiter_factory = AiolimiterRateLimiterFactory[str](
        max_rate=100.0,
        time_period=60.0,
    )

    requests: dict[UUID, Request[str]] = {
        uuid4(): Request[str](
            request_key=uuid4(),
            url="https://esi.evetech.net/latest/status/",
            method="GET",
            rate_key="public-status",
        )
    }


    async def run() -> None:
        async with ApiRequester[str](
            cache_factory=cache_factory,
            rate_limiter_factory=rate_limiter_factory,
        ) as requester:
            await requester.process_requests(requests)
"""

from collections.abc import Hashable
from contextlib import AbstractAsyncContextManager
from typing import Protocol


class RateLimiterProtocol[T: Hashable](Protocol):
    """Protocol for a rate limiter that gates async work.

    Implementations may produce one-shot limiters for each operation or may
    return a shared limiter context that gates all operations.

    The protocol does not require any grouping strategy. Implementations may
    ignore `subject`, or they may use it to select or derive limiter behavior.
    """

    def limit(self, subject: T | None) -> AbstractAsyncContextManager[None]:
        """Create an async gate for one operation.

        Depending on implementation, `subject` may influence behavior. For
        example, a limiter might group requests by endpoint family, tenant, or
        priority class.

        Examples:
            async with rate_limiter.limit(subject):
                # performs the operation that is subject to rate limiting, after the
                # gate is acquired.

        Args:
            subject: Domain input that may influence limiter behavior. Prefer a
                stable, hashable value that represents the grouping intent.

        Returns:
            An async context manager that acquires limiter capacity.
        """
        ...


class RateLimiterFactoryProtocol[T: Hashable](Protocol):
    """Protocol for callables that build shared rate-limiter instances.

    This protocol is used to create configured rate limiters for use in
    requesters. One produced limiter instance is typically reused by one
    requester/task-group so concurrent work coordinates against shared budget.
    """

    def __call__(self) -> RateLimiterProtocol[T]:
        """Build and return a configured shared rate-limiter instance."""
        ...
