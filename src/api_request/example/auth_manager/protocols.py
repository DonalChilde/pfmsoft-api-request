"""Protocol for the AuthManager class."""

from typing import Annotated, Protocol
from uuid import UUID

from annotated_types import Ge, Le
from httpx2 import AsyncClient, Client

from .models import (
    AuthCredentials,
    AuthorizedCharacter,
    EsiAppCredentials,
    OAuthMetadataTimestamped,
)


class AuthManagerProtocol(Protocol):
    """Protocol for the AuthManager class."""

    def get_credentials(self, cred_id: UUID) -> AuthCredentials:
        """Get the credentials for the given ID."""
        ...

    def add_credentials(self, credentials: EsiAppCredentials) -> UUID:
        """Save the given credentials and return their ID."""
        ...

    async def remove_credentials(self, cred_id: UUID, *, session: AsyncClient) -> None:
        """Remove the credentials for the given ID.

        Also revokes all associated character tokens.
        """
        ...

    def get_character(self, cred_id: UUID, character_id: int) -> AuthorizedCharacter:
        """Get the authenticated character for the given character ID."""
        ...

    def add_character(self, character: AuthorizedCharacter) -> None:
        """Add an authenticated character."""
        ...

    def revoke_character(
        self, cred_id: UUID, character_id: int, *, session: Client
    ) -> None:
        """Revoke the authenticated character for the given character ID.

        Also removes the character from the database.
        """
        ...

    def get_all_characters(self, cred_id: UUID) -> list[AuthorizedCharacter]:
        """Get all authenticated characters for the given credentials ID."""
        ...

    def get_all_character_ids(self, cred_id: UUID) -> set[int]:
        """Get all authenticated character IDs for the given credentials ID."""
        ...

    def refresh_character(
        self,
        cred_id: UUID,
        character_id: int,
        *,
        session: Client,
        min_seconds: Annotated[int, Ge(0), Le(1200)] = 300,
    ) -> AuthorizedCharacter:
        """Refresh the authenticated character for the given character ID."""
        ...

    async def refresh_characters(
        self,
        cred_id: UUID,
        character_ids: set[int] | None = None,
        *,
        session: AsyncClient,
        min_seconds: Annotated[int, Ge(0), Le(1200)] = 300,
    ) -> list[AuthorizedCharacter]:
        """Refresh all authenticated characters for the given credentials ID."""
        ...

    def get_oauth_metadata(self) -> OAuthMetadataTimestamped:
        """Get the OAuth metadata."""
        ...

    def set_oauth_metadata(self, metadata: OAuthMetadataTimestamped) -> None:
        """Set the OAuth metadata."""
        ...
