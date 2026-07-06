"""CLI commands for listing cached ESI schemas."""

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown

from esi_link.cli.helpers import get_esi_link_settings_from_context
from esi_link.esi_link_api import EsiLink
from esi_link.schema.schema_cache_sqlite import AvailableCachedSchema

app = typer.Typer(no_args_is_help=True)


@app.command()
def list_cached(ctx: typer.Context) -> None:
    """List all cached schemas."""
    console = Console()
    settings = get_esi_link_settings_from_context(ctx)

    async def _list_cached() -> None:
        async with EsiLink(settings) as esi_link:
            await asyncio.sleep(
                0
            )  # Yield control to ensure proper async context management
            cached_schemas = esi_link.app_data.schema_cache.cached_schemas()
            if not cached_schemas:
                console.print("No cached schemas found.")
                raise typer.Exit(0)
            console.print("Cached Schemas:")
            console.print(Markdown(_markdown_format_cached_schemas(cached_schemas)))

    asyncio.run(_list_cached())


def _markdown_format_cached_schemas(cached_schemas: list[AvailableCachedSchema]) -> str:
    # A markdown table with columns for the schema name, path, and time until expiration in days:hours:seconds. If the schema is expired, show "Expired" in the time until expiration column.
    if not cached_schemas:
        return "No cached schemas found."
    lines: list[str] = [
        "| Schema Name | Download Date | Time Until Expiration |",
        "|-------------|-----------------------|----------------------|",
    ]
    for cached_schema in cached_schemas:
        compatibility_date = cached_schema.compatibility_date
        download_date = cached_schema.timestamp_instant
        seconds_remaining = cached_schema.seconds_remaining
        if seconds_remaining < 0:
            time_until_expiration = "Expired"
        else:
            days, remainder = divmod(seconds_remaining, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_until_expiration = f"{days}d {hours}h {minutes}m {seconds}s"
        lines.append(
            f"| {compatibility_date} | {download_date} | {time_until_expiration} |"
        )
    return "\n".join(lines)
