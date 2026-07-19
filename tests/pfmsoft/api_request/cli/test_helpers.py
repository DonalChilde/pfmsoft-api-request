"""Tests for CLI helper utilities."""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from pfmsoft.api_request.cli.helpers import (
    get_api_request_settings_from_context,
    get_stdin,
)
from pfmsoft.api_request.settings import SETTINGS_KEY, ApiRequestSettings


class _FakeStdin:
    def __init__(self, *, is_tty: bool, data: str = "") -> None:
        self._is_tty = is_tty
        self._stream = io.StringIO(data)

    def isatty(self) -> bool:
        return self._is_tty

    def read(self) -> str:
        return self._stream.read()


def test_get_auth_manager_settings_from_context_returns_settings() -> None:
    """Context helper should return settings when the key exists."""
    expected = ApiRequestSettings(
        application_directory=Path("/tmp/api-request"),
        logging_directory=Path("/tmp/api-request/logs"),
        web_cache_path=Path("/tmp/api-request/api_requests_web_cache.sqlite"),
    )
    ctx = SimpleNamespace(obj={SETTINGS_KEY: expected})

    assert get_api_request_settings_from_context(ctx) is expected


@pytest.mark.parametrize(
    ("ctx_obj",),
    [
        (None,),
        ({},),
    ],
)
def test_get_auth_manager_settings_from_context_raises_for_missing_settings(
    ctx_obj: object,
) -> None:
    """Context helper should fail fast when settings were not initialized."""
    ctx = SimpleNamespace(obj=ctx_obj)

    with pytest.raises(ValueError, match="ApiRequestSettings not found"):
        get_api_request_settings_from_context(ctx)


def test_get_stdin_reads_from_non_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Piped stdin content should be returned as-is."""
    monkeypatch.setattr("sys.stdin", _FakeStdin(is_tty=False, data="hello\nworld"))

    assert get_stdin() == "hello\nworld"


def test_get_stdin_raises_on_interactive_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive tty stdin should raise with a usage-focused message."""
    monkeypatch.setattr("sys.stdin", _FakeStdin(is_tty=True))

    with pytest.raises(ValueError, match="provide a file path or pipe data"):
        get_stdin()
