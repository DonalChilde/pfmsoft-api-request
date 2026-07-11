"""Tests for the request CLI command."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
import typer

from api_request.cli.request import request as request_cmd
from api_request.request.models import (
    Request,
    Response,
    ResponseMetadata,
    Responses,
    Source,
)
from api_request.settings import SETTINGS_KEY, ApiRequestSettings


@dataclass(slots=True)
class _FakeConsole:
    stderr: bool
    quiet: bool = False
    messages: list[object] = field(default_factory=list)

    def print(self, message: object) -> None:
        self.messages.append(message)


class _FakeApiRequester:
    next_result: Responses
    last_force_fail_on: set[int] | None = None

    def __init__(
        self,
        *,
        cache_factory: object,
        rate_limiter_factory: object,
        force_fail_on: set[int],
    ) -> None:
        _ = cache_factory, rate_limiter_factory
        type(self).last_force_fail_on = force_fail_on

    async def __aenter__(self) -> _FakeApiRequester:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        _ = exc_type, exc, tb

    async def process_requests(self, requests_to_run: dict[UUID, Request]) -> Responses:
        _ = requests_to_run
        return type(self).next_result


def _build_successful_responses(requests: dict[UUID, Request]) -> Responses:
    request_key = next(iter(requests.keys()))
    request = requests[request_key]
    metadata = ResponseMetadata(
        status_code=200,
        reason_phrase="OK",
        url=request.url,
        elapsed=1,
        bytes_downloaded=2,
        headers=(("Date", "Mon, 06 Jul 2026 18:00:00 GMT"),),
        received_timestamp=1_000,
    )
    response = Response(
        metadata=metadata,
        json={"ok": True},
        request=request,
        source=Source.NETWORK,
    )
    return Responses(successful={request_key: response}, failed={})


def _requests_json() -> str:
    return (
        '{"00000000-0000-0000-0000-000000000001":'
        '{"url":"https://example.invalid/data","method":"GET"}}'
    )


def test_request_cli_exits_for_empty_request_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty request input should fail with exit code 1 and message."""
    settings = ApiRequestSettings(
        application_directory=Path("/tmp/api-request"),
        logging_directory=Path("/tmp/api-request/logs"),
        web_cache_path=Path("/tmp/api-request/api_requests_web_cache.sqlite"),
    )
    consoles: list[_FakeConsole] = []

    def fake_console(*, stderr: bool, quiet: bool = False) -> _FakeConsole:
        console = _FakeConsole(stderr=stderr, quiet=quiet)
        consoles.append(console)
        return console

    monkeypatch.setattr(request_cmd, "setup_logging", lambda *, log_dir: None)
    monkeypatch.setattr(request_cmd, "get_stdin", lambda: "{}")
    monkeypatch.setattr(request_cmd, "Console", fake_console)

    with pytest.raises(typer.Exit) as exc:
        request_cmd.request(
            SimpleNamespace(obj={SETTINGS_KEY: settings}),
            file_in=Path("-"),
            quiet=True,
        )

    assert exc.value.exit_code == 1
    assert consoles[0].quiet is True
    assert any("No requests found" in str(message) for message in consoles[0].messages)


def test_request_cli_writes_plain_json_to_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """When output is stdout and --plain is set, command should print plain JSON."""
    settings = ApiRequestSettings(
        application_directory=Path("/tmp/api-request"),
        logging_directory=Path("/tmp/api-request/logs"),
        web_cache_path=Path("/tmp/api-request/api_requests_web_cache.sqlite"),
    )

    monkeypatch.setattr(request_cmd, "setup_logging", lambda *, log_dir: None)
    monkeypatch.setattr(request_cmd, "get_stdin", _requests_json)
    monkeypatch.setattr(request_cmd, "SqliteCacheFactory", lambda cache_file: object())
    monkeypatch.setattr(
        request_cmd,
        "AiolimiterRateLimiterFactory",
        lambda *, max_rate, time_period: object(),
    )
    monkeypatch.setattr(
        request_cmd,
        "Console",
        lambda *, stderr, quiet=False: _FakeConsole(stderr=stderr, quiet=quiet),
    )

    class _ConfiguredFakeApiRequester(_FakeApiRequester):
        async def process_requests(
            self, requests_to_run: dict[UUID, Request]
        ) -> Responses:
            return _build_successful_responses(requests_to_run)

    monkeypatch.setattr(request_cmd, "ApiRequester", _ConfiguredFakeApiRequester)

    request_cmd.request(
        SimpleNamespace(obj={SETTINGS_KEY: settings}),
        file_in=Path("-"),
        file_out=Path("-"),
        plain=True,
        indent=2,
        forced_fail_status_codes=[418],
    )

    captured = capsys.readouterr()
    assert "successful" in captured.out
    assert "failed" in captured.out
    assert _ConfiguredFakeApiRequester.last_force_fail_on == {418}


def test_request_cli_writes_file_and_reports_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When output is a file path, command should save JSON and report destination."""
    settings = ApiRequestSettings(
        application_directory=Path("/tmp/api-request"),
        logging_directory=Path("/tmp/api-request/logs"),
        web_cache_path=Path("/tmp/api-request/api_requests_web_cache.sqlite"),
    )
    output_file = tmp_path / "responses.json"
    consoles: list[_FakeConsole] = []
    save_call: dict[str, Any] = {}

    def fake_console(*, stderr: bool, quiet: bool = False) -> _FakeConsole:
        console = _FakeConsole(stderr=stderr, quiet=quiet)
        consoles.append(console)
        return console

    def fake_save_text_file(
        *,
        text: str,
        output_directory: Path,
        file_name: str,
        overwrite: bool,
    ) -> Path:
        save_call["text"] = text
        save_call["output_directory"] = output_directory
        save_call["file_name"] = file_name
        save_call["overwrite"] = overwrite
        return output_directory / file_name

    monkeypatch.setattr(request_cmd, "setup_logging", lambda *, log_dir: None)
    monkeypatch.setattr(request_cmd, "get_stdin", _requests_json)
    monkeypatch.setattr(request_cmd, "SqliteCacheFactory", lambda cache_file: object())
    monkeypatch.setattr(
        request_cmd,
        "AiolimiterRateLimiterFactory",
        lambda *, max_rate, time_period: object(),
    )
    monkeypatch.setattr(request_cmd, "Console", fake_console)
    monkeypatch.setattr(request_cmd, "save_text_file", fake_save_text_file)

    class _ConfiguredFakeApiRequester(_FakeApiRequester):
        async def process_requests(
            self, requests_to_run: dict[UUID, Request]
        ) -> Responses:
            return _build_successful_responses(requests_to_run)

    monkeypatch.setattr(request_cmd, "ApiRequester", _ConfiguredFakeApiRequester)

    request_cmd.request(
        SimpleNamespace(obj={SETTINGS_KEY: settings}),
        file_in=Path("-"),
        file_out=output_file,
        overwrite=True,
    )

    assert save_call["output_directory"] == output_file.parent
    assert save_call["file_name"] == output_file.name
    assert save_call["overwrite"] is True
    assert "successful" in save_call["text"]
    assert any("Responses saved to" in str(message) for message in consoles[0].messages)


def test_request_cli_respects_app_dir_and_rich_stdout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Command should apply app-dir override and print rich JSON to stdout."""
    settings = ApiRequestSettings(
        application_directory=Path("/tmp/original"),
        logging_directory=Path("/tmp/original/logs"),
        web_cache_path=Path("/tmp/original/api_requests_web_cache.sqlite"),
    )
    consoles: list[_FakeConsole] = []

    def fake_console(*, stderr: bool, quiet: bool = False) -> _FakeConsole:
        console = _FakeConsole(stderr=stderr, quiet=quiet)
        consoles.append(console)
        return console

    monkeypatch.setattr(request_cmd, "setup_logging", lambda *, log_dir: None)
    monkeypatch.setattr(request_cmd, "get_stdin", _requests_json)
    monkeypatch.setattr(request_cmd, "SqliteCacheFactory", lambda cache_file: object())
    monkeypatch.setattr(
        request_cmd,
        "AiolimiterRateLimiterFactory",
        lambda *, max_rate, time_period: object(),
    )
    monkeypatch.setattr(request_cmd, "Console", fake_console)
    monkeypatch.setattr(request_cmd, "JSON", lambda payload: {"json": payload})

    class _ConfiguredFakeApiRequester(_FakeApiRequester):
        async def process_requests(
            self, requests_to_run: dict[UUID, Request]
        ) -> Responses:
            return _build_successful_responses(requests_to_run)

    monkeypatch.setattr(request_cmd, "ApiRequester", _ConfiguredFakeApiRequester)

    request_cmd.request(
        SimpleNamespace(obj={SETTINGS_KEY: settings}),
        file_in=Path("-"),
        file_out=Path("-"),
        plain=False,
        app_dir=tmp_path,
    )

    assert settings.application_directory == tmp_path
    assert consoles[0].messages
    assert isinstance(consoles[0].messages[0], dict)
    assert "successful" in consoles[0].messages[0]["json"]
