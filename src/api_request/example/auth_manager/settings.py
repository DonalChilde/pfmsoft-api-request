"""Settings and constants for the auth_manager package."""

from dataclasses import dataclass
from pathlib import Path

from httpx2 import AsyncClient, Client
from pydantic_settings import BaseSettings, SettingsConfigDict
from typer import get_app_dir

from . import __app_name__, __url__, __version__

AUDIENCE = "EVE Online"
USER_AGENT = f"{__app_name__} ({__version__}) (+{__url__}) auth_manager stand alone"


@dataclass(slots=True, kw_only=True)
class AuthManagerSettings:
    auth_db_path: Path
    logging_directory: Path
    client_session: Client | None = None
    async_client_session: AsyncClient | None = None


class AuthManagerSettingsPydantic(BaseSettings):
    """Pydantic settings for the auth_manager package."""

    model_config = SettingsConfigDict(env_prefix="ESI_AUTH_MANAGER_")
    auth_db_path: Path = Path(get_app_dir(__app_name__)) / "auth_manager.db"

    @property
    def logging_directory(self) -> Path:
        """Return the logging directory for the auth_manager package."""
        return self.auth_db_path.parent / "logs"


def get_settings(
    pydantic_settings: AuthManagerSettingsPydantic | None = None,
) -> AuthManagerSettings:
    """Get the settings for the auth_manager package.

    Ways of initializing the settings:
    1. If the cli is run directly, The settings will be initiallized in the @app.callback,
    method and stored in the typer context.obj.
    2. If the cli is imported into another cli, that cli will init the AuthManagerSettings
    object either directly, or by working with an AuthManagerSettingsPydantic object,
    and the settings obj will be stored in the typer context.obj.
    3. If this code is imported into another package, that package is responsible for
    creating the AuthManagerSettings object.
    """
    pydantic_settings = pydantic_settings or AuthManagerSettingsPydantic()
    return AuthManagerSettings(
        auth_db_path=pydantic_settings.auth_db_path,
        logging_directory=pydantic_settings.logging_directory,
    )
