"""CLI commands for fetching ESI schemas."""

# pyright: standard
import asyncio
from typing import Annotated

import typer
from rich.console import Console

from esi_link.cli.helpers import get_esi_link_settings_from_context
from esi_link.esi_link_api import EsiLink
from esi_link.schema.schema_cache_sqlite import CachedSchema

app = typer.Typer(no_args_is_help=True)


@app.command()
def fetch(
    ctx: typer.Context,
    compatibility_date: Annotated[
        str | None,
        typer.Option(
            "-c",
            "--compatibility-date",
            help="The compatibility date for the schema to fetch. If not provided, the "
            "latest valid compatibility date will be used.",
        ),
    ] = None,
) -> None:
    """Fetch and cache the ESI schema for a given compatibility date.

    This can be used to update an already cached schema or to fetch and cache a new schema
    for a compatibility date that has not been cached yet. If no compatibility date is
    provided, the latest valid compatibility date will be used.
    """
    console = Console()
    settings = get_esi_link_settings_from_context(ctx)

    async def _fetch() -> CachedSchema:
        esi_link = EsiLink(settings)
        async with esi_link:
            valid_dates = esi_link.app_data.schema_cache.schema_versions()
            if compatibility_date is None:
                if not valid_dates:
                    console.print("No valid compatibility dates found.")
                    raise typer.Exit(0)
                latest_date = max(valid_dates)
                console.print(
                    f"No compatibility date provided. Using latest valid compatibility "
                    f"date {latest_date}."
                )
                compatibility_date_to_fetch = latest_date
            else:
                if compatibility_date not in valid_dates:
                    console.print(
                        f"Compatibility date {compatibility_date} is not valid. Valid "
                        f"compatibility dates are: {', '.join(valid_dates)}."
                    )
                    raise typer.Exit(1)
                compatibility_date_to_fetch = compatibility_date
            cached_schema = esi_link.app_data.schema_cache.fetch_and_cache_schema(
                compatibility_date_to_fetch
            )
            return cached_schema

    cached_schema = asyncio.run(_fetch())
    console.print(
        f"Fetched and cached schema for compatibility date {cached_schema.esi_schema.version}."
    )
