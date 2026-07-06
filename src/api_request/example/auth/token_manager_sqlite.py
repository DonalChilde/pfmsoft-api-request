import asyncio
import sqlite3
from typing import Annotated

from annotated_types import Ge, Le
from pydantic_core import from_json, to_json
from whenever import Instant

from esi_link.app_data.helpers import transaction
from esi_link.auth.models import CharacterToken
from esi_link.auth.token_tool import TokenTool

# TODO refactor token manager database table to include client_id.
# This would be one way to handle changing the app credentials, and avoiding trying to
# use old tokens with new credentials. It could also support multiple sets of
# credentials in the same database, if needed in the future.
# NOTE: another way to handle changing credentials would be to just delete all existing
# tokens when the client_id changes, since they would all be invalid anyway. This might
# be simpler than trying to manage multiple sets of credentials and tokens in the same database.


class CharacterTokenManagerSqlite:
    def __init__(
        self, connection: sqlite3.Connection, client_id: str, token_tool: TokenTool
    ):
        """A simple token manager that stores ESI character tokens in a SQLite database."""
        self._connection = connection
        self._client_id = client_id
        self._token_tool = token_tool

    # TODO make db load/save/get all private methods.

    def save_character(self, character_token: CharacterToken) -> None:
        """Save a character token to the database."""
        oauth_token_json = to_json(character_token.oauth_token)
        sql = """
        REPLACE INTO CharacterTokens (character_id, character_name, expires_at, oauth_token_json, timestamped)
        VALUES (?, ?, ?, ?, ?)
        """
        with transaction(self._connection) as conn:
            conn.execute(
                sql,
                (
                    character_token.character_id,
                    character_token.character_name,
                    character_token.expires_at,
                    oauth_token_json,
                    Instant.now().timestamp_nanos(),
                ),
            )

    def get_character(self, character_id: int) -> CharacterToken:
        """Fetch the token for a specific character ID from the database."""
        sql = "SELECT * FROM CharacterTokens WHERE character_id = ?"
        with transaction(self._connection) as conn:
            cursor = conn.execute(sql, (character_id,))
            row = cursor.fetchone()
        if row is None:
            raise ValueError(f"No token found for character ID {character_id}.")
        return CharacterToken(
            character_id=row["character_id"],
            character_name=row["character_name"],
            expires_at=row["expires_at"],
            oauth_token=from_json(row["oauth_token_json"]),
        )

    def get_all_characters(self) -> list[CharacterToken]:
        """Fetch tokens for all characters stored in the database."""
        sql = "SELECT * FROM CharacterTokens"
        with transaction(self._connection) as conn:
            rows = conn.execute(sql).fetchall()
        character_tokens = [
            CharacterToken(
                character_id=row["character_id"],
                character_name=row["character_name"],
                expires_at=row["expires_at"],
                oauth_token=from_json(row["oauth_token_json"]),
            )
            for row in rows
        ]
        return character_tokens

    def _refresh_character_token(self, character_id: int) -> CharacterToken:
        """Refresh the token for a specific character ID and update it in the database."""
        existing_token = self.get_character(character_id)
        oauth_token = self._token_tool.refresh_existing_token(
            client_id=self._client_id,
            refresh_token=existing_token.oauth_token.refresh_token,
        )
        validated_token = self._token_tool.validate_token(oauth_token.access_token)
        updated_character_token = CharacterToken(
            character_id=validated_token.character_id,
            character_name=validated_token.character_name,
            expires_at=validated_token.expires_at,
            oauth_token=oauth_token,
        )
        self.save_character(updated_character_token)
        return updated_character_token

    async def _async_refresh_character_token(self, character_id: int) -> CharacterToken:
        """Asynchronously refresh the token for a specific character ID and update it in the database."""
        existing_token = self.get_character(character_id)
        oauth_token = await self._token_tool.async_refresh_existing_token(
            client_id=self._client_id,
            refresh_token=existing_token.oauth_token.refresh_token,
        )
        validated_token = self._token_tool.validate_token(oauth_token.access_token)
        updated_character_token = CharacterToken(
            character_id=validated_token.character_id,
            character_name=validated_token.character_name,
            expires_at=validated_token.expires_at,
            oauth_token=oauth_token,
        )
        self.save_character(updated_character_token)
        return updated_character_token

    def refresh_character_token(
        self,
        character_id: int,
        min_seconds: Annotated[int, Ge(0), Le(1200)] = 300,
    ) -> CharacterToken:
        """Get the token for a character, refreshing it if it's close to expiring."""
        character_token = self.get_character(character_id)
        if character_token.expires_in < min_seconds:
            return self._refresh_character_token(character_id)
        return character_token

    async def refresh_all_character_tokens(
        self,
        *,
        min_seconds: Annotated[int, Ge(0), Le(1200)] = 300,
    ) -> list[CharacterToken]:
        """Refresh tokens for all characters that are close to expiring."""
        character_tokens = self.get_all_characters()
        tasks = [
            self._async_refresh_character_token(character_id=token.character_id)
            for token in character_tokens
            if token.expires_in < min_seconds
        ]
        _ = await asyncio.gather(*tasks)
        # After refreshing, fetch all character tokens again to get the updated values
        character_tokens = self.get_all_characters()
        return character_tokens

    def revoke_character_token(self, character_id: int) -> None:
        """Revoke the token for a specific character ID and remove it from the database."""
        # FIXME implement token revocation using the ESI revoke endpoint, and then delete
        # the token from the database if revocation is successful.
        sql = "DELETE FROM CharacterTokens WHERE character_id = ?"
        with transaction(self._connection) as conn:
            conn.execute(sql, (character_id,))

    def revoke_all_character_tokens(self) -> None:
        """Revoke all tokens and remove them from the database."""
        # FIXME implement token revocation using the ESI revoke endpoint, and then delete
        # all tokens from the database if revocation is successful.
        sql = "DELETE FROM CharacterTokens"
        with transaction(self._connection) as conn:
            conn.execute(sql)

    @property
    def available_characters(self) -> list[int]:
        """Get a list of character IDs for which tokens are stored in the database."""
        sql = "SELECT character_id FROM CharacterTokens"
        with transaction(self._connection) as conn:
            cursor = conn.execute(sql)
            rows = cursor.fetchall()
        character_ids = [row["character_id"] for row in rows]
        return character_ids
