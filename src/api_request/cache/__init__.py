"""Cache implementations and helpers for request orchestration.

Exports:
        - `InMemoryCache` and `InMemoryCacheFactory` for ephemeral, process-local
            caching.
        - `SqliteCache` and `SqliteCacheFactory` for persistent SQLite-backed
            caching.
        - `merge_cached_revalidation_metadata` for `304 Not Modified`
            revalidation merge semantics.

Typical usage:

```python
from api_request import ApiRequester
from api_request.cache import SqliteCacheFactory
from api_request.rate_limit import AiolimiterRateLimiterFactory

async with ApiRequester(
    cache_factory=SqliteCacheFactory("./.cache/api-request.sqlite3"),
    rate_limiter_factory=AiolimiterRateLimiterFactory(max_rate=100.0),
) as requester:
    ...
```
"""

from .memory_cache import InMemoryCache, InMemoryCacheFactory
from .metadata_helpers import merge_cached_revalidation_metadata
from .sqlite_cache.sqlite_cache import SqliteCache, SqliteCacheFactory

__all__ = [
    "InMemoryCache",
    "merge_cached_revalidation_metadata",
    "SqliteCache",
    "InMemoryCacheFactory",
    "SqliteCacheFactory",
]
