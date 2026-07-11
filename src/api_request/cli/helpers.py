"""Helper functions for the api-request CLI."""

import sys
from typing import cast

from typer import Context

from api_request.settings import SETTINGS_KEY, ApiRequestSettings


def get_api_request_settings_from_context(ctx: Context) -> ApiRequestSettings:
    """Return ApiRequestSettings stored in the Typer context.

    Args:
        ctx: Typer command context whose obj mapping should contain the
            initialized ApiRequestSettings.

    Returns:
        ApiRequestSettings stored under the `settings.SETTINGS_KEY` key.

    Raises:
        ValueError: If the context does not contain initialized ApiRequestSettings.
    """
    if ctx.obj is None or SETTINGS_KEY not in ctx.obj:
        raise ValueError("ApiRequestSettings not found in context.")
    return cast(ApiRequestSettings, ctx.obj[SETTINGS_KEY])


def get_stdin() -> str:
    """Read piped or redirected stdin content until EOF.

    Returns:
        Full stdin content as a string.

    Raises:
        ValueError: If stdin is attached to an interactive terminal instead
            of a pipe or redirected input source.
    """
    if sys.stdin.isatty():
        raise ValueError("Error: provide a file path or pipe data via stdin.")
    return sys.stdin.read()
