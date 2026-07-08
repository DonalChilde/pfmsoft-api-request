"""Tests for application settings helpers."""

from __future__ import annotations

from pathlib import Path

from api_request.settings import ApiRequestSettings, get_settings


def test_api_request_settings_path_properties() -> None:
    """Derived cache and logging paths should be rooted at application_directory."""
    settings = ApiRequestSettings(application_directory=Path("/tmp/api-request"))

    assert settings.cache_directory == Path("/tmp/api-request/cache")
    assert settings.cache_file == Path("/tmp/api-request/cache/web-cache.sqlite3")
    assert settings.logging_directory == Path("/tmp/api-request/logs")


def test_get_settings_honors_environment_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Pydantic settings should map API_REQUEST_APPLICATION_DIRECTORY from env."""
    monkeypatch.setenv("API_REQUEST_APPLICATION_DIRECTORY", str(tmp_path))

    settings = get_settings()

    assert settings.application_directory == tmp_path
