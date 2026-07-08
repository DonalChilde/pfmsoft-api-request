"""Rate limiter implementation using aiolimiter."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from aiolimiter import AsyncLimiter

from api_request.rate_limit.protocols import (
    RateLimiterFactoryProtocol,
    RateLimiterProtocol,
)


@dataclass(slots=True)
class AiolimiterRateLimiter(RateLimiterProtocol):
    """Shared rate limiter backed by one AsyncLimiter instance.

    This implementation enforces a single global bucket for all operations.
    The provided `subject` value is currently ignored.

    """

    limiter: AsyncLimiter
    """The shared AsyncLimiter used by all gated operations."""

    def limit(self, subject: str | None) -> AbstractAsyncContextManager[None]:
        """Return the shared AsyncLimiter as an async context manager.

        NOTE: `subject` is accepted for protocol compatibility and future
        extensibility. It is currently ignored.

        Args:
            subject: Domain input for the gated operation.

        Returns:
            An async context manager that acquires capacity from the shared limiter.
        """
        return self.limiter


@dataclass(slots=True, frozen=True)
class AiolimiterRateLimiterFactory(RateLimiterFactoryProtocol):
    """Factory that builds shared aiolimiter-backed rate limiters.

    Use one factory per limiter configuration and one produced limiter per
    requester/task-group that should share budget.

    This factory is designed to be passed into requester constructors that build
    their shared limiter in `__aenter__`.
    """

    max_rate: float
    """The maximum acquisitions allowed within `time_period`.

    This should be greater than zero.
    """
    time_period: float = 60.0
    """The limiting window length in seconds.

    This should be greater than zero.
    """

    def __call__(self) -> AiolimiterRateLimiter:
        """Build a shared rate limiter instance.

        Returns:
            A shared rate limiter backed by one configured AsyncLimiter.

        Raises:
            ValueError: Propagated from `AsyncLimiter` for invalid constructor
                arguments.
        """
        return AiolimiterRateLimiter(
            limiter=AsyncLimiter(self.max_rate, self.time_period)
        )
