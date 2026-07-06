"""Protocols module for API requests."""

from collections.abc import Callable, Hashable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from api_request.models import (
    CachedResponse,
    CacheInfo,
    FailedResponse,
    Request,
    Response,
)


class CacheProtocol(Protocol):
    async def __aenter__(self) -> Self:
        """Enter the asynchronous context manager."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the asynchronous context manager."""
        ...

    async def get(self, cache_key: UUID) -> CachedResponse | None:
        """Get a cached response by cache key."""
        ...

    async def set(self, cache_key: UUID, cached_response: CachedResponse) -> None:
        """Set a cached response in the cache."""
        ...

    async def update(self, cache_key: UUID, cached_response: CachedResponse) -> None:
        """Update an existing cached response in the cache."""
        ...

    async def delete(self, cache_key: UUID) -> None:
        """Delete a cached response from the cache."""
        ...

    async def clear(
        self, only_expired: bool = False, age_limit: int | None = None
    ) -> None:
        """Clear the cache, optionally only removing expired entries or entries older than a certain age."""
        ...

    async def flush(self) -> None:
        """Flush the cache to ensure all changes are persisted."""
        ...

    async def cache_info(self) -> CacheInfo:
        """Get cache information such as size and number of entries."""
        ...


class ApiRequesterProtocol[T: Hashable](Protocol):
    async def process_requests(
        self,
        requests: dict[UUID, Request[T]],
    ) -> dict[UUID, Response[T] | FailedResponse[T]]:
        """Process a batch of API requests and return their corresponding cached responses."""
        ...


CacheFactory = Callable[[], CacheProtocol]
