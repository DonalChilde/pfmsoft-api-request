"""Manage the metadata for the OAuth2 flow."""

import logging
import sqlite3

from httpx2 import Client
from jwt import PyJWKClient
from pydantic_core import from_json, to_json
from whenever import Instant

from esi_link import USER_AGENT
from esi_link.app_data.helpers import transaction
from esi_link.auth.models import OAuthMetadataTimestamped
from esi_link.settings import OAUTH_METADATA_URL

logger = logging.getLogger(__name__)

# TODO refactor fetch code and models to be like compatibility dates and schema cache.


class OAuthMetadataSqliteCache:
    def __init__(
        self,
        connection: sqlite3.Connection,
        session: Client,
        cache_ttl: int = 86400,
        metadata_url: str = OAUTH_METADATA_URL,
    ):
        """Manage the disk cache for OAuth metadata.

        Args:
            connection: The SQLite connection to use for caching metadata.
            cache_ttl: Time-to-live for the cached metadata, in seconds. Default is 86400 (1 day).
            metadata_url: The URL to fetch the metadata from if the cache is expired or does not exist. Default is OAUTH_METADATA_URL.
        """
        self._connection = connection
        self._session = session
        self._cache_ttl = cache_ttl
        self._metadata_url = metadata_url
        self._cached_metadata: OAuthMetadataTimestamped | None = None
        self._jwks_client: PyJWKClient | None = None
        self._timestamped_metadata: OAuthMetadataTimestamped | None = None
        self._initialize_cache()

    def _load_metadata_from_db(self) -> OAuthMetadataTimestamped | None:
        """Load the cached metadata from db."""
        sql = "SELECT timestamped, metadata_json FROM OauthMetadataCache WHERE id = 0"
        with transaction(self._connection) as conn:
            row = conn.execute(sql).fetchone()
            if row is None:
                logger.info("No cached OAuth metadata found in database.")
                return None
            timestamped = row["timestamped"]
            metadata = from_json(row["metadata_json"])
            return OAuthMetadataTimestamped(
                metadata=metadata,
                timestamp=timestamped,
            )

    def _fetch_metadata_from_url(self) -> OAuthMetadataTimestamped:
        """Fetch the metadata from the URL."""
        response = self._session.get(
            self._metadata_url, headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()
        metadata = response.json()
        return OAuthMetadataTimestamped(
            metadata=metadata, timestamp=Instant.now().timestamp_nanos()
        )

    def _save_metadata_to_cache(self, metadata: OAuthMetadataTimestamped) -> None:
        """Save the metadata to disk."""
        metadata_json = to_json(metadata.metadata)
        sql = """
        REPLACE INTO OauthMetadataCache (id, timestamped, metadata_json)
        VALUES (0, ?, ?)
        """
        with transaction(self._connection) as conn:
            conn.execute(sql, (metadata.timestamp, metadata_json))
            logger.info(
                "Saved new OAuth metadata to cache with timestamp %d",
                metadata.timestamp,
            )

    def _is_cache_valid(self) -> bool:
        """Check if the cached metadata is still valid based on the TTL."""
        if self._cached_metadata is None:
            logger.info("No cached metadata found, cache is not valid.")
            return False
        now = Instant.now()
        cache_time = self._cached_metadata.timestamp_instant
        age = (now - cache_time).total("seconds")
        if age < self._cache_ttl:
            logger.info(
                f"Cached metadata is valid (age: {age:.2f} seconds, TTL: {self._cache_ttl} seconds)."
            )
            return True
        else:
            logger.info(
                f"Cached metadata is expired (age: {age:.2f} seconds, TTL: {self._cache_ttl} seconds)."
            )
            return False

    def _fetch_and_cache_metadata(self) -> None:
        """Fetch the metadata from the URL and save it to the cache."""
        fetched_metadata = self._fetch_metadata_from_url()
        self._save_metadata_to_cache(fetched_metadata)
        self._cached_metadata = fetched_metadata

    def _initialize_cache(self) -> None:
        """Initialize the cache by loading metadata from the database or fetching from the URL if necessary."""
        cached_metadata = self._load_metadata_from_db()
        self._cached_metadata = cached_metadata

        if not self._is_cache_valid():
            self._fetch_and_cache_metadata()

    # def __enter__(self) -> Self:
    #     """Load the metadata, either from cache or from the URL if the cache is invalid."""
    #     cached_metadata = self._load_metadata_from_db()
    #     if cached_metadata is not None and self._is_cache_valid():
    #         self._cached_metadata = cached_metadata
    #     else:
    #         fetched_metadata = self._fetch_metadata_from_url()
    #         self._save_metadata_to_cache(fetched_metadata)
    #         self._cached_metadata = fetched_metadata
    #     return self

    # def __exit__(
    #     self,
    #     exc_type: type[BaseException] | None,
    #     exc_val: BaseException | None,
    #     exc_tb: TracebackType | None,
    # ) -> None:
    #     """Clean up any resources if necessary. In this case, there are no resources to clean up."""
    #     pass

    def get(self) -> OAuthMetadataTimestamped:
        """Get the current OAuth metadata, either from cache or freshly fetched."""
        if self._cached_metadata is None:
            raise ValueError("OAuth metadata is not loaded.")
        if not self._is_cache_valid():
            self._fetch_and_cache_metadata()
        return self._cached_metadata

    # @property
    # def jwks_client(self) -> PyJWKClient:
    #     """Get a PyJWKClient for the JWKS URI provided in the metadata."""
    #     if self._jwks_client is None:
    #         self._jwks_client = PyJWKClient(
    #             self.metadata.jwks_uri, headers={"User-Agent": USER_AGENT}
    #         )
    #     return self._jwks_client
