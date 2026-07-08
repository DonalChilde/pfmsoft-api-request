"""In-memory cache implementations for API requests.

These caches are primarily intended for tests and local development where a
persistent backing store is unnecessary.

Behavior summary:
    - Storage is process-local and non-durable.
    - `set` performs upsert semantics.
    - `update_304` preserves cached body text and merges metadata.
    - `flush` is a no-op.
"""

from types import TracebackType
from typing import Self
from uuid import UUID

from whenever import Instant

from ..request.models import ResponseMetadata, ResponseMetadataRoot
from .metadata_helpers import merge_cached_revalidation_metadata
from .models import CachedResponse, CacheInfo
from .protocols import CacheFactoryProtocol, CacheProtocol


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
        """Get a cached response by key, or None when missing."""
        return self._entries.get(cache_key)

    @staticmethod
    def _ensure_validators(metadata: ResponseMetadata) -> None:
        """Ensure at least one cache validator is present."""
        if metadata.etag is None and metadata.last_modified is None:
            raise ValueError("Cached responses require etag or last_modified")

    @staticmethod
    def _build_cached_response(
        *,
        cache_key: UUID,
        text: str,
        metadata: ResponseMetadata,
    ) -> CachedResponse:
        """Build a CachedResponse from response text and metadata."""
        InMemoryCache._ensure_validators(metadata)
        return CachedResponse(
            cache_key=cache_key,
            response_text=text,
            response_metadata_json=metadata.as_string,
            etag=metadata.etag,
            last_modified=metadata.last_modified,
            expires_at=metadata.expires_at,
            cache_timestamp=Instant.now().timestamp_nanos(),
        )

    async def set(
        self, cache_key: UUID, text: str, metadata: ResponseMetadata
    ) -> CachedResponse:
        """Create or replace a cached response entry.

        Raises:
            ValueError: If both metadata validators are absent.
        """
        cached_response = self._build_cached_response(
            cache_key=cache_key,
            text=text,
            metadata=metadata,
        )
        self._entries[cache_key] = cached_response
        return cached_response

    async def update_304(
        self, cache_key: UUID, metadata: ResponseMetadata
    ) -> CachedResponse:
        """Refresh a stale entry from 304 metadata while preserving body text.

        Raises:
            KeyError: If no existing entry is present.
            ValueError: If merged metadata lacks both validators.
        """
        existing = self._entries.get(cache_key)
        if existing is None:
            raise KeyError(f"No cached response found for key {cache_key}")

        existing_metadata = ResponseMetadataRoot.model_validate_json(
            existing.response_metadata_json
        ).root
        merged_metadata = merge_cached_revalidation_metadata(
            cached=existing_metadata,
            refreshed=metadata,
        )

        cached_response = self._build_cached_response(
            cache_key=cache_key,
            text=existing.response_text,
            metadata=merged_metadata,
        )
        self._entries[cache_key] = cached_response
        return cached_response

    async def delete(self, cache_key: UUID) -> None:
        """Delete a cached response from the cache.

        This operation is idempotent and does not raise for missing keys.
        """
        self._entries.pop(cache_key, None)

    async def clear(
        self, only_expired: bool = False, age_limit: int | None = None
    ) -> None:
        """Clear cached entries matching the requested filters.

        Args:
            only_expired: When true, remove only expired entries.
            age_limit: When provided, remove entries with `cache_age` greater
                than or equal to this nanosecond threshold.

        Notes:
            When both filters are provided, entries must satisfy both.
        """
        if not only_expired and age_limit is None:
            self._entries.clear()
            return

        removable_keys: list[UUID] = []
        for cache_key, cached_response in self._entries.items():
            is_expired_match = not only_expired or cached_response.is_expired
            is_age_match = age_limit is None or cached_response.cache_age >= age_limit
            if is_expired_match and is_age_match:
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


class InMemoryCacheFactory(CacheFactoryProtocol):
    """Factory for creating InMemoryCache instances.

    The InMemoryCache class takes no arguments, so this factory simply returns a new
    instance of InMemoryCache.
    """

    def __call__(self) -> CacheProtocol:
        """Create and return a new in-memory cache instance."""
        return InMemoryCache()
