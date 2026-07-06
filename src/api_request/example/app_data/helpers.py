import logging
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Wrap a block in an explicit transaction.

    Commits on clean exit, rolls back on any exception.

    sqlite3.connect() has autocommit behaviour that changed in 3.12 and was
    further clarified in 3.14 (PEP 249-compliant isolation_level=None gives
    you a pure manual-commit mode). Using an explicit context manager here
    keeps intent clear regardless of the default.
    """
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception as e:
        logger.error("Transaction failed. %s", e, exc_info=e)
        conn.execute("ROLLBACK")
        raise
