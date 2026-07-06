# """This module defines the CacheManagerProtocol, which is an interface for managing cached responses in the ESI Link system."""

# from types import TracebackType
# from typing import Any, Self
# from uuid import UUID

# from esi_link.cache.models import CachedResponse
# from esi_link.execution.models import HttpResponse


# class CacheManagerProtocol:
#     """An Interface for managing cached responses in the ESI Link system.

#     Returned CachedResponses should not have any connection to the cache data.
#     This would happen naturally with some cache implemetations, like a per file cache
#     where each CachedResponse is read from a separate file, but for in-memory caches
#     we need to make sure that the CachedResponse instances returned by get, set, and
#     refresh are copies of the data stored in the cache, to avoid unintended side effects
#     from modifying the returned CachedResponse directly. This should be called out in
#     the docstrings for these methods, and we should make sure to implement this behavior
#     in any in-memory cache implementations.
#     """

#     # TODO batch writes to the cache, and provide a hot cache for recently accessed items.
#     # See Claude's suggestions for cache management strategies.
#     async def __aenter__(self) -> Self:
#         """Enter the runtime context related to this object."""
#         return self

#     async def __aexit__(
#         self,
#         exc_type: type[BaseException] | None,
#         exc_value: BaseException | None,
#         traceback: TracebackType | None,
#     ) -> bool | None:
#         """Exit the runtime context related to this object."""
#         ...

#     async def get(self, key: UUID) -> CachedResponse | None:
#         """Get a cached response by cache key.

#         Returned CachedResponse must be treated as immutable. If the caller needs to
#         modify the CachedResponse, they should create a copy of it before making any
#         modifications, to avoid unintended side effects on the cached response stored in
#         the cache manager. Modifying the returned CachedResponse directly may lead to
#         issues such as stale data being returned for other requests that share the same
#         cache key, or inconsistencies in the cache state if the CachedResponse is updated
#         with new data while it is being modified by the caller.

#         Args:
#             key: The UUID key for the cached response.

#         Returns:
#             The CachedResponse if found, or None if not found.
#         """
#         ...

#     async def set(self, key: UUID, http_response: HttpResponse) -> CachedResponse:
#         """Set a cached response in the cache.

#         Returned CachedResponse must be treated as immutable. If the caller needs to
#         modify the CachedResponse, they should create a copy of it before making any
#         modifications, to avoid unintended side effects on the cached response stored in
#         the cache manager. Modifying the returned CachedResponse directly may lead to
#         issues such as stale data being returned for other requests that share the same
#         cache key, or inconsistencies in the cache state if the CachedResponse is updated
#         with new data while it is being modified by the caller.

#         Args:
#             key: The UUID key for the cached response.
#             http_response: The new HttpResponse to store in the cache.

#         Returns:
#             The CachedResponse instance that was set in the cache.
#         """
#         ...

#     async def refresh(
#         self, key: UUID, new_http_response: HttpResponse
#     ) -> CachedResponse:
#         """Refresh an existing cached response with new response data.

#         Returned CachedResponse must be treated as immutable. If the caller needs to
#         modify the CachedResponse, they should create a copy of it before making any
#         modifications, to avoid unintended side effects on the cached response stored in
#         the cache manager. Modifying the returned CachedResponse directly may lead to
#         issues such as stale data being returned for other requests that share the same
#         cache key, or inconsistencies in the cache state if the CachedResponse is updated
#         with new data while it is being modified by the caller.

#         Args:
#             key: The UUID key for the cached response to refresh.
#             new_http_response: The new HttpResponse to update the cached response with.

#         Returns:
#             The updated CachedResponse instance after refreshing.

#         Raises:
#             KeyError: If no cached response exists for the given cache key.
#         """
#         ...

#     async def clear(self, only_stale: bool = False) -> int:
#         """Clear all cached responses from the cache.

#         Args:
#             only_stale: If True, only clear stale cached responses.

#         Returns:
#             The number of cached responses that were cleared.
#         """
#         ...

#     async def cache_info(self) -> dict[str, Any]:
#         """Get information about the cache, such as size, number of entries, etc.

#         Returns:
#             A dictionary containing information about the cache.
#         """
#         ...
