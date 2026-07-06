"""Generate human readable documentation for the ESI schema."""

# pyright: standard
import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from esi_link.cli.helpers import get_esi_link_settings_from_context
from esi_link.esi_link_api import EsiLink
from esi_link.helpers.file_safe_string import file_safe_string
from esi_link.helpers.save_text_file import save_text_file
from esi_link.schema.schema_cache_sqlite import CachedSchema
from esi_link.schema.schema_doc import generate_esi_schema_doc

app = typer.Typer(no_args_is_help=True)


@app.command(name="generate-doc")
def generate_doc(
    ctx: typer.Context,
    compatibility_date: Annotated[
        str | None,
        typer.Option(
            "-c",
            "--compatibility-date",
            help="Compatibility date to generate documentation for. Defaults to None. "
            "If not provided, the latest valid compatibility date will be used.",
        ),
    ] = None,
    output_directory: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output directory path. Defaults to None. If not provided, the output will "
            "be written to the terminal.",
        ),
    ] = None,
    output_file: Annotated[
        str | None,
        typer.Option(
            "-f",
            "--output-file",
            help="Output file name. Defaults to None. If not provided, the filename will "
            "be generated automatically. Ignored if output directory is not provided.",
        ),
    ] = None,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Whether to overwrite existing files.")
    ] = False,
) -> None:
    """Generate human readable schema documentation."""
    console = Console()
    settings = get_esi_link_settings_from_context(ctx)

    async def get_schema() -> CachedSchema:
        esi_link = EsiLink(settings)
        async with esi_link:
            valid_dates = esi_link.app_data.schema_cache.schema_versions()
            if compatibility_date and compatibility_date not in valid_dates:
                console.print(
                    f"Compatibility date {compatibility_date} is not valid. Valid compatibility dates are:"
                )
                for date in valid_dates:
                    console.print(f"- {date}")
                console.print(
                    "Did you mean to ask for the latest valid compatibility date? If so, "
                    "run the command without providing a compatibility date."
                )
                raise typer.Exit(0)
            if not compatibility_date:
                cached_schema = (
                    esi_link.app_data.schema_cache.get_latest_cached_schema()
                )
            else:
                cached_schema = esi_link.app_data.schema_cache.get_cached_schema(
                    compatibility_date=compatibility_date
                )
            return cached_schema

    cached_schema = asyncio.run(get_schema())

    doc = generate_esi_schema_doc(
        cached_schema.esi_schema,
        download_date=cached_schema.timestamp_instant,
    )
    if not output_directory:
        console.print(doc)
        raise typer.Exit(0)
    if not output_file:
        output_file = (
            f"esi_schema_doc_{compatibility_date}_{cached_schema.timestamp_instant}.md"
        )
        output_file = file_safe_string(output_file)
    saved = save_text_file(
        text=doc,
        output_dir=output_directory,
        file_name=output_file,
        overwrite=overwrite,
    )
    console.print(f"Generated schema documentation written to {saved}")
