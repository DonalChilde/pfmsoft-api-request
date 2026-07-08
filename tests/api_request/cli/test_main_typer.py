"""Tests for CLI bootstrap in main_typer."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from api_request.cli import main_typer
from api_request.settings import ApiRequestSettings


def test_default_options_initializes_settings_and_logging(
    monkeypatch,
) -> None:
    """Bootstrap callback should store settings and configure logging."""
    settings = ApiRequestSettings(application_directory=Path("/tmp/api-request"))
    captured: dict[str, Path] = {}

    def fake_get_settings() -> ApiRequestSettings:
        return settings

    def fake_setup_logging(*, log_dir: Path) -> None:
        captured["log_dir"] = log_dir

    monkeypatch.setattr(main_typer, "get_settings", fake_get_settings)
    monkeypatch.setattr(main_typer, "setup_logging", fake_setup_logging)

    ctx = SimpleNamespace(obj=None)
    main_typer.default_options(ctx)

    assert captured["log_dir"] == settings.logging_directory
    assert ctx.obj == {"api-request-settings": settings}


def test_main_typer_app_metadata() -> None:
    """Typer app should expose expected name and no-args behavior."""
    assert main_typer.app.info.name == "api-request"
    assert main_typer.app.info.no_args_is_help is True
