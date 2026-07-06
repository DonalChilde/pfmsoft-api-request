"""A simple json disk store for ESI authentication tokens."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from types import CoroutineType, TracebackType
from typing import Annotated, Any, Self

from annotated_types import Ge, Le
from httpx2 import AsyncClient, Client
from pydantic import RootModel

from esi_link.auth.models import CharacterToken, EsiAppCredentials
from esi_link.auth.token_tool import TokenTool


@dataclass(slots=True)
class TokenStoreData:
    credentials: EsiAppCredentials
    character_tokens: dict[int, CharacterToken] = field(
        default_factory=dict[int, CharacterToken]
    )

    def to_string(self, indent: int) -> str:
        """Return a string representation of the token store data with the specified indentation."""
        root_model = TokenStoreDataRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> TokenStoreData:
        """Parse the token store data from a JSON string."""
        value = TokenStoreDataRoot.model_validate_json(json_str).root
        return value


TokenStoreDataRoot = RootModel[TokenStoreData]


class TokenStoreError(Exception):
    """Base exception for TokenStore errors."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Custom exception for errors related to the TokenStore."""
        super().__init__(*args, **kwargs)


class TokenStore:
    def __init__(self, store_path: Path, token_tool: TokenTool) -> None:
        """A simple json disk store for ESI authentication tokens."""
        self._token_tool = token_tool
        self._store_path = store_path
        self._store_data: TokenStoreData | None = None
        self._dirty: bool = False

    @classmethod
    def from_credentials(
        cls,
        *,
        store_path: Path,
        token_tool: TokenTool,
        credentials: EsiAppCredentials,
    ) -> Self:
        """Create a new TokenStore from ESI app credentials."""
        data = TokenStoreData(credentials=credentials)
        store = cls(store_path=store_path, token_tool=token_tool)
        store._store_data = data
        store._dirty = True
        store._save_to_disk()
        store._store_data = None
        return store

    def __enter__(self) -> Self:
        """Load the store data from disk."""
        if self._store_data is not None:
            raise TokenStoreError("TokenStore context manager already entered.")
        self._load_from_disk()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Save the store data to disk if it is dirty."""
        self._save_to_disk()

    def _save_to_disk(self) -> None:
        """Save the store data to disk if it is dirty."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        if not self._dirty:
            return
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(self._store_data.to_string(indent=2))
        self._dirty = False

    def _load_from_disk(self) -> None:
        """Load the store data from disk."""
        if not self._store_path.exists():
            raise TokenStoreError(
                f"Token store file {self._store_path} does not exist."
            )
        if not self._store_path.is_file():
            raise TokenStoreError(f"Token store path {self._store_path} is not a file.")
        self._store_data = TokenStoreData.from_string(self._store_path.read_text())
        self._dirty = False

    def _refresh_character(
        self,
        character_id: int,
        *,
        session: Client,
    ) -> CharacterToken:
        """Refresh the token for a character and update the store."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        character_token = self._store_data.character_tokens[character_id]
        new_oauth_token = self._token_tool.refresh_existing_token(
            client_id=self._store_data.credentials.clientId,
            refresh_token=character_token.oauth_token.refresh_token,
            session=session,
        )
        new_character_token = self._token_tool.create_character_token(
            oauth_token=new_oauth_token,
        )
        if new_character_token.character_id != character_id:
            raise TokenStoreError(
                f"Refreshed token character ID {new_character_token.character_id} does not match expected character ID {character_id}."
            )
        self._store_data.character_tokens[character_id] = new_character_token
        return new_character_token

    async def _async_refresh_character(
        self,
        character_id: int,
        *,
        client_session: AsyncClient,
    ) -> CharacterToken:
        """Asynchronously refresh the token for a character and update the store."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        character_token = self._store_data.character_tokens[character_id]
        new_oauth_token = await self._token_tool.async_refresh_existing_token(
            client_id=self._store_data.credentials.clientId,
            refresh_token=character_token.oauth_token.refresh_token,
            session=client_session,
        )
        new_character_token = self._token_tool.create_character_token(
            oauth_token=new_oauth_token,
        )
        if new_character_token.character_id != character_id:
            raise TokenStoreError(
                f"Refreshed token character ID {new_character_token.character_id} does not match expected character ID {character_id}."
            )
        self._store_data.character_tokens[character_id] = new_character_token
        return new_character_token

    def refresh_character_token(
        self,
        character_id: int,
        *,
        min_seconds: Annotated[int, Ge(0), Le(1200)] = 300,
        session: Client | None = None,
    ) -> CharacterToken:
        """Get the token for a character."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        if character_id not in self._store_data.character_tokens:
            raise KeyError(f"No token found for character ID {character_id}.")
        character_token = self._store_data.character_tokens[character_id]
        if session is None:
            return character_token
        if character_token.expires_in >= min_seconds:
            return character_token
        new_character_token = self._refresh_character(character_id, session=session)
        return new_character_token

    async def async_refresh_character_tokens(
        self,
        *,
        session: AsyncClient,
        min_seconds: Annotated[int, Ge(0), Le(1200)] = 300,
    ) -> dict[int, CharacterToken]:
        """Asynchronously refresh the tokens for all characters, updating any that are about to expire."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        character_tokens = self._store_data.character_tokens
        tasks: list[CoroutineType[Any, Any, CharacterToken]] = []
        for character_id, character_token in character_tokens.items():
            if character_token.expires_in < min_seconds:
                task = self._async_refresh_character(
                    character_id, client_session=session
                )
                tasks.append(task)
        await asyncio.gather(*tasks)
        return self._store_data.character_tokens

    def add_character_token(self, character_token: CharacterToken) -> None:
        """Add a character token to the store."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        self._store_data.character_tokens[character_token.character_id] = (
            character_token
        )
        self._dirty = True

    def remove_character_token(self, character_id: int) -> None:
        """Remove a character token from the store."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        if character_id not in self._store_data.character_tokens:
            raise TokenStoreError(f"No token found for character ID {character_id}.")
        del self._store_data.character_tokens[character_id]
        self._dirty = True

    @property
    def available_character_ids(self) -> set[int]:
        """Return a set of character IDs for which tokens are available."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        return set(self._store_data.character_tokens.keys())

    @property
    def credentials(self) -> EsiAppCredentials:
        """Return the ESI app credentials associated with this token store."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        return self._store_data.credentials

    @property
    def character_tokens(self) -> dict[int, CharacterToken]:
        """Return the character tokens in the store."""
        if self._store_data is None:
            raise TokenStoreError("TokenStore data is not initialized.")
        return self._store_data.character_tokens
