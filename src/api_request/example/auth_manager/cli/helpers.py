"""Helpers for the auth_manager CLI."""

import sys
from typing import cast

from httpx2 import AsyncClient, Client
from typer import Context

from ..settings import USER_AGENT, AuthManagerSettings


def config_http_client(user_agent: str = USER_AGENT) -> Client:
    """Configures the HTTP client with the provided user agent."""
    return Client(headers={"User-Agent": user_agent})


async def config_async_http_client(user_agent: str = USER_AGENT) -> AsyncClient:
    """Configures the asynchronous HTTP client with the provided user agent."""
    return AsyncClient(headers={"User-Agent": user_agent})


def get_auth_manager_settings_from_context(ctx: Context) -> AuthManagerSettings:
    """Helper function to get the auth_manager settings from the Typer context."""
    if ctx.obj is None or "auth-manager-settings" not in ctx.obj:
        raise ValueError("Auth Manager settings not found in context.")
    return cast(AuthManagerSettings, ctx.obj["auth-manager-settings"])


def get_stdin() -> str:
    """Read from stdin until EOF and return the content as a string."""
    if sys.stdin.isatty():
        raise ValueError("Error: provide a file path or pipe data via stdin.")
    return sys.stdin.read()
