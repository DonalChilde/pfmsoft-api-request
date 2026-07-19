"""Request orchestration protocol contracts.

This module defines the public behavioral surface expected from requester
implementations.

Typical usage:

```python
from uuid import uuid4

from api_request import ApiRequester, Request
from api_request.cache import InMemoryCache
from api_request.rate_limit import AiolimiterRateLimiterFactory

request = Request(
    request_key=uuid4(),
    method="GET",
    url="https://esi.evetech.net/status/",
)

async with ApiRequester(
    cache_factory=InMemoryCache,
    rate_limiter_factory=AiolimiterRateLimiterFactory(max_rate=100.0),
) as requester:
    responses = await requester.process_requests({request.request_key: request})
```
"""

from typing import Protocol

from pfmsoft.api_request.request.models import (
    Requests,
    Responses,
)


class ApiRequesterProtocol(Protocol):
    """Protocol for batched request orchestration.

    Contract:
        - Input keys in `requests` are preserved in output mappings.
        - Successful request outcomes are returned in `Responses.successful`.
        - Request-scoped failures are returned in `Responses.failed`.
        - Implementations are typically used as async context managers to
            provision HTTP/cache/rate-limit dependencies.
        - Implementations may raise for fatal infrastructure/configuration errors.
    """

    async def process_requests(
        self,
        requests: Requests,
    ) -> Responses:
        """Process a batch of requests and return normalized success/failure maps."""
        ...
