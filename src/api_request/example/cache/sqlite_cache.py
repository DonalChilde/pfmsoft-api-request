import logging
import sqlite3
from typing import Any
from uuid import UUID

from whenever import Instant

from esi_link.app_data.helpers import transaction
from esi_link.cache.models import CachedResponse
from esi_link.execution.models import HttpResponse

logger = logging.getLogger(__name__)


class CacheManagerSqlite:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    async def _save_cached_response(self, cached_response: CachedResponse) -> None:
        with transaction(self._connection) as conn:
            conn.execute(
                """
                REPLACE INTO WebCache (cache_key, response_text, response_metadata_json, etag, expires_at, timestamped)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(cached_response.cache_key),
                    cached_response.response_text,
                    cached_response.response_metadata_json,
                    cached_response.etag,
                    cached_response.expires_at,
                    cached_response.timestamped,
                ),
            )

    async def _load_cached_response(self, key: UUID) -> CachedResponse | None:
        with transaction(self._connection) as conn:
            row = conn.execute(
                "SELECT cache_key, response_text, response_metadata_json, etag, expires_at, timestamped FROM WebCache WHERE cache_key = ?",
                (str(key),),
            ).fetchone()
            if row is None:
                return None
            response = CachedResponse(
                cache_key=UUID(row["cache_key"]),
                response_text=row["response_text"],
                response_metadata_json=row["response_metadata_json"],
                etag=row["etag"],
                expires_at=row["expires_at"],
                timestamped=row["timestamped"],
            )
            return response

    async def _delete_cached_response(self, key: UUID) -> None:
        with transaction(self._connection) as conn:
            conn.execute(
                "DELETE FROM WebCache WHERE cache_key = ?",
                (str(key),),
            )

    async def _clear_cache(self, only_stale: bool = False) -> None:
        with transaction(self._connection) as conn:
            if only_stale:
                conn.execute(
                    "DELETE FROM WebCache WHERE expires_at IS NOT NULL AND expires_at <= ?",
                    (Instant.now().timestamp(),),
                )
            else:
                conn.execute("DELETE FROM WebCache")

    async def get(self, key: UUID) -> CachedResponse | None:
        """Get a cached response by cache key."""
        response = await self._load_cached_response(key)
        if response is None:
            logger.info(f"Cache miss for key {key}")
            return None
        else:
            logger.info(
                "Cache hit for key %s, expires in %s seconds",
                key,
                (response.expires_at - Instant.now().timestamp())
                if response.expires_at is not None
                else "unknown",
            )
            return response

    async def set(self, key: UUID, http_response: HttpResponse) -> CachedResponse:
        """Set a cached response in the cache."""
        cached_response = CachedResponse(
            cache_key=key,
            response_text=http_response.text,
            response_metadata_json=http_response.metadata.as_bytes,
            etag=http_response.etag,
            expires_at=http_response.expires_at,
            timestamped=Instant.now().timestamp_nanos(),
        )
        await self._save_cached_response(cached_response)
        logger.info(
            "Cached response for key %s, url: %s with expiration in %s seconds",
            cached_response.cache_key,
            http_response.metadata.url,
            (cached_response.expires_at - Instant.now().timestamp())
            if cached_response.expires_at is not None
            else "unknown",
        )
        return cached_response

    async def refresh(
        self, key: UUID, new_http_response: HttpResponse
    ) -> CachedResponse:
        """Refresh an existing cached response with new response data."""
        cached_response = await self._load_cached_response(key)
        if cached_response is None:
            logger.info("No cached response found for key %s to refresh.", key)
            raise KeyError(f"No cached response found for key {key} to refresh.")
        logger.info("Refreshing cache for key %s.", key)
        updated_http_response = HttpResponse(
            metadata=new_http_response.metadata,
            text=cached_response.response_text,
        )
        updated_cached_response = await self.set(
            key=key, http_response=updated_http_response
        )
        return updated_cached_response

    async def delete(self, key: UUID) -> None:
        """Delete a cached response from the cache."""
        await self._delete_cached_response(key)
        logger.info(f"Deleted cached response for key {key} from cache.")

    async def clear(self, only_stale: bool = False) -> None:
        """Clear all cached responses from the cache."""
        await self._clear_cache(only_stale=only_stale)
        logger.info(
            f"Cleared {'stale ' if only_stale else ''}cached responses from cache."
        )

    async def cache_info(self) -> dict[str, Any]:
        """Get information about the cache, such as the number of cached responses, total size, etc."""
        raise NotImplementedError(
            "Cache info is not implemented for CacheManagerSqlite yet."
        )
