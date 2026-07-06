"""SQLite auth manager implementation stubs."""

from pathlib import Path
from types import TracebackType
from typing import Annotated
from uuid import UUID

from annotated_types import Ge, Le
from httpx2 import AsyncClient, Client

from ..models import (
    AuthCredentials,
    AuthorizedCharacter,
    EsiAppCredentials,
    OAuthMetadataTimestamped,
)
from ..protocols import AuthManagerProtocol


class SqliteAuthManager(AuthManagerProtocol):
    """SQLite-backed auth manager stub implementation."""

    def __init__(self, db_path: str | Path):
        """Initialize the auth manager with the SQLite database path."""
        self.db_path: Path = Path(db_path)

    def __enter__(self) -> "SqliteAuthManager":
        """Enter the context manager."""
        raise NotImplementedError("SqliteAuthManager.__enter__ is not implemented")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the context manager."""
        raise NotImplementedError("SqliteAuthManager.__exit__ is not implemented")

    def get_credentials(self, cred_id: UUID) -> AuthCredentials:
        """Get credentials by credentials ID."""
        raise NotImplementedError(
            "SqliteAuthManager.get_credentials is not implemented"
        )

    def add_credentials(self, credentials: EsiAppCredentials) -> UUID:
        """Add credentials and return the new credentials ID."""
        raise NotImplementedError(
            "SqliteAuthManager.add_credentials is not implemented"
        )

    async def remove_credentials(self, cred_id: UUID, *, session: AsyncClient) -> None:
        """Remove credentials and revoke associated character tokens."""
        raise NotImplementedError(
            "SqliteAuthManager.remove_credentials is not implemented"
        )

    def get_character(self, cred_id: UUID, character_id: int) -> AuthorizedCharacter:
        """Get an authorized character by credentials and character IDs."""
        raise NotImplementedError("SqliteAuthManager.get_character is not implemented")

    def add_character(self, character: AuthorizedCharacter) -> None:
        """Add an authorized character."""
        raise NotImplementedError("SqliteAuthManager.add_character is not implemented")

    def revoke_character(
        self, cred_id: UUID, character_id: int, *, session: Client
    ) -> None:
        """Revoke a character and remove it from storage."""
        raise NotImplementedError(
            "SqliteAuthManager.revoke_character is not implemented"
        )

    def get_all_characters(self, cred_id: UUID) -> list[AuthorizedCharacter]:
        """Get all authorized characters for the credentials ID."""
        raise NotImplementedError(
            "SqliteAuthManager.get_all_characters is not implemented"
        )

    def get_all_character_ids(self, cred_id: UUID) -> set[int]:
        """Get all authorized character IDs for the credentials ID."""
        raise NotImplementedError(
            "SqliteAuthManager.get_all_character_ids is not implemented"
        )

    def refresh_character(
        self,
        cred_id: UUID,
        character_id: int,
        *,
        session: Client,
        min_seconds: Annotated[int, Ge(0), Le(1200)] = 300,
    ) -> AuthorizedCharacter:
        """Refresh an authorized character if token age threshold is met."""
        raise NotImplementedError(
            "SqliteAuthManager.refresh_character is not implemented"
        )

    async def refresh_characters(
        self,
        cred_id: UUID,
        character_ids: set[int] | None = None,
        *,
        session: AsyncClient,
        min_seconds: Annotated[int, Ge(0), Le(1200)] = 300,
    ) -> list[AuthorizedCharacter]:
        """Refresh one or more authorized characters."""
        raise NotImplementedError(
            "SqliteAuthManager.refresh_characters is not implemented"
        )

    def get_oauth_metadata(self) -> OAuthMetadataTimestamped:
        """Get the OAuth metadata."""
        raise NotImplementedError(
            "SqliteAuthManager.get_oauth_metadata is not implemented"
        )

    def set_oauth_metadata(self, metadata: OAuthMetadataTimestamped) -> None:
        """Set the OAuth metadata."""
        raise NotImplementedError(
            "SqliteAuthManager.set_oauth_metadata is not implemented"
        )
