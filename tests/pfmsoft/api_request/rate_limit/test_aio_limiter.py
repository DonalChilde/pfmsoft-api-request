"""Tests for concrete aiolimiter-backed rate limiter implementations."""

import asyncio
import time

from aiolimiter import AsyncLimiter

from pfmsoft.api_request.rate_limit.aio_limiter import (
    AiolimiterRateLimiter,
    AiolimiterRateLimiterFactory,
)


def test_limit_returns_same_limiter_for_different_subjects() -> None:
    """The concrete limiter should return one shared async gate for all subjects."""
    limiter = AsyncLimiter(10.0, 1.0)
    rate_limiter = AiolimiterRateLimiter(limiter=limiter)

    first = rate_limiter.limit("subject-a")
    second = rate_limiter.limit("subject-b")

    assert first is limiter
    assert second is limiter


def test_factory_builds_concrete_rate_limiter() -> None:
    """The factory should build an AiolimiterRateLimiter wrapper instance."""
    factory = AiolimiterRateLimiterFactory(max_rate=5.0, time_period=1.0)

    produced = factory()

    assert isinstance(produced, AiolimiterRateLimiter)
    assert isinstance(produced.limiter, AsyncLimiter)


def test_shared_limiter_throttles_concurrent_tasks() -> None:
    """Concurrent tasks sharing one limiter should observe one shared limit."""

    async def run() -> tuple[float, float]:
        limiter = AsyncLimiter(1.0, 0.2)
        rate_limiter = AiolimiterRateLimiter(limiter=limiter)
        entered_at: list[float] = []

        async def gated(subject: str) -> None:
            async with rate_limiter.limit(subject):
                entered_at.append(time.monotonic())

        await asyncio.gather(gated("subject-a"), gated("subject-b"))
        entered_at.sort()
        return entered_at[0], entered_at[1]

    first, second = asyncio.run(run())

    assert second - first >= 0.15
