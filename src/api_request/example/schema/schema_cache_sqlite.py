"""A simple schema cache that stores ESI schema data in a SQLite database."""

import sqlite3
from dataclasses import dataclass

from httpx2 import Client
from pydantic import RootModel
from pydantic_core import from_json, to_json
from whenever import Instant

from esi_link.app_data.helpers import transaction
from esi_link.schema.compatibility_dates_cache_sqlite import (
    CompatibilityDatesCacheSQLite,
)
from esi_link.schema.helpers import fetch_versioned_schema, resolve_schema
from esi_link.schema.models import EsiSchema


@dataclass(slots=True, kw_only=True, frozen=True)
class CachedSchema:
    """Represents a cached ESISchema, and the timestamp of when it was fetched."""

    esi_schema: EsiSchema
    """The ESISchema"""
    timestamp: int
    """Nanoseconds since the Unix epoch when the schema was fetched."""

    def is_expired(self, ttl: int) -> bool:
        """Check if the cached schema has expired based on the provided TTL."""
        return (Instant.now() - self.timestamp_instant).total("seconds") > ttl

    def expires_in(self, ttl: int) -> int:
        """Return the number of seconds until the cached schema expires, or a negative number if it is already expired."""
        return ttl - int((Instant.now() - self.timestamp_instant).total("seconds"))

    @property
    def timestamp_instant(self) -> Instant:
        """Return the timestamp of when the schema was fetched as an Instant."""
        return Instant.from_timestamp_nanos(self.timestamp)

    def to_string(self, indent: int) -> str:
        """Return a string representation of the cached schema with the specified indentation."""
        root_model = CachedSchemaRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> CachedSchema:
        """Parse the cached schema from a JSON string."""
        value = CachedSchemaRoot.model_validate_json(json_str).root
        return value


CachedSchemaRoot = RootModel[CachedSchema]


@dataclass(slots=True, kw_only=True, frozen=True)
class AvailableCachedSchema:
    """Represents an available cached schema, including the compatibility date and the timestamp of when it was fetched."""

    compatibility_date: str
    timestamp: int
    """Nanoseconds since the Unix epoch when the schema was fetched."""
    seconds_remaining: int
    """Number of seconds until the cached schema expires, or a negative number if it is already expired."""

    @property
    def timestamp_instant(self) -> Instant:
        """Return the timestamp of when the schema was fetched as an Instant."""
        return Instant.from_timestamp_nanos(self.timestamp)


class SchemaCacheSqlite:
    def __init__(
        self,
        connection: sqlite3.Connection,
        session: Client,
        dates_cache: CompatibilityDatesCacheSQLite,
        ttl: int = 2_592_000,
    ):
        """A simple schema cache that stores ESI schema data in a SQLite database."""
        self._connection = connection
        self._session = session
        self._compatibility_dates_cache = dates_cache
        self._cached_schemas: dict[str, CachedSchema] = {}
        self._ttl = ttl

    def _load_schema_from_db(self, compatibility_date: str) -> CachedSchema | None:
        """Load a cached schema from the database for the given compatibility date."""
        sql = "SELECT timestamped, schema_json FROM SchemaCache WHERE compatibility_date = ?"
        with transaction(self._connection) as conn:
            row = conn.execute(sql, (compatibility_date,)).fetchone()
            if row is None:
                return None
            timestamped, schema_json = row

        esi_schema = EsiSchema(dereferenced_schema=from_json(schema_json))
        cached_schema = CachedSchema(esi_schema=esi_schema, timestamp=timestamped)
        return cached_schema

    def _save_schema_to_db(self, cached_schema: CachedSchema) -> None:
        """Save a cached schema to the database for the given compatibility date."""
        sql = """
        REPLACE INTO SchemaCache (timestamped, compatibility_date, schema_json)
        VALUES (?, ?, ?)
        
        """
        with transaction(self._connection) as conn:
            conn.execute(
                sql,
                (
                    cached_schema.timestamp,
                    cached_schema.esi_schema.compatibility_date,
                    to_json(cached_schema.esi_schema.dereferenced_schema),
                ),
            )

    def _fetch_schema_for_date(self, compatibility_date: str) -> CachedSchema:
        """Fetch the ESI schema for the given compatibility date from the ESI endpoint.

        Args:
            compatibility_date: The compatibility date to fetch the schema for.

        Returns:
            A CachedSchema object containing the fetched schema and the timestamp of when it was fetched.

        Raises:
            ValueError: If the compatibility date is not in the list of available compatibility dates.
        """
        cached_dates = self._compatibility_dates_cache.compatibility_dates
        if compatibility_date not in cached_dates.compatibility_dates:
            raise ValueError(
                f"Compatibility date {compatibility_date} is not in the list of available "
                f"compatibility dates: {cached_dates.compatibility_dates}"
            )
        timestamped_schema = fetch_versioned_schema(
            session=self._session, compatibility_date=compatibility_date
        )
        resolved_schema = resolve_schema(timestamped_schema)
        esi_schema = EsiSchema(dereferenced_schema=resolved_schema.schema)
        cached_schema = CachedSchema(
            esi_schema=esi_schema, timestamp=timestamped_schema.timestamp
        )
        return cached_schema

    def _is_cached_schema_expired(self, cached_schema: CachedSchema, ttl: int) -> bool:
        """Check if the cached schema has expired based on the provided TTL."""
        return cached_schema.is_expired(ttl)

    def fetch_and_cache_schema(self, compatibility_date: str) -> CachedSchema:
        """Fetch the ESI schema for the given compatibility date and cache it in the database.

        This method will fetch the schema from the ESI endpoint and save it to the
        database, regardless of whether there is already a cached schema in the database
        or not. It does not check if there is a valid cached schema in the database before
        fetching a new one.

        Args:
            compatibility_date: The compatibility date to fetch the schema for.

        Returns:
            A CachedSchema object containing the fetched schema and the timestamp of when it was fetched.
        """
        cached_schema = self._fetch_schema_for_date(compatibility_date)
        self._save_schema_to_db(cached_schema)
        return cached_schema

    def cached_schemas(self) -> list[AvailableCachedSchema]:
        """Return a list of available cached schemas, including their compatibility dates and timestamps."""
        sql = "SELECT compatibility_date, timestamped FROM SchemaCache"
        with transaction(self._connection) as conn:
            rows = conn.execute(sql).fetchall()
        available_schemas: list[AvailableCachedSchema] = []
        for row in rows:
            compatibility_date = row["compatibility_date"]
            timestamp = row["timestamped"]
            seconds_remaining = self._ttl - int(
                (Instant.now() - Instant.from_timestamp_nanos(timestamp)).total(
                    "seconds"
                )
            )
            available_schemas.append(
                AvailableCachedSchema(
                    compatibility_date=compatibility_date,
                    timestamp=timestamp,
                    seconds_remaining=seconds_remaining,
                )
            )
        return available_schemas

    def schema_versions(self) -> list[str]:
        """Return a list of possible schema compatibility dates."""
        cached_dates = self._compatibility_dates_cache.compatibility_dates
        versions = cached_dates.compatibility_dates
        return versions

    def get_cached_schema(self, compatibility_date: str) -> CachedSchema:
        """Get a cached schema for the given compatibility date.

        Either from the database or freshly fetched if it is not in the database or has expired.

        Args:
            compatibility_date: The compatibility date to get the cached schema for.

        Returns:
            A CachedSchema object containing the cached schema and the timestamp of when
                it was fetched.

        Raises:
            ValueError: If the compatibility date is not in the list of available compatibility dates.
        """
        # First check if the cached schema is in memory and not expired.
        memory_cached_schema = self._cached_schemas.get(compatibility_date)
        if memory_cached_schema is not None and not self._is_cached_schema_expired(
            memory_cached_schema, self._ttl
        ):
            return memory_cached_schema
        # If the cached schema is not in memory or has expired, check the database.
        cached_schema = self._load_schema_from_db(compatibility_date)
        if cached_schema is not None and not self._is_cached_schema_expired(
            cached_schema, self._ttl
        ):
            self._cached_schemas[compatibility_date] = cached_schema
            return cached_schema
        # If the cached schema is not in the database or has expired, fetch a new one
        # and save it to the database.
        cached_schema = self._fetch_schema_for_date(compatibility_date)
        self._save_schema_to_db(cached_schema)
        self._cached_schemas[compatibility_date] = cached_schema
        return cached_schema

    def get_latest_cached_schema(self) -> CachedSchema:
        """Get the latest cached schema based on the latest compatibility date.

        Either from the database or freshly fetched if it is not in the database or has expired.

        Returns:
            A CachedSchema object containing the cached schema and the timestamp of when
                it was fetched.

        Raises:
            ValueError: If there are no available compatibility dates.
        """
        versions = self.schema_versions()
        if not versions:
            raise ValueError("No available compatibility dates to fetch schema for.")
        latest_compatibility_date = max(versions)
        return self.get_cached_schema(latest_compatibility_date)
