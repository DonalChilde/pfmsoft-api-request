"""Tests for HTTP client factory helpers."""

from __future__ import annotations

import asyncio

import pytest

from pfmsoft.api_request.helpers import http_session_factory


class _FakeClient:
    def __init__(self, *, headers: dict[str, str]):
        self.headers = headers
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeAsyncClient:
    def __init__(self, *, headers: dict[str, str]):
        self.headers = headers
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def test_config_http_client_uses_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Synchronous factory should pass User-Agent header to Client."""
    monkeypatch.setattr(http_session_factory, "Client", _FakeClient)

    client = http_session_factory.config_http_client("test-agent")

    assert isinstance(client, _FakeClient)
    assert client.headers == {"User-Agent": "test-agent"}


def test_config_async_http_client_uses_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async factory should pass User-Agent header to AsyncClient."""
    monkeypatch.setattr(http_session_factory, "AsyncClient", _FakeAsyncClient)

    client = asyncio.run(http_session_factory.config_async_http_client("test-agent"))

    assert isinstance(client, _FakeAsyncClient)
    assert client.headers == {"User-Agent": "test-agent"}


def test_client_manager_closes_client_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Context-managed sync clients should always close after use."""
    monkeypatch.setattr(http_session_factory, "Client", _FakeClient)

    with http_session_factory.client_manager("test-agent") as client:
        assert client.headers == {"User-Agent": "test-agent"}
        assert client.closed is False

    assert client.closed is True


def test_client_manager_closes_client_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Context-managed sync clients should close even when body raises."""
    monkeypatch.setattr(http_session_factory, "Client", _FakeClient)

    with pytest.raises(RuntimeError, match="boom"):
        with http_session_factory.client_manager("test-agent"):
            raise RuntimeError("boom")


def test_async_client_manager_closes_client_on_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Context-managed async clients should close after use."""
    monkeypatch.setattr(http_session_factory, "AsyncClient", _FakeAsyncClient)

    async def run() -> _FakeAsyncClient:
        async with http_session_factory.async_client_manager("test-agent") as client:
            assert client.headers == {"User-Agent": "test-agent"}
            assert client.closed is False
            return client

    client = asyncio.run(run())
    assert client.closed is True


def test_async_client_manager_closes_client_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Context-managed async clients should close when body raises."""
    monkeypatch.setattr(http_session_factory, "AsyncClient", _FakeAsyncClient)

    async def run() -> None:
        async with http_session_factory.async_client_manager("test-agent"):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(run())


def test_client_manager_propagates_creation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync manager should propagate client construction errors cleanly."""

    def raising_client(*, headers: dict[str, str]) -> _FakeClient:
        _ = headers
        raise RuntimeError("client-create-failed")

    monkeypatch.setattr(http_session_factory, "Client", raising_client)

    with pytest.raises(RuntimeError, match="client-create-failed"):
        with http_session_factory.client_manager("test-agent"):
            raise AssertionError("unreachable")


def test_async_client_manager_propagates_creation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async manager should propagate async client construction errors cleanly."""

    async def raising_async_client(_user_agent: str) -> _FakeAsyncClient:
        raise RuntimeError("async-client-create-failed")

    monkeypatch.setattr(
        http_session_factory, "config_async_http_client", raising_async_client
    )

    async def run() -> None:
        async with http_session_factory.async_client_manager("test-agent"):
            raise AssertionError("unreachable")

    with pytest.raises(RuntimeError, match="async-client-create-failed"):
        asyncio.run(run())


def test_client_manager_allows_none_client_without_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync manager should skip close when client construction returns None."""
    monkeypatch.setattr(http_session_factory, "config_http_client", lambda _ua: None)

    with http_session_factory.client_manager("test-agent") as client:
        assert client is None


def test_async_client_manager_allows_none_client_without_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async manager should skip aclose when async client creation returns None."""

    async def return_none(_ua: str):
        return None

    monkeypatch.setattr(http_session_factory, "config_async_http_client", return_none)

    async def run() -> None:
        async with http_session_factory.async_client_manager("test-agent") as client:
            assert client is None

    asyncio.run(run())
