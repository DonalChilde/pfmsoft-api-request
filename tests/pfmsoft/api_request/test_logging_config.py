"""Tests for logging configuration setup."""

from __future__ import annotations

from pathlib import Path

from pfmsoft.api_request.logging_config import setup_logging


def test_setup_logging_creates_directory_and_applies_dict_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """setup_logging should create log dir and install expected handlers."""
    captured: dict[str, object] = {}
    log_dir = tmp_path / "logs"

    def fake_dict_config(config: dict[str, object]) -> None:
        captured["config"] = config

    monkeypatch.setattr("logging.config.dictConfig", fake_dict_config)

    setup_logging(log_dir)

    assert log_dir.exists()
    config = captured["config"]
    assert isinstance(config, dict)
    assert config["version"] == 1

    handlers = config["handlers"]
    assert handlers["file"]["filename"] == log_dir / "debug.log"
    assert handlers["rot_file_info"]["filename"] == log_dir / "rotating_info.log"
    assert handlers["rot_file_warn"]["filename"] == log_dir / "rotating_warn.log"
