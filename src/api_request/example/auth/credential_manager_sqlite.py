"""A credential manager that stores ESI app credentials in a SQLite database."""

import sqlite3

from pydantic_core import from_json, to_json
from whenever import Instant

from esi_link.app_data.helpers import transaction
from esi_link.auth.models import EsiAppCredentials


class CredentialManagerSqlite:
    def __init__(self, connection: sqlite3.Connection):
        """A simple credential manager that stores ESI app credentials in a SQLite database."""
        self._connection = connection

    def _load_credentials_from_db(self) -> EsiAppCredentials | None:
        """Load the ESI app credentials from the database."""
        sql = "SELECT * FROM Credentials WHERE ID = 0"
        with transaction(self._connection) as conn:
            cursor = conn.execute(sql)
            row = cursor.fetchone()
        if row is None:
            return None
        return EsiAppCredentials(
            name=row["app_name"],
            description=row["app_description"],
            clientId=row["client_id"],
            clientSecret=row["client_secret"],
            callbackUrl=row["callback_url"],
            scopes=from_json(row["scopes_json"]),
        )

    def get(self) -> EsiAppCredentials | None:
        """Fetch the ESI app credentials from the database."""
        credentials = self._load_credentials_from_db()
        return credentials

    def save(self, credentials: EsiAppCredentials, overwrite: bool = False) -> None:
        """Save the ESI app credentials to the database."""
        existing_credentials = self._load_credentials_from_db()
        if existing_credentials is not None and not overwrite:
            raise ValueError(
                "Credentials already exist in the database. Use overwrite=True to replace them."
            )
        scopes_json = to_json(credentials.scopes)
        sql = """
        REPLACE INTO Credentials (ID, app_name, app_description, client_id, client_secret, callback_url, scopes_json,timestamped)
        VALUES (0, ?, ?, ?, ?, ?, ?,?)
        """
        with transaction(self._connection) as conn:
            conn.execute(
                sql,
                (
                    credentials.name,
                    credentials.description,
                    credentials.clientId,
                    credentials.clientSecret,
                    credentials.callbackUrl,
                    scopes_json,
                    Instant.now().timestamp_nanos(),
                ),
            )
