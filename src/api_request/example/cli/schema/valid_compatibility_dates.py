"""CLI commands for listing valid compatibility dates for ESI schemas."""

import asyncio

import typer
from rich.console import Console

from esi_link.cli.helpers import get_esi_link_settings_from_context
from esi_link.esi_link_api import EsiLink

app = typer.Typer(no_args_is_help=True)


@app.command(name="valid-dates")
def valid_compatibility_dates(ctx: typer.Context) -> None:
    """List all valid compatibility dates for ESI schemas."""
    console = Console()
    settings = get_esi_link_settings_from_context(ctx)

    async def _valid_compatibility_dates() -> None:
        esi_link = EsiLink(settings)
        async with esi_link:
            valid_dates = esi_link.app_data.schema_cache.schema_versions()
        if not valid_dates:
            console.print("No valid compatibility dates found.")
            raise typer.Exit(0)
        console.print("Valid Compatibility Dates:")
        for date in valid_dates:
            console.print(f"- {date}")

    asyncio.run(_valid_compatibility_dates())
