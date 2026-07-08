"""Command-line interface for making API requests."""

from collections.abc import Hashable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.json import JSON

from api_request import ApiRequester, Request, Response, __app_name__, __version__
from api_request.cache import SqliteCacheFactory
from api_request.rate_limit.aio_limiter import AiolimiterRateLimiterFactory
from api_request.request.models import Requests, RequestsRoot

from .helpers import get_auth_manager_settings_from_context, get_stdin

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
    application_directory: Annotated[
        Path,
        typer.Option(
            "--app-dir",
            help="Path to the application directory. If not provided, the default application directory will be used.",
            file_okay=False,
            dir_okay=True,
            writable=True,
        ),
    ]
    | None = None,
    max_rate: Annotated[
        float,
        typer.Option(
            "--max-rate",
            help="Maximum number of requests per time period for the rate limiter.",
        ),
    ] = 50.0,
    time_period: Annotated[
        float,
        typer.Option(
            "--time-period",
            help="Time period in seconds for the rate limiter.",
        ),
    ] = 60.0,
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
    if quiet:
        messenger = Console(stderr=True, quiet=True)
    else:
        messenger = Console(stderr=True)
    settings = get_auth_manager_settings_from_context(ctx)
    if version:
        typer.echo(f"{__app_name__} v{__version__}")
        typer.echo(f"Application directory: {settings.application_directory}")
        typer.echo(f"Cache directory: {settings.cache_directory}")
        typer.echo(f"Cache file: {settings.cache_file}")
        typer.echo(f"Logging directory: {settings.logging_directory}")
        raise typer.Exit()
    input_data = get_stdin() if file_path == Path("-") else file_path.read_text()
    requests = RequestsRoot.model_validate_json(input_data).root
    if not requests:
        messenger.print(
            "[bold red]Error: No requests found in the input file.[/bold red]"
        )
        raise typer.Exit(code=1)
    if application_directory:
        settings.application_directory = application_directory

    async def run_requests[T: Hashable](requests_to_run: Requests[T]):
        cache_factory = SqliteCacheFactory(settings.cache_file)
        rate_limiter_factory = AiolimiterRateLimiterFactory[str](
            max_rate=max_rate, time_period=time_period
        )

        async with ApiRequester(
            cache_factory=cache_factory,
            rate_limiter_factory=rate_limiter_factory,
        ) as requester:
            responses = await requester.process_requests(requests_to_run)
