# """A JSON-based disk cache implementation."""

# from dataclasses import replace
# from pathlib import Path
# from types import TracebackType
# from typing import Any, Self
# from uuid import UUID

# from pydantic import RootModel
# from whenever import Instant

# from esi_link.cache.models import (
#     CachedResponse,
# )
# from esi_link.execution.models import HttpResponse
# from esi_link.protocols.cache_manager import CacheManagerProtocol

# CachedResponseRoot = RootModel[CachedResponse]


# class JsonDiskCache(CacheManagerProtocol):
#     def __init__(self, cache_directory: Path):
#         """A disk-based cache implementation using json files in a single directory.

#         Args:
#             cache_directory: The directory where cached responses will be stored.
#         """
#         self.cache_directory = cache_directory
#         self.cache_directory.mkdir(parents=True, exist_ok=True)

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
#         pass

#     async def get(self, key: UUID) -> CachedResponse | None:
#         """Get a value from the disk cache."""
#         response_path = self.cache_directory.joinpath(f"{key}.json")
#         if not response_path.exists():
#             return None
#         response = CachedResponseRoot.model_validate_json(
#             response_path.read_text()
#         ).root
#         return response

#     async def set(self, key: UUID, http_response: HttpResponse) -> CachedResponse:
#         """Set a value in the disk cache."""
#         cached_response = CachedResponse(
#             cache_key=key,
#             cached_at=Instant.now(),
#             http_response=http_response,
#             expires_at=http_response.expires_at,
#         )
#         response_path = self.cache_directory.joinpath(f"{key}.json")
#         response_path.write_text(
#             CachedResponseRoot(cached_response).model_dump_json(indent=2)
#         )
#         return cached_response

#     async def refresh(
#         self, key: UUID, new_http_response: HttpResponse
#     ) -> CachedResponse:
#         """Refresh a value in the disk cache."""
#         cached_response = await self.get(key)
#         if cached_response is None:
#             raise KeyError(f"No cached response found for key {key} to refresh.")
#         data = cached_response.http_response.text
#         updated_http_response = replace(cached_response.http_response, text=data)
#         return await self.set(key, updated_http_response)

#     async def clear(self, only_stale: bool = False) -> int:
#         """Clear all cached responses from the cache."""
#         count = 0
#         for file in self.cache_directory.glob("*.json"):
#             if only_stale:
#                 response = CachedResponseRoot.model_validate_json(file.read_text()).root
#                 if not response.is_expired:
#                     continue
#             file.unlink()
#             count += 1
#         return count

#     async def cache_info(self) -> dict[str, Any]:
#         """Get information about the cache, such as size, number of entries, etc."""
#         directory_size = sum(
#             file.stat().st_size for file in self.cache_directory.glob("*.json")
#         )
#         return {
#             "path": self.cache_directory,
#             "size": directory_size,
#             "entries": len(list(self.cache_directory.glob("*.json"))),
#         }
