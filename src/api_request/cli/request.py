"""Command-line interface for making API requests."""

import asyncio
import logging
from collections.abc import Hashable
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.json import JSON

from api_request import ApiRequester, __app_name__, __version__
from api_request.cache import SqliteCacheFactory
from api_request.helpers.save_text_file import save_text_file
from api_request.logging_config import setup_logging
from api_request.rate_limit.aio_limiter import AiolimiterRateLimiterFactory
from api_request.request.models import Requests, RequestsRoot, Responses, ResponsesRoot
from api_request.settings import get_settings

from .helpers import get_stdin

logger = logging.getLogger(__name__)

app = typer.Typer(
    no_args_is_help=True, help="A command-line tool for making API requests."
)


@app.command("api-request", help="Make an API request.")
def request(
    ctx: Annotated[typer.Context, typer.Option(hidden=True)],
    file_in: Annotated[
        Path,
        typer.Option(
            "--from",
            help="Path to the request file.",
            allow_dash=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = Path("-"),
    file_out: Annotated[
        Path,
        typer.Option(
            "--to",
            help="Path to the output file.",
            allow_dash=True,
            file_okay=True,
            dir_okay=False,
            writable=True,
        ),
    ] = Path("-"),
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
    indent: Annotated[
        int | None,
        typer.Option(
            "--indent",
            help="Number of spaces to use for indentation in the output JSON.",
        ),
    ] = None,
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
    """Make an API request.

    Requests use UUIDs as keys to identify requests and responses.

    If you need to generate a UUID for a request, you can use the `uuidgen` command-line
    tool or any other UUID generator.

    Using `uuidgen`:
    ```bash
    uuidgen
    ```

    Using python:
    ```bash
    python -c "import uuid; print(uuid.uuid4())"
    or
    python3 -c "import uuid; print(uuid.uuid4())"
    ```
    """
    if quiet:
        messenger = Console(stderr=True, quiet=True)
    else:
        messenger = Console(stderr=True)
    settings = get_settings()
    if application_directory:
        settings.application_directory = application_directory
    setup_logging(log_dir=settings.logging_directory)
    logger.info(
        f"Starting {__app_name__} v{__version__} with settings: {asdict(settings)!r}"
    )
    if version:
        typer.echo(f"{__app_name__} v{__version__}")
        typer.echo(f"Application directory: {settings.application_directory}")
        typer.echo(f"Cache directory: {settings.cache_directory}")
        typer.echo(f"Cache file: {settings.cache_file}")
        typer.echo(f"Logging directory: {settings.logging_directory}")
        raise typer.Exit()
    input_data = get_stdin() if file_in == Path("-") else file_in.read_text()
    requests = RequestsRoot.model_validate_json(input_data).root
    if not requests:
        messenger.print(
            "[bold red]Error: No requests found in the input file.[/bold red]"
        )
        raise typer.Exit(code=1)

    async def run_requests[T: Hashable](requests_to_run: Requests[T]) -> Responses[T]:
        cache_factory = SqliteCacheFactory(settings.cache_file)
        rate_limiter_factory = AiolimiterRateLimiterFactory[T](
            max_rate=max_rate, time_period=time_period
        )

        async with ApiRequester(
            cache_factory=cache_factory,
            rate_limiter_factory=rate_limiter_factory,
        ) as requester:
            responses = await requester.process_requests(requests_to_run)
            return responses

    responses = asyncio.run(run_requests(requests))
    if file_out == Path("-"):
        if plain:
            print(ResponsesRoot(root=responses).model_dump_json(indent=indent))
        else:
            messenger.print(
                JSON(ResponsesRoot(root=responses).model_dump_json(indent=indent))
            )
    else:
        output_path = save_text_file(
            text=ResponsesRoot(root=responses).model_dump_json(indent=indent),
            output_directory=file_out.parent,
            file_name=file_out.name,
            overwrite=overwrite,
        )
        messenger.print(f"[bold green]Responses saved to {output_path}[/bold green]")


_example_request_status = {
    "request_key": "293c20f6-7356-4787-9fb9-3833ed9a4956",
    "method": "get",
    "url": "https://esi.evetech.net/status/",
    "cache_key": "af7c3da6-355b-4ece-abf3-b79ce625ea37",
    "rate_key": "status",
}
