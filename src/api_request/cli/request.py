from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.json import JSON

from api_request import ApiRequester, Request, Response, __app_name__, __version__

from .helpers import get_auth_manager_settings_from_context

app = typer.Typer(
    no_args_is_help=True, help="A command-line tool for making API requests."
)


@app.command("api-request", help="Make an API request.")
def request(
    ctx: Annotated[typer.Context, typer.Option(hidden=True)],
    file_path: Annotated[
        Path,
        typer.Option(
            "--from",
            help="Path to the request file.",
            allow_dash=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output_path: Annotated[
        Path,
        typer.Option(
            "--to",
            help="Path to the output file.",
            allow_dash=True,
            file_okay=True,
            dir_okay=False,
            writable=True,
        ),
    ],
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Display the output in plain text markdown instead of Rich markdown.",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Whether to overwrite the output file if it already exists.",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            help="Suppress output messages.",
        ),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the version of the api-request CLI.",
            is_eager=True,
        ),
    ] = False,
):
    """Make an API request."""
    settings = get_auth_manager_settings_from_context(ctx)
    if version:
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()
