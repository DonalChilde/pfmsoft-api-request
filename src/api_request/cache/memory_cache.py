"""In-memory cache implementations for API requests.

These caches are primarily intended for tests and local development where a
persistent backing store is unnecessary.
"""

from types import TracebackType
from typing import Self
from uuid import UUID

from .models import CachedResponse, CacheInfo
from .protocols import CacheProtocol


class InMemoryCache(CacheProtocol):
    """Dictionary-backed cache implementation.

    The cache stores `CachedResponse` objects in memory and performs no I/O.
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory cache."""
        self._entries: dict[UUID, CachedResponse] = {}

    async def __aenter__(self) -> Self:
        """Enter the asynchronous context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the asynchronous context manager."""
        _ = exc_type, exc_value, traceback

    async def get(self, cache_key: UUID) -> CachedResponse | None:
        """Get a cached response by cache key."""
        return self._entries.get(cache_key)

    async def set(self, cache_key: UUID, cached_response: CachedResponse) -> None:
        """Set a cached response in the cache."""
        self._entries[cache_key] = cached_response

    async def update(self, cache_key: UUID, cached_response: CachedResponse) -> None:
        """Update an existing cached response in the cache."""
        self._entries[cache_key] = cached_response

    async def delete(self, cache_key: UUID) -> None:
        """Delete a cached response from the cache."""
        self._entries.pop(cache_key, None)

    async def clear(
        self, only_expired: bool = False, age_limit: int | None = None
    ) -> None:
        """Clear cached entries matching the requested filters.

        Args:
            only_expired: When true, remove only expired entries.
            age_limit: When provided, remove entries with `cache_age` greater
                than or equal to this nanosecond threshold.
        """
        if not only_expired and age_limit is None:
            self._entries.clear()
            return

        removable_keys: list[UUID] = []
        for cache_key, cached_response in self._entries.items():
            is_expired_match = only_expired and cached_response.is_expired
            is_age_match = (
                age_limit is not None and cached_response.cache_age >= age_limit
            )
            if is_expired_match or is_age_match:
                removable_keys.append(cache_key)

        for cache_key in removable_keys:
            del self._entries[cache_key]

    async def flush(self) -> None:
        """Flush the cache.

        This implementation has no buffered writes, so flush is a no-op.
        """
        return None

    async def cache_info(self) -> CacheInfo:
        """Return summary information about the cache."""
        return CacheInfo(size=len(self._entries))
