"""Helper functions for the api-request CLI."""

from typing import cast

from typer import Context

from api_request.settings import ApiRequestSettings


def get_auth_manager_settings_from_context(ctx: Context) -> ApiRequestSettings:
    """Return ApiRequestSettings stored in the Typer context.

    Args:
        ctx: Typer command context whose obj mapping should contain the
            initialized ApiRequestSettings.

    Returns:
        ApiRequestSettings stored under the api-request-settings key.

    Raises:
        ValueError: If the context does not contain initialized ApiRequestSettings.
    """
    if ctx.obj is None or "api-request-settings" not in ctx.obj:
        raise ValueError("ApiRequestSettings not found in context.")
    return cast(ApiRequestSettings, ctx.obj["api-request-settings"])
