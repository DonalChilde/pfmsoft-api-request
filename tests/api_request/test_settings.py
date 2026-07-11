"""Tests for application settings helpers."""

from __future__ import annotations

from pathlib import Path

from api_request.settings import ApiRequestSettings, get_settings


def test_api_request_settings_stores_provided_paths() -> None:
    """ApiRequestSettings should store the paths it is given."""
    app_dir = Path("/tmp/api-request")
    log_dir = app_dir / "logs"
    cache_path = app_dir / "api_requests_web_cache.sqlite"

    settings = ApiRequestSettings(
        application_directory=app_dir,
        logging_directory=log_dir,
        web_cache_path=cache_path,
    )

    assert settings.application_directory == app_dir
    assert settings.logging_directory == log_dir
    assert settings.web_cache_path == cache_path


def test_get_settings_honors_environment_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Pydantic settings should map API_REQUEST_APPLICATION_DIRECTORY from env."""
    monkeypatch.setenv("PFMSOFT_API_REQUEST_APPLICATION_DIRECTORY", str(tmp_path))

    settings = get_settings()

    assert settings.application_directory == tmp_path
