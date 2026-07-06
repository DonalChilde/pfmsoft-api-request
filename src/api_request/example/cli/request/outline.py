"""This module contains the implementation of the `outline-request` and `outline-group` commands for the ESI Link CLI.

These commands allow users to generate outlines for requests and request groups, which
can be used as templates for creating new requests and request groups.
"""

from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer
from rich.console import Console
from yaml import safe_dump

from esi_link.helpers.save_text_file import save_text_file
from esi_link.request.models import Request, RequestGroup
from esi_link.type_defs import Lang, LangEnum

app = typer.Typer(no_args_is_help=True)


@app.command(name="outline-request")
def outline_request(
    ctx: typer.Context,
    output_file: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output-file",
            help="The file to save the request outline to. If not provided, the outline will be printed to stdout.",
        ),
    ] = None,
    file_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="The format to use for the outline. Supported formats are 'json' and 'yaml'.",
            show_default=True,
        ),
    ] = "json",
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Whether to overwrite the output file if it already exists. If not set and the output file already exists, an error will be raised.",
        ),
    ] = False,
    pipe_output: Annotated[
        bool,
        typer.Option(
            "--pipe",
            help="Whether to pipe the outline output to stdout. If set, the outline will be printed without extra text.",
        ),
    ] = False,
    language: Annotated[
        LangEnum,
        typer.Option(
            "--language",
            help="The language to use for the request outline.",
            show_default=True,
        ),
    ] = LangEnum.EN,
):
    """Generate an outline for a request and save it to a file or print it to stdout."""
    request = _generate_request_outline(language=language.value)
    if file_format == "json":
        output = request.to_json_string(indent=2)
    elif file_format == "yaml":
        json_compatible_dict = request.to_object()
        output = safe_dump(json_compatible_dict, sort_keys=False)
    else:
        raise ValueError(f"Unsupported format: {file_format}")
    if pipe_output:
        print(output)
        return
    console = Console()
    if output_file is not None:
        saved = save_text_file(
            text=output,
            output_dir=output_file.parent,
            file_name=output_file.name,
            overwrite=overwrite,
        )
        console.print(f"Request outline saved to [bold green]{saved}[/bold green]")
    else:
        console.print("Request outline:")
        console.print(output)


@app.command(name="outline-group")
def outline_request_group(
    ctx: typer.Context,
    output_file: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output-file",
            help="The file to save the request outline to. If not provided, the outline will be printed to stdout.",
        ),
    ] = None,
    file_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="The format to use for the outline. Supported formats are 'json' and 'yaml'.",
            show_default=True,
        ),
    ] = "json",
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Whether to overwrite the output file if it already exists. If not set and the output file already exists, an error will be raised.",
        ),
    ] = False,
    pipe_output: Annotated[
        bool,
        typer.Option(
            "--pipe",
            help="Whether to pipe the outline output to stdout. If set, the outline will be printed without extra text.",
        ),
    ] = False,
    language: Annotated[
        LangEnum,
        typer.Option(
            "--language",
            help="The language to use for the request group outline.",
            show_default=True,
        ),
    ] = LangEnum.EN,
    request_count: Annotated[
        int,
        typer.Option(
            "-c",
            "--request-count",
            help="The number of requests to include in the request group outline.",
            show_default=True,
        ),
    ] = 2,
):
    """Generate an outline for a request group and save it to a file or print it to stdout."""
    request_group = _generate_request_group_outline(
        lanuage=language.value, request_count=request_count
    )
    if file_format == "json":
        output = request_group.to_json_string(indent=2)
    elif file_format == "yaml":
        json_compatible_dict = request_group.to_object()
        output = safe_dump(json_compatible_dict, sort_keys=False)
    else:
        raise ValueError(f"Unsupported format: {file_format}")
    if pipe_output:
        print(output)
        return
    console = Console()
    if output_file is not None:
        saved = save_text_file(
            text=output,
            output_dir=output_file.parent,
            file_name=output_file.name,
            overwrite=overwrite,
        )
        console.print(
            f"Request group outline saved to [bold green]{saved}[/bold green]"
        )
    else:
        console.print("Request group outline:")
        console.print(output)


def _generate_request_outline(language: Lang = "en") -> Request:
    return Request(
        request_id=uuid4(),
        operation_id="operation_id_goes_here",
        description="Request description goes here.",
        language=language,
    )


def _generate_request_group_outline(
    lanuage: Lang = "en", request_count: int = 2
) -> RequestGroup:
    requests = {
        x.request_id: x
        for x in (
            _generate_request_outline(language=lanuage) for _ in range(request_count)
        )
    }
    return RequestGroup(
        group_id=uuid4(),
        description="Request group description goes here.",
        requests=requests,
    )
