"""Settings for the api-request module."""

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from pydantic_settings import BaseSettings, SettingsConfigDict
from typer import get_app_dir

from pfmsoft.api_request import (
    __app_name__,
    __url__,
    __version__,
)

logger = logging.getLogger(__name__)

# Typical application settings
USER_AGENT = f"{__app_name__}/{__version__} ({__url__})"
"""User-Agent header value sent to remote OAuth and ESI services."""
APP_DOMAIN = f"{__app_name__}"
APP_NAMESPACE = uuid5(NAMESPACE_DNS, __app_name__)
ENV_PREFIX = __app_name__.replace(".", "_").replace("-", "_").upper() + "_"
SETTINGS_KEY = ENV_PREFIX + "SETTINGS"


@dataclass(slots=True, kw_only=True)
class ApiRequestSettings:
    """Settings for the api-request module."""

    application_directory: Path
    """Directory where the application stores its data."""
    logging_directory: Path
    """Directory where the application stores its log files."""
    web_cache_path: Path
    """Path to the web cache SQLite database."""


class ApiRequestSettingsPydantic(BaseSettings):
    """Pydantic settings for the api-request module."""

    application_directory: Path = Path(get_app_dir(__app_name__)).resolve()
    """Directory where the application stores its data."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=(".env", ".env.dev"),
        env_file_encoding="utf-8",
    )


def get_settings(
    application_directory: Path | None = None,
) -> ApiRequestSettings:
    """Build runtime settings from a Pydantic settings model or application directory.

    Args:
        application_directory (Path | None): Optional application directory path.
            If not provided, the default application directory is used.

    Returns:
        Runtime settings dataclass used by the application.

    Raises:
        ValueError: If the provided application directory exists but is not a directory.
    """
    if application_directory is None:
        # If the application directory is not provided, use the value from the Pydantic
        # settings model. This allows for environment variable overrides and .env file loading.
        application_directory = ApiRequestSettingsPydantic().application_directory
    application_directory = application_directory.expanduser().resolve()
    if application_directory.exists() and not application_directory.is_dir():
        raise ValueError(
            f"Application directory '{application_directory}' exists but is not a directory."
        )
    settings = _initialize_settings(application_directory)
    return settings


def _initialize_settings(application_directory: Path) -> ApiRequestSettings:
    """Build default runtime settings.

    Also ensures that the application directories exist.
    """
    settings = ApiRequestSettings(
        application_directory=application_directory,
        logging_directory=application_directory / "logs",
        web_cache_path=application_directory / "api_requests_web_cache.sqlite",
    )
    # Ensure that the application directories exist.
    settings.application_directory.mkdir(parents=True, exist_ok=True)
    settings.logging_directory.mkdir(parents=True, exist_ok=True)
    return settings
