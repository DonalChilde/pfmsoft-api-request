"""Tests for sqlite connection helper utilities."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pfmsoft.api_request.cache.sqlite_cache.connection_helpers import (
    create_read_only_connection,
    create_read_write_connection,
    db_connection_manager,
    read_only_uri,
    read_write_uri,
)


def test_uri_helpers_encode_sqlite_modes() -> None:
    """URI helper functions should include expected sqlite mode flags."""
    assert read_only_uri("/tmp/cache.sqlite3") == "file:/tmp/cache.sqlite3?mode=ro"
    assert read_write_uri("/tmp/cache.sqlite3") == "file:/tmp/cache.sqlite3?mode=rwc"


def test_create_read_write_and_read_only_connections(tmp_path: Path) -> None:
    """Read-write connection should bootstrap schema and read-only should query it."""
    db_path = tmp_path / "cache.sqlite3"

    rw_connection = create_read_write_connection(db_path)
    assert rw_connection.row_factory is sqlite3.Row
    tables = {
        row[0]
        for row in rw_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "WebCache" in tables
    rw_connection.close()

    ro_connection = create_read_only_connection(db_path)
    assert ro_connection.row_factory is sqlite3.Row
    assert ro_connection.execute("SELECT 1").fetchone()[0] == 1
    ro_connection.close()


def test_create_read_write_connection_accepts_string_path(tmp_path: Path) -> None:
    """String paths should create parent directories before connecting."""
    db_path = tmp_path / "nested" / "cache.sqlite3"

    connection = create_read_write_connection(str(db_path))

    assert db_path.exists()
    connection.close()


def test_db_connection_manager_selects_factories_and_closes(monkeypatch) -> None:
    """Context manager should dispatch by mode and always close the connection."""

    class _FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    ro_connection = _FakeConnection()
    rw_connection = _FakeConnection()

    monkeypatch.setattr(
        "pfmsoft.api_request.cache.sqlite_cache.connection_helpers.create_read_only_connection",
        lambda _db_path: ro_connection,
    )
    monkeypatch.setattr(
        "pfmsoft.api_request.cache.sqlite_cache.connection_helpers.create_read_write_connection",
        lambda _db_path: rw_connection,
    )

    with db_connection_manager("/tmp/cache.sqlite3", read_only=True) as connection:
        assert connection is ro_connection
    assert ro_connection.closed is True

    with db_connection_manager("/tmp/cache.sqlite3", read_only=False) as connection:
        assert connection is rw_connection
    assert rw_connection.closed is True


def test_create_read_only_connection_accepts_string_path(tmp_path: Path) -> None:
    """Read-only helper should also accept a string path input."""
    db_path = tmp_path / "readonly.sqlite3"
    rw_connection = create_read_write_connection(db_path)
    rw_connection.close()

    ro_connection = create_read_only_connection(str(db_path))
    assert ro_connection.execute("SELECT 1").fetchone()[0] == 1
    ro_connection.close()


def test_db_connection_manager_does_not_close_when_open_fails(monkeypatch) -> None:
    """Manager should handle factory failures when connection was never created."""

    def raising_create_read_only_connection(_db_path: str) -> object:
        raise RuntimeError("open failed")

    monkeypatch.setattr(
        "pfmsoft.api_request.cache.sqlite_cache.connection_helpers.create_read_only_connection",
        raising_create_read_only_connection,
    )

    with pytest.raises(RuntimeError, match="open failed"):
        with db_connection_manager("/tmp/cache.sqlite3", read_only=True):
            raise AssertionError("unreachable")


def test_db_connection_manager_handles_none_connection(monkeypatch) -> None:
    """Manager should permit a None connection and skip close in finally."""
    monkeypatch.setattr(
        "pfmsoft.api_request.cache.sqlite_cache.connection_helpers.create_read_only_connection",
        lambda _db_path: None,
    )

    with db_connection_manager("/tmp/cache.sqlite3", read_only=True) as connection:
        assert connection is None
