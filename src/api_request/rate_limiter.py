"""Rate-limiter protocols and aiolimiter-backed implementations.

This module defines a reusable protocol shape for request gating and provides a
concrete implementation backed by `aiolimiter.AsyncLimiter`.
"""

from collections.abc import Hashable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from aiolimiter import AsyncLimiter


class RateLimiterProtocol[T: Hashable](Protocol):
    """Protocol for a rate limiter that gates async work.

    Implementations may produce one shot limiters for each operation or may produce a
    shared limiter that gates all operations.
    """

    def limit(self, subject: T) -> AbstractAsyncContextManager[None]:
        """Create an async gate for one operation.

        Depending on the implementation, the subject argument may be used to determine
        the rate-limiting behavior. For example, a limiter might group requests by
        endpoint or user.

        Examples:
            async with rate_limiter.limit(subject):
                # performs the operation that is subject to rate limiting, after the
                # gate is acquired.

        Args:
            subject: Domain input that may influence limiter behavior.

        Returns:
            An async context manager that acquires limiter capacity.
        """
        ...


class RateLimiterFactoryProtocol[T: Hashable](Protocol):
    """Protocol for callables that build shared rate-limiter instances.

    This protocol is used to create configured rate limiters for use in requesters.
    """

    def __call__(self) -> RateLimiterProtocol[T]:
        """Build and return a configured shared rate limiter instance."""
        ...


@dataclass(slots=True)
class AiolimiterRateLimiter[T: Hashable](RateLimiterProtocol[T]):
    """Shared rate limiter backed by one AsyncLimiter instance.

    This implementation enforces a single global bucket for all operations.

    """

    limiter: AsyncLimiter
    """The shared AsyncLimiter used by all gated operations."""

    def limit(self, subject: T) -> AbstractAsyncContextManager[None]:
        """Return the shared AsyncLimiter as an async context manager.

        NOTE: `subject` is accepted for protocol compatibility. It is currently ignored.

        Args:
            subject: Domain input for the gated operation.

        Returns:
            An async context manager that acquires capacity from the shared limiter.
        """
        return self.limiter


@dataclass(slots=True, frozen=True)
class AiolimiterRateLimiterFactory[T: Hashable](RateLimiterFactoryProtocol[T]):
    """Factory that builds shared aiolimiter-backed rate limiters.

    Use one factory per limiter configuration and one produced limiter per
    requester/task-group that should share budget.
    """

    max_rate: float
    """The maximum number of acquisitions allowed within the time period."""
    time_period: float = 60.0
    """The length of the limiting window in seconds."""

    def __call__(self) -> AiolimiterRateLimiter[T]:
        """Build a shared rate limiter instance.

        Returns:
            A shared rate limiter backed by one configured AsyncLimiter.
        """
        return AiolimiterRateLimiter(
            limiter=AsyncLimiter(self.max_rate, self.time_period)
        )
