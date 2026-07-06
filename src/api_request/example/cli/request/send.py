"""This module contains the implementation of the `send` command for the ESI Link CLI.

This command allows users to send a request or request group defined in a JSON file and
receive the response.
"""

import asyncio
import json
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console
from whenever import Instant
from yaml import safe_load

from esi_link.cli.helpers import get_esi_link_settings_from_context
from esi_link.esi_link_api import EsiLink
from esi_link.helpers.file_safe_string import file_safe_string
from esi_link.helpers.save_text_file import save_text_file
from esi_link.request.models import Request, RequestGroup
from esi_link.response.models import ResponseDebugGroup, ResponseGroup
from esi_link.response.response_factories import (
    response_group_to_response_data_group,
    response_to_data_only,
)

app = typer.Typer(no_args_is_help=True)


@app.command()
def send(
    ctx: typer.Context,
    request_file: Annotated[
        Path,
        typer.Argument(
            help="The path to the request file to execute. This should be a JSON file containing either a Request or RequestGroup object.",
            file_okay=True,
            dir_okay=False,
            exists=True,
            readable=True,
        ),
    ],
    output_directory: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output-directory",
            help="The directory to save the response file to. If not provided, the response will not be saved to disk.",
            file_okay=False,
            dir_okay=True,
            exists=True,
            writable=True,
        ),
    ] = None,
    file_name: Annotated[
        str | None,
        typer.Option(
            "--file-name",
            help="The name to use for the response file. If not provided, a name will be "
            "generated based on the request ID and current date.",
        ),
    ] = None,
    data_model: Annotated[
        Literal["detailed", "data-plus", "data-only"],
        typer.Option(
            "--data-model",
            help="The format to output the response data in. Supported formats are "
            "'detailed', 'data-plus', and 'data-only'. "
            "'detailed' includes all available information, "
            "'data-plus' the original request, the received json data, and the request metrics., "
            "and 'data-only' includes only the request_id and received json data.",
            show_default=True,
        ),
    ] = "data-plus",
    debug: Annotated[
        bool,
        typer.Option(
            "--debug", help="Whether to output detailed error information to stderr."
        ),
    ] = False,
    pipe_output: Annotated[
        bool,
        typer.Option(
            "--pipe",
            help="Whether to pipe the response output to stdout. If set, the response objects will be printed without extra text.",
        ),
    ] = False,
) -> None:
    """Send a request or request group from a JSON file.

    Errors will be logged, and optionally output to stderr if the --debug flag is set,
    but will not cause the command to fail with an exception.
    """
    console = Console()
    err_console = Console(stderr=True)
    if not pipe_output and not output_directory:
        console.print(
            "[bold yellow]Warning: No output directory specified. The response will not be saved to disk or piped to stdout.[/bold yellow]"
        )
        raise typer.Exit(1)
    settings = get_esi_link_settings_from_context(ctx)
    loaded_request = _load_request_from_file(request_file)

    access = EsiLink(settings)

    async def get_response(
        request: Request | RequestGroup,
    ) -> tuple[ResponseGroup, ResponseDebugGroup | None]:
        if isinstance(request, Request):
            async with access:
                return await access.send_request(request)
        else:
            async with access:
                return await access.send_request_group(request)

    response, debug_response = asyncio.run(get_response(loaded_request))

    if debug_response is not None:
        if debug:
            err_console.print("[bold red]Debug Information:[/bold red]")
            err_console.print(debug_response.to_string(indent=2))
        else:
            err_console.print(
                "[bold red]Errors were encountered during the processing of the request. "
                "Check the logs for more information, or "
                "use the --debug flag to see detailed error information.[/bold red]"
            )
    match data_model:
        case "detailed":
            output_str = response.to_string(indent=2)
        case "data-plus":
            output_model = response_group_to_response_data_group(response)
            output_str = output_model.to_string(indent=2)
        case "data-only":
            output_data = response_to_data_only(response)
            output_str = json.dumps(output_data, indent=2)

    if output_directory is not None:
        output_directory.mkdir(parents=True, exist_ok=True)
        if file_name is None:
            now_str = file_safe_string(f"{Instant.now()}")
            file_name = f"{response.request_group.group_id}-{now_str}-response-{data_model}.json"
        saved = save_text_file(
            text=output_str,
            output_dir=output_directory,
            file_name=file_name,
            overwrite=True,
        )
        if not pipe_output:
            console.print(f"Saved response to disk at: {saved}", style="bold green")
    if pipe_output:
        print(output_str)
    if debug_response is not None:
        raise typer.Exit(code=1)


def _load_request_from_file(request_file: Path) -> Request | RequestGroup:
    """Load a Request or RequestGroup object from a JSON or YAML file."""
    if request_file.stem.endswith("-request"):
        if request_file.suffix == ".json":
            request_data = Request.from_json_string(request_file.read_text())
        elif request_file.suffix in [".yaml", ".yml"]:
            request_object = safe_load(request_file.read_text())
            request_data = Request.from_object(request_object)
        else:
            raise ValueError(
                f"Unsupported file format: {request_file.suffix}. Supported formats are .json, .yaml, and .yml."
            )
    elif request_file.stem.endswith("-request-group"):
        if request_file.suffix == ".json":
            request_data = RequestGroup.from_json_string(request_file.read_text())
        elif request_file.suffix in [".yaml", ".yml"]:
            request_object = safe_load(request_file.read_text())
            request_data = RequestGroup.from_object(request_object)
        else:
            raise ValueError(
                f"Unsupported file format: {request_file.suffix}. Supported formats are .json, .yaml, and .yml."
            )
    else:
        raise ValueError(
            f"The request file name must end with either '-request.json' or '-request-group.json' to indicate whether it contains a Request or RequestGroup object."
        )
    return request_data
