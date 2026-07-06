"""Helper functions for the ESI Link CLI."""

from typing import cast

from typer import Context

from esi_link.settings import EsiLinkSettings


def get_esi_link_settings_from_context(ctx: Context) -> EsiLinkSettings:
    """Helper function to get the ESI Link settings from the Typer context."""
    if ctx.obj is None or "esi-link-settings" not in ctx.obj:
        raise ValueError("ESI Link settings not found in context.")
    return cast(EsiLinkSettings, ctx.obj["esi-link-settings"])
