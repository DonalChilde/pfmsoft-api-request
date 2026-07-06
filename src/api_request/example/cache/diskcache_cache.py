# """A disk-based cache implementation for ESI responses using the diskcache library."""

# import logging
# from dataclasses import replace
# from pathlib import Path
# from types import TracebackType
# from typing import Any, Self
# from uuid import UUID

# from diskcache import Cache  # type: ignore
# from whenever import Instant

# from esi_link.cache.models import (
#     CachedResponse,
# )
# from esi_link.execution.models import HttpResponse
# from esi_link.protocols.cache_manager import CacheManagerProtocol

# logger = logging.getLogger(__name__)


# class DiskCache(CacheManagerProtocol):
#     def __init__(self, cache_directory: Path, local_max_age_seconds: int = 3600):
#         """A disk-based cache implementation using the diskcache library.

#         Local expiration checks can be performed using the local_max_age_seconds parameter,
#         which determines how long a cached response is considered fresh before it is
#         treated as stale. This allows for more aggressive cache invalidation based on
#         local rules, in addition to the standard HTTP caching headers.

#         Args:
#             cache_directory: The directory where cached responses will be stored.
#             local_max_age_seconds: The maximum age in seconds for a cached response to
#                 be considered fresh. This is used for local expiration checks before considering the response stale based on its expires_at value.
#         """
#         self.cache_directory = cache_directory
#         self.cache = Cache(cache_directory)
#         self.local_max_age_seconds = local_max_age_seconds

#     async def __aenter__(self) -> Self:
#         """Enter the runtime context related to this object, which will automatically open the disk cache."""
#         self.cache.__enter__()
#         return self

#     async def __aexit__(
#         self,
#         exc_type: type[BaseException] | None,
#         exc_value: BaseException | None,
#         traceback: TracebackType | None,
#     ) -> bool | None:
#         """Exit the runtime context related to this object, which will automatically close the disk cache."""
#         self.cache.__exit__(exc_type, exc_value, traceback)  # type: ignore

#     async def get(self, key: UUID) -> CachedResponse | None:
#         """Get a value from the disk cache."""
#         response = self.cache.get(str(key))  # type: ignore
#         if response is None:
#             logger.info(f"Cache miss for key {key}")
#             return None
#         if not isinstance(response, CachedResponse):
#             logger.error(
#                 f"Cached value for key {key} is not of type CachedResponse, got {type(response)}"  # type: ignore
#             )
#             raise ValueError(
#                 f"Cached value for key {key} is not of type CachedResponse, got {type(response)}"  # type: ignore
#             )
#         logger.info(
#             f"Cache hit for key {key}, is_expired: {response.is_expired}, cached at {response.cached_at}, expires at {response.expires_at}"
#         )
#         return response

#     async def set(self, key: UUID, http_response: HttpResponse) -> CachedResponse:
#         """Set a value in the disk cache."""
#         cached_response = CachedResponse(
#             cache_key=key,
#             cached_at=Instant.now(),
#             http_response=http_response,
#             expires_at=http_response.expires_at,
#         )
#         self.cache.set(str(key), cached_response)  # type: ignore
#         logger.info(
#             f"Cached response for key {key} with expiration at {cached_response.expires_at}"
#         )
#         return cached_response

#     async def refresh(
#         self, key: UUID, new_http_response: HttpResponse
#     ) -> CachedResponse:
#         """Refresh a value in the disk cache."""
#         cached_response = await self.get(key)
#         if cached_response is None:
#             logger.info(f"No cached response found for key {key} to refresh.")
#             raise KeyError(f"No cached response found for key {key} to refresh.")
#         logger.info(
#             f"Refreshing cache for key {key} with new HTTP response received at {new_http_response.received_timestamp}"
#         )
#         data = cached_response.http_response.text
#         updated_http_response = replace(cached_response.http_response, text=data)

#         return await self.set(key, updated_http_response)

#     async def clear(self, only_stale: bool = False) -> int:
#         """Clear all cached responses from the cache."""
#         if only_stale:
#             keys_to_delete: list[str] = [
#                 key
#                 for key, response in self.cache.items()  # type: ignore
#                 if response.is_expired  # type: ignore
#             ]
#             for key in keys_to_delete:
#                 self.cache.delete(key)  # type: ignore
#             return len(keys_to_delete)
#         return self.cache.clear()

#     async def cache_info(self) -> dict[str, Any]:
#         """Get information about the cache, such as size, number of entries, etc."""
#         return {
#             "path": self.cache_directory,
#             "size": self.cache.volume(),
#             "entries": len(self.cache),  # type: ignore
#         }
