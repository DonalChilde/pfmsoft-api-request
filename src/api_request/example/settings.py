"""Settings for the Esi Link application.

The cache configuration shows an example of poissible future expansion
to support other schema store and metadata cache types. For now, the simple disk based
versions are fine.
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from esi_link import DEFAULT_APP_DIR

_app_env_prefix = "PFMSOFT_ESI_LINK_"

COMPATIBILITY_DATES_URL = "https://esi.evetech.net/meta/compatibility-dates"
"""URL to fetch the list of compatibility dates from the ESI API."""
OAUTH_METADATA_URL = (
    "https://login.eveonline.com/.well-known/oauth-authorization-server"
)
"""URL to fetch OAuth metadata from the ESI auth server."""
ESI_SCHEMA_URL = "https://esi.evetech.net/meta/openapi.json"
"""URL to fetch ESI OpenAPI schema.

Example: 
    https://esi.evetech.net/meta/openapi.json?compatibility_date=2026-05-19

The schemas are versioned by compatibility date. If no compatibility date is provided, the 
schema downloaded will be the OLDEST schema available, which is not likely what is desired.

Provide a date in the past to get the latest schema. future dates are not allowed.

The API changes at 11:00 UTC, so use `now() minus 11 hours` as an iso date to get the latest schema.
"""


# @dataclass(slots=True, frozen=True)
# class CacheConfiguration:
#     """Configuration for the cache used by ESI Link."""

#     cache_type: Literal["memory", "diskcache", "jsonstore"]
#     configuration: dict[str, str] = Field(
#         default_factory=dict[str, str],
#         description="Additional configuration options for the cache. The specific options depend on the cache type.",
#     )


# @dataclass(slots=True, frozen=True, kw_only=True)
# class MemoryCacheConfiguration(CacheConfiguration):
#     """Configuration for an in-memory cache used by ESI Link."""

#     cache_type: Literal["memory"] = "memory"
#     configuration: dict[str, str] = field(default_factory=dict[str, str])


# @dataclass(slots=True, frozen=True, kw_only=True)
# class JsonStoreCacheConfiguration(CacheConfiguration):
#     """Configuration for a JSON file-based cache used by ESI Link."""

#     cache_type: Literal["jsonstore"] = "jsonstore"
#     configuration: dict[str, str] = field(default_factory=dict[str, str])


# @dataclass(slots=True, frozen=True, kw_only=True)
# class DiskCacheConfiguration(CacheConfiguration):
#     """Configuration for a disk-based cache using the diskcache library."""

#     cache_type: Literal["diskcache"] = "diskcache"
#     configuration: dict[str, str] = field(default_factory=dict[str, str])


# JsonStoreCacheConfigurationRoot = RootModel[JsonStoreCacheConfiguration]
# DiskCacheConfigurationRoot = RootModel[DiskCacheConfiguration]


@dataclass(slots=True, kw_only=True, frozen=True)
class EsiLinkSettings:
    """Settings for the ESI Link application."""

    application_directory: Path
    """The directory where the ESI Link application stores its data, logs, and cache."""
    log_directory: Path
    """The directory where the ESI Link application stores its log files."""
    app_data_db_path: Path
    """The file path for the app-data SQLite database."""
    # cache_directory: Path
    # """The directory where the ESI Link application stores its cache files."""
    esi_schema_url: str
    """The URL to fetch the ESI OpenAPI schema from."""
    oauth_metadata_url: str
    """The URL to fetch OAuth metadata from the ESI auth server."""
    schema_cache_directory: Path
    """The directory where the ESI Link application stores its cached ESI OpenAPI schemas."""
    token_store_path: Path
    """The file path for the token store JSON file."""
    auth_metadata_cache_path: Path
    """The file path for the OAuth metadata cache."""
    # auth_metadata_cache_ttl: int
    # """The time-to-live (TTL) for cached OAuth metadata, in seconds. After this time, the
    #     cached metadata will be considered stale and will be refreshed."""
    rate_limit_connection_period: int
    """The period over which to calculate the rate limit for connections to the ESI API, 
        in seconds. This is used to determine how many requests can be made within this 
        period without exceeding the rate limit."""
    rate_limit_connection_max_rate: int
    """The maximum number of requests allowed within the rate limit period."""
    # cache_configuration: CacheConfiguration
    # """Configuration for the cache used by ESI Link."""


class EsiLinkSettingsPydantic(BaseSettings):
    """Settings for the ESI Link application.

    This settings class uses Pydantic for validation and loading from environment variables.
    It includes properties for various directories and configuration options used by ESI Link,
    such as schema URLs, cache settings, rate limiting settings, and ESI Auth settings.
    The settings can be overridden by environment variables with the prefix "PFMSOFT_ESI_LINK_"
    or by .esi-link.env files in the application directory or current working directory.

    This is NOT the class used to configure the app, Its responsibility is loading settings
    from environment variables and providing defaults. The EsiLinkSettings dataclass is
    the main settings class used for the app, and it can be constructed from this Pydantic
    settings class. This separation allows us to use Pydantic's powerful settings management
    features while keeping the main settings class simple and focused on the application's
    needs.

    Example env file (.esi-link.env):
    ```
    # Load settings from environment variables or .esi-link.env file
    PFMSOFT_ESI_LINK_APPLICATION_DIRECTORY=./dev-data/app-dir
    ```
    """

    model_config = SettingsConfigDict(
        env_prefix=_app_env_prefix,
        env_file=".esi-link-env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    application_directory: Path = Field(
        default=DEFAULT_APP_DIR,
        description="The directory where the ESI Link application stores its data, logs, and cache.",
    )

    esi_schema_url: str = Field(
        default=ESI_SCHEMA_URL,
        description="The URL to fetch the ESI OpenAPI schema from.",
    )
    oauth_metadata_url: str = Field(
        default=OAUTH_METADATA_URL,
        description="The URL to fetch OAuth metadata from the ESI auth server.",
    )

    # auth_metadata_cache_ttl: int = Field(
    #     default=3600,
    #     description=(
    #         "The time-to-live (TTL) for cached OAuth metadata, in seconds. "
    #         "After this time, the cached metadata will be considered stale and will be refreshed."
    #     ),
    # )
    rate_limit_connection_period: int = Field(
        default=60,
        description=(
            "The period over which to calculate the rate limit for connections to the ESI API, in seconds."
            "This is used to determine how many requests can be made within this period without exceeding the rate limit."
        ),
    )
    rate_limit_connection_max_rate: int = Field(
        default=1000,
        description=(
            "The maximum number of requests that can be made to the ESI API within the rate limit connection period."
            "This is used in conjunction with the rate_limit_connection_period setting to enforce rate limits on API requests."
        ),
    )
    # cache_type: Literal["memory", "diskcache", "jsonstore"] = Field(
    #     default="diskcache",
    #     description=(
    #         "The type of cache to use for storing data. Options are 'memory' for an "
    #         "in-memory cache, 'diskcache' for a disk-based cache using the diskcache library, "
    #         "and 'jsonstore' for a simple JSON file-based cache."
    #     ),
    # )

    # cache_configuration: str = Field(
    #     default="{}",
    #     description=(
    #         "Additional configuration options for the cache, provided as a JSON string. "
    #         "The specific options depend on the cache type. For example, for 'diskcache', "
    #         "you might provide options like {'size_limit': 1e9} to set a size limit on the cache."
    #     ),
    # )


def get_settings(
    pydantic_settings: EsiLinkSettingsPydantic | None = None,
) -> EsiLinkSettings:
    """Get the settings for the ESI Link application.

    This function loads settings from environment variables using the EsiLinkSettingsPydantic class,
    and then constructs an EsiLinkSettings dataclass instance from the loaded Pydantic settings.
    This allows us to use Pydantic's powerful settings management features while keeping the main
    settings class simple and focused on the application's needs.

    Args:
        pydantic_settings: An optional instance of EsiLinkSettingsPydantic. If not provided, a new instance will be created by loading from environment variables.

    Returns:
        An instance of EsiLinkSettings with the loaded configuration.
    """
    if pydantic_settings is None:
        pydantic_settings = EsiLinkSettingsPydantic()
    # # Use cache type to select the appropriate cache configuration class and parse the cache configuration JSON string if provided.
    # match pydantic_settings.cache_type:
    #     case "memory":
    #         # No additional configuration needed for memory cache, just use an empty dict.
    #         cache_configuration = MemoryCacheConfiguration(
    #             cache_type="memory", configuration={}
    #         )
    #     case "diskcache":
    #         config_obj = json.loads(pydantic_settings.cache_configuration)
    #         config_obj["cache_type"] = "diskcache"
    #         cache_configuration = DiskCacheConfigurationRoot.model_validate(
    #             config_obj
    #         ).root
    #     case "jsonstore":
    #         config_obj = json.loads(pydantic_settings.cache_configuration)
    #         config_obj["cache_type"] = "jsonstore"
    #         cache_configuration = JsonStoreCacheConfigurationRoot.model_validate(
    #             config_obj
    #         ).root
    #     case _:
    #         raise ValueError(f"Unsupported cache type: {pydantic_settings.cache_type}")

    return EsiLinkSettings(
        application_directory=pydantic_settings.application_directory,
        log_directory=pydantic_settings.application_directory / "logs",
        # cache_directory=pydantic_settings.application_directory / "cache",
        app_data_db_path=pydantic_settings.application_directory / "app_data.db",
        esi_schema_url=pydantic_settings.esi_schema_url,
        oauth_metadata_url=pydantic_settings.oauth_metadata_url,
        schema_cache_directory=pydantic_settings.application_directory / "schema_cache",
        auth_metadata_cache_path=pydantic_settings.application_directory
        / "auth_metadata_cache.json",
        # auth_metadata_cache_ttl=pydantic_settings.auth_metadata_cache_ttl,
        rate_limit_connection_period=pydantic_settings.rate_limit_connection_period,
        rate_limit_connection_max_rate=pydantic_settings.rate_limit_connection_max_rate,
        token_store_path=pydantic_settings.application_directory / "token_store.json",
        # cache_configuration=cache_configuration,
    )
