"""Module for working with ESI app credentials."""

# pyright: standard
import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from esi_link.auth.models import EsiAppCredentialsRoot
from esi_link.cli.helpers import get_esi_link_settings_from_context
from esi_link.esi_link_api import EsiLink

from ...protocols import AuthManagerProtocol

app = typer.Typer(
    no_args_is_help=True, name="credentials", help="Manage ESI app credentials."
)


@app.command(name="add")
def add_credentials(
    ctx: typer.Context,
    credentials_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the credentials file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Whether to overwrite existing credentials."),
    ] = False,
) -> None:
    """Add or replace credentials."""
    console = Console()
    settings = get_esi_link_settings_from_context(ctx)
    console.print(f"[blue]Loading credentials from {credentials_file}...[/blue]")
    credentials = EsiAppCredentialsRoot.model_validate_json(
        credentials_file.read_text()
    ).root
    console.print("[green]Credentials loaded successfully.[/green]")

    console.print(f"[blue]Adding credentials to database...[/blue]")

    async def _add_creds() -> None:
        esi_link = EsiLink(settings)
        async with esi_link:
            esi_link.app_data.save_credentials(credentials, overwrite=overwrite)

    asyncio.run(_add_creds())
    console.print("[green]Credentials added successfully.[/green]")


@app.command()
def display(ctx: typer.Context) -> None:
    """Display the currently stored credentials."""
    console = Console()
    settings = get_esi_link_settings_from_context(ctx)

    async def _display() -> None:
        esi_link = EsiLink(settings)
        async with esi_link:
            credentials = esi_link.app_data.get_credentials()
            if credentials is None:
                console.print("No credentials found.")
                raise typer.Exit(0)
            console.print("Current Credentials:")
            console.print(credentials)

    asyncio.run(_display())
