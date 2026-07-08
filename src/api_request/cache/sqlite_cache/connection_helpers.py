"""Helpers for building SQLite URIs, opening connections, and bootstrapping schema."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files as resource_files
from pathlib import Path

logger = logging.getLogger(__name__)

_table_def_parent = "api_request.cache.sqlite_cache"
_table_def_sql = "table_definitions.sql"


def read_only_uri(db_path: str) -> str:
    """Build a read-only SQLite URI for use with sqlite3.connect(uri=True).

    Args:
        db_path: Filesystem path to the SQLite database.

    Returns:
        URI string with mode=ro.
    """
    return f"file:{db_path}?mode=ro"


def read_write_uri(db_path: str) -> str:
    """Build a read-write/create SQLite URI for use with sqlite3.connect(uri=True).

    Args:
        db_path: Filesystem path to the SQLite database.

    Returns:
        URI string with mode=rwc.
    """
    return f"file:{db_path}?mode=rwc"


def create_read_only_connection(db_path: str | Path) -> sqlite3.Connection:
    """Create a read-only SQLite connection for an existing database.

    The caller is responsible for closing the connection when done.

    Args:
        db_path: Path to an existing SQLite database file.

    Returns:
        Open SQLite connection configured with sqlite3.Row row factory.

    Notes:
        The target database is expected to already contain the required schema.
        Read-only connections cannot create temporary tables. Query helpers that
        rely on temporary tables for large key filters may fail in this mode.
    """
    if isinstance(db_path, Path):
        db_path = str(db_path.resolve())
    uri = read_only_uri(db_path)
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def create_read_write_connection(db_path: str | Path) -> sqlite3.Connection:
    """Create a read-write SQLite connection and ensure the packaged schema exists.

    The caller is responsible for closing the connection when done.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Open SQLite connection configured with sqlite3.Row row factory.

    Notes:
        Missing tables and other schema objects defined in the packaged SQL
        script are created before the connection is returned.
    """
    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path = str(db_path.resolve())
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db_path = str(Path(db_path).resolve())
    uri = read_write_uri(db_path)
    connection = sqlite3.connect(uri, uri=True)
    logger.info(f"Created read-write connection to database at {db_path}")
    connection.row_factory = sqlite3.Row
    table_defs = resource_files(_table_def_parent).joinpath(_table_def_sql).read_text()
    with connection:
        connection.executescript(table_defs)
        logger.info("Ensured database schema is created.")
    return connection


@contextmanager
def db_connection_manager(
    db_path: str | Path, read_only: bool = True
) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection and close it automatically on exit.

    Delegates to the read-only or read-write connection factory based on the
    read_only flag.

    Args:
        db_path: Path to the SQLite database file.
        read_only: Whether to open the connection in read-only mode.

    Yields:
        Open SQLite connection configured with sqlite3.Row row factory.
    """
    connection: sqlite3.Connection | None = None
    try:
        if read_only:
            logger.info(f"Opening read-only connection to database at {db_path}")
            connection = create_read_only_connection(db_path)
        else:
            logger.info(f"Opening read-write connection to database at {db_path}")
            connection = create_read_write_connection(db_path)
        yield connection
    finally:
        if connection is not None:
            connection.close()
