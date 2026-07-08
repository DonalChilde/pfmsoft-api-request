"""Rate-limiter implementations used by request orchestration.

Exports:
                - `AiolimiterRateLimiter`: concrete limiter wrapper around
                        `aiolimiter.AsyncLimiter`.
                - `AiolimiterRateLimiterFactory`: dependency-injection factory used by
                        requester construction.

Typical usage:

```python
from api_request.rate_limit import AiolimiterRateLimiterFactory

factory = AiolimiterRateLimiterFactory(max_rate=100.0, time_period=60.0)
limiter = factory()

async with limiter.limit("market/orders"):
    ...
```
"""

from .aio_limiter import AiolimiterRateLimiter, AiolimiterRateLimiterFactory

__all__ = ["AiolimiterRateLimiter", "AiolimiterRateLimiterFactory"]
