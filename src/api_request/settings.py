"""Settings for the api-request module."""

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from pydantic_settings import BaseSettings, SettingsConfigDict
from typer import get_app_dir

from api_request import __app_name__, __project_namespace__, __url__, __version__

logger = logging.getLogger(__name__)

USER_AGENT = f"{__app_name__} ({__version__}) (+{__url__})"
APP_DOMAIN = f"{__project_namespace__}.{__app_name__}"
APP_NAMESPACE = uuid5(NAMESPACE_DNS, APP_DOMAIN)
ENV_PREFIX = APP_DOMAIN.replace(".", "_").replace("-", "_").upper() + "_"
SETTINGS_KEY = ENV_PREFIX + "SETTINGS"


@dataclass(slots=True, kw_only=True)
class ApiRequestSettings:
    """Settings for the api-request module."""

    application_directory: Path
    logging_directory: Path
    web_cache_path: Path


class ApiRequestSettingsPydantic(BaseSettings):
    """Pydantic settings for the api-request module."""

    application_directory: Path = Path(get_app_dir(__app_name__))

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=(".env", ".env.dev"),
        env_file_encoding="utf-8",
    )


def get_settings() -> ApiRequestSettings:
    """Get the settings for the api-request module."""
    logger.info("Loading settings from environment variables...")
    logger.info(f"Environment variable prefix: {ENV_PREFIX}")
    pydantic_settings = ApiRequestSettingsPydantic()
    logger.info(
        f"Loaded settings from environment variables: {pydantic_settings.model_dump()}"
    )
    application_directory = pydantic_settings.application_directory.resolve()
    if not application_directory.exists():
        application_directory.mkdir(parents=True, exist_ok=True)
    settings = ApiRequestSettings(
        application_directory=application_directory,
        logging_directory=application_directory / "logs",
        web_cache_path=application_directory / "api_requests_web_cache.sqlite",
    )
    logger.info(f"Resolved application settings: {asdict(settings)}")
    return settings
