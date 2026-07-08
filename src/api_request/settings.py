"""Settings for the api-request module."""

from dataclasses import dataclass
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from typer import get_app_dir

from api_request import __app_name__, __url__, __version__

USER_AGENT = f"{__app_name__} ({__version__}) (+{__url__})"


@dataclass(slots=True, kw_only=True)
class ApiRequestSettings:
    """Settings for the api-request module."""

    application_directory: Path

    @property
    def cache_directory(self) -> Path:
        """Get the cache directory path."""
        return self.application_directory / "cache"

    @property
    def cache_file(self) -> Path:
        """Get the cache file path."""
        return self.cache_directory / "cache.sqlite3"

    @property
    def logging_directory(self) -> Path:
        """Get the logging directory path."""
        return self.application_directory / "logs"


class ApiRequestSettingsPydantic(BaseSettings):
    """Pydantic settings for the api-request module."""

    application_directory: Path = Path(get_app_dir(__app_name__))

    model_config = SettingsConfigDict(
        env_prefix="API_REQUEST_",
        env_file=".env",
        env_file_encoding="utf-8",
    )


def get_settings() -> ApiRequestSettings:
    """Get the settings for the api-request module."""
    pydantic_settings = ApiRequestSettingsPydantic()
    return ApiRequestSettings(
        application_directory=pydantic_settings.application_directory,
    )
