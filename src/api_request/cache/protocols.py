"""Cache protocols for API requests."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from api_request.cache.models import CachedResponse, CacheInfo
from api_request.request.models import ResponseMetadata


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

    async def set(
        self, cache_key: UUID, text: str, metadata: ResponseMetadata
    ) -> CachedResponse:
        """Create or replace a cached response for a key.

        Implementations must treat inputs as immutable and build a new
        `CachedResponse` from the provided values.

        Contract:
            - Upsert behavior: create when missing, replace when present.
            - `cache_timestamp` is set to the current update time in nanoseconds.
            - `etag` and `last_modified` are derived from `metadata`.
            - At least one validator (`etag` or `last_modified`) must be present;
              raise `ValueError` if both are missing.

        Args:
            cache_key: Cache entry key.
            text: Response body text to store.
            metadata: Response metadata used to populate validator/expiry fields.

        Returns:
            The stored `CachedResponse`.

        Raises:
            ValueError: If both `metadata.etag` and `metadata.last_modified` are missing.
        """
        ...

    async def update_304(
        self, cache_key: UUID, metadata: ResponseMetadata
    ) -> CachedResponse:
        """Refresh an existing cached response from a 304 revalidation.

        This operation updates metadata fields while preserving the existing cached
        body text and cached-success representation.

        Contract:
            - Entry must already exist for `cache_key`.
            - Response text is preserved from the existing entry.
            - Stored and returned metadata must continue to represent the cached body
              as a successful response rather than a raw `304 Not Modified`
              response.
            - Metadata-derived fields are refreshed by merging the existing cached
              metadata with the revalidation response headers and timing data.
            - The merged result is then used to populate `response_metadata_json`,
              `etag`, `last_modified`, and `expires_at`.
            - `cache_timestamp` is set to the current update time in nanoseconds.
            - At least one validator (`etag` or `last_modified`) must be present in
              `metadata`; raise `ValueError` if both are missing.

        Args:
            cache_key: Cache entry key.
            metadata: Fresh metadata returned from a `304 Not Modified`
                revalidation request. Implementations merge this with the
                existing cached metadata so the stored representation remains a
                successful cached response.

        Returns:
            The updated `CachedResponse`.

        Raises:
            KeyError: If `cache_key` does not exist.
            ValueError: If both `metadata.etag` and `metadata.last_modified` are missing.
        """
        ...

    async def delete(self, cache_key: UUID) -> None:
        """Delete a cached response from the cache."""
        ...

    async def clear(
        self, only_expired: bool = False, age_limit: int | None = None
    ) -> None:
        """Clear cache entries matching filter criteria.

        Filter behavior:
            - `only_expired=True`: remove only expired entries.
            - `age_limit` set: remove entries whose age is greater than or equal to
              the nanosecond threshold.
            - both set: remove entries that satisfy both criteria.
            - neither set: remove all entries.
        """
        ...

    async def flush(self) -> None:
        """Flush pending cache writes to durable storage.

        Implementations that do not buffer writes may treat this as a no-op.
        """
        ...

    async def cache_info(self) -> CacheInfo:
        """Get cache information such as size and number of entries."""
        ...


CacheFactory = Callable[[], CacheProtocol]


class CacheFactoryProtocol(Protocol):
    """A protocol for a cache factory that produces instances of CacheProtocol.

    This protocol defines a callable that returns a new instance of a cache provider
    that adheres to the CacheProtocol. It is used to create cache instances for use
    with the ApiRequester, allowing for different caching strategies to be implemented
    and swapped as needed.
    """

    def __call__(self) -> CacheProtocol:
        """Build and return a configured cache instance."""
        ...
