"""Tools for fetching and processing ESI OpenAPI schemas and compatibility dates."""

import logging
from dataclasses import dataclass
from typing import Any, TypedDict

from httpx2 import Client
from pydantic import RootModel
from whenever import Instant

from esi_link.helpers.eve_dates import latest_schema_date
from esi_link.helpers.resolve_json_ref import resolve_internal_refs
from esi_link.settings import COMPATIBILITY_DATES_URL, ESI_SCHEMA_URL

logger = logging.getLogger(__name__)


class CompatibilityDates(TypedDict):
    """Represents the structure of the compatibility dates response from the ESI endpoint."""

    compatibility_dates: list[str]


CompatibilityDatesRoot = RootModel[CompatibilityDates]


@dataclass(slots=True, kw_only=True, frozen=True)
class TimestampedCompatibilityDates:
    """Represents the compatibility dates along with the timestamp of when they were fetched."""

    compatibility_dates: list[str]
    timestamp: int
    """Nanoseconds since the Unix epoch when the compatibility dates were fetched."""

    @property
    def timestamp_instant(self) -> Instant:
        """Convert the fetch timestamp to an Instant."""
        return Instant.from_timestamp_nanos(self.timestamp)


@dataclass(slots=True, kw_only=True, frozen=True)
class TimestampedSchema:
    """The ESI schema along with the timestamp of when it was fetched."""

    schema: dict[str, Any]
    timestamp: int
    """Nanoseconds since the Unix epoch when the schema was fetched."""

    @property
    def timestamp_instant(self) -> Instant:
        """Convert the fetch timestamp to an Instant."""
        return Instant.from_timestamp_nanos(self.timestamp)


@dataclass(slots=True, kw_only=True, frozen=True)
class ResolvedTimestampedSchema:
    """The ESI schema along with the timestamp of when it was fetched."""

    schema: dict[str, Any]
    timestamp: int
    """Nanoseconds since the Unix epoch when the schema was fetched."""

    @property
    def timestamp_instant(self) -> Instant:
        """Convert the fetch timestamp to an Instant."""
        return Instant.from_timestamp_nanos(self.timestamp)


def _fetch_schema_for_date(
    session: Client,
    *,
    compatibility_date: str,
    url: str = ESI_SCHEMA_URL,
) -> TimestampedSchema:
    """Fetch the ESI OpenAPI schema for a specific compatibility date. This is a helper method for fetch_latest_schema."""
    url = f"{url}?compatibility_date={compatibility_date}"
    try:
        response = session.get(url)
        response.raise_for_status()
        logger.info(
            f"Fetched schema for compatibility date {compatibility_date} from {url}"
        )
    except Exception as e:
        logger.error(
            f"Failed to fetch schema for compatibility date {compatibility_date} from {url}: {e}"
        )
        raise
    return TimestampedSchema(
        schema=response.json(),
        timestamp=Instant.now().timestamp_nanos(),
    )


def fetch_versioned_schema(
    session: Client,
    *,
    compatibility_date: str,
    url: str = ESI_SCHEMA_URL,
) -> TimestampedSchema:
    """Fetch the ESI OpenAPI schema for a specific compatibility date."""
    try:
        timestamped_schema = _fetch_schema_for_date(
            compatibility_date=compatibility_date, session=session, url=url
        )
        return timestamped_schema
    except Exception as e:
        raise ValueError(
            f"Failed to fetch schema for compatibility date {compatibility_date}: {e}"
        ) from e


def fetch_latest_schema(
    session: Client, *, url: str = ESI_SCHEMA_URL
) -> TimestampedSchema:
    """Fetch the ESI OpenAPI schema for the latest compatibility date."""
    latest_date = latest_schema_date()
    timestamped_schema = _fetch_schema_for_date(
        compatibility_date=latest_date, session=session, url=url
    )
    return timestamped_schema


def resolve_schema(schema: TimestampedSchema) -> ResolvedTimestampedSchema:
    """Resolve internal references in the ESI OpenAPI schema."""
    resolved_schema = resolve_internal_refs(schema.schema, schema.schema)
    return ResolvedTimestampedSchema(
        schema=resolved_schema,
        timestamp=schema.timestamp,
    )


def fetch_compatibility_dates(
    session: Client, *, url: str = COMPATIBILITY_DATES_URL
) -> TimestampedCompatibilityDates:
    """Fetch the compatibility dates from the URL."""
    try:
        response = session.get(url)
        response.raise_for_status()
        dates = response.json()
        logger.info(f"Fetched compatibility dates from {url}")
    except Exception as e:
        logger.error(f"Failed to fetch compatibility dates from {url}: {e}")
        raise
    # Sort the dates in ascending order, so order is guaranteed.
    dates["compatibility_dates"].sort()
    timestamp = Instant.now().timestamp_nanos()
    compatibility_dates = CompatibilityDatesRoot.model_validate(dates).root
    return TimestampedCompatibilityDates(
        compatibility_dates=compatibility_dates["compatibility_dates"],
        timestamp=timestamp,
    )
