"""Command-line interface for making API requests."""

import asyncio
import logging
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
    no_args_is_help=True,
    help="Commands for executing JSON-defined API request batches.",
)


@app.command("api-request", help="Make an API request.")
def request(
    ctx: Annotated[typer.Context, typer.Option(hidden=True)],
    file_in: Annotated[
        Path,
        typer.Option(
            "--from",
            help="Input JSON file path. Use '-' (default) to read stdin.",
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
            help="Output JSON file path. Use '-' (default) to write stdout.",
            allow_dash=True,
            file_okay=True,
            dir_okay=False,
            writable=True,
        ),
    ] = Path("-"),
    app_dir: Annotated[
        Path | None,
        typer.Option(
            "--app-dir",
            help="Application directory override for cache/log/settings paths.",
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
            help="Rate limiter max acquisitions per time window.",
        ),
    ] = 50.0,
    time_period: Annotated[
        float,
        typer.Option(
            "--time-period",
            help="Rate limiter window length in seconds.",
        ),
    ] = 60.0,
    forced_fail_status_codes: Annotated[
        list[int] | None,
        typer.Option(
            "--code",
            help="HTTP status codes that should be treated as batch request failures.",
        ),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Write plain JSON to stdout instead of Rich formatted output.",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite existing output file when --to is a file path.",
        ),
    ] = False,
    indent: Annotated[
        int | None,
        typer.Option(
            "--indent",
            help="Indent width for output JSON (compact when omitted).",
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            help="Suppress non-essential CLI messages.",
        ),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show CLI version and resolved runtime directories.",
            is_eager=True,
        ),
    ] = False,
):
    """Execute a batch of API requests from JSON input.

    Input format:
        A JSON object keyed by request UUID. Each value must match the
        `Request` model shape.

    Output format:
        A JSON object matching the `Responses` model with `successful` and
        `failed` maps keyed by the same request UUIDs.

    Notes:
        - `--from -` reads input JSON from stdin.
        - `--to -` writes output to stdout.
        - Use `--plain` for plain stdout JSON when writing to stdout.
        - Use `--code` to treat specific HTTP status codes as batch request failures.
          Any requests that have not made it to the network yet will fail if any of the
          specified codes are present in a response.

    UUID generation quick reference:
        Request maps are keyed by UUID strings. Generate UUID values with one
        of the commands below.

        Shell:
            ```bash
            uuidgen
            ```

        Python:
            ```bash
            python -c "import uuid; print(uuid.uuid4())"
            ```

            ```bash
            python3 -c "import uuid; print(uuid.uuid4())"
            ```
    """
    if quiet:
        messenger = Console(stderr=True, quiet=True)
    else:
        messenger = Console(stderr=True)
    settings = get_settings()
    if app_dir:
        settings.application_directory = app_dir
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
    force_codes: set[int] = (
        set(forced_fail_status_codes) if forced_fail_status_codes else set()
    )

    async def run_requests(
        requests_to_run: Requests, force_fail_codes: set[int]
    ) -> Responses:
        cache_factory = SqliteCacheFactory(settings.cache_file)
        rate_limiter_factory = AiolimiterRateLimiterFactory(
            max_rate=max_rate, time_period=time_period
        )

        async with ApiRequester(
            cache_factory=cache_factory,
            rate_limiter_factory=rate_limiter_factory,
            force_fail_on=force_fail_codes,
        ) as requester:
            responses = await requester.process_requests(requests_to_run)
            return responses

    responses = asyncio.run(run_requests(requests, force_codes))
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
