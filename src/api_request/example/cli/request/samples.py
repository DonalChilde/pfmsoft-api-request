# pyright: standard
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console
from yaml import safe_dump

from esi_link import example_requests
from esi_link.helpers.save_text_file import save_text_file
from esi_link.request.models import Request, RequestGroup, RequestGroupRoot, RequestRoot

app = typer.Typer(no_args_is_help=True)


@app.command(name="sample-requests")
def save_samples(
    ctx: typer.Context,
    output_directory: Annotated[
        Path,
        typer.Argument(
            help="Output directory path.",
        ),
    ],
    character_id: Annotated[
        int | None,
        typer.Option(
            "--character-id", help="Character ID to use for authorized request samples."
        ),
    ] = None,
    file_format: Annotated[
        Literal["json", "yaml"],
        typer.Option(
            "--format",
            help="The format to use for the sample requests. Supported formats are 'json' and 'yaml'. defaults to 'json'.",
            show_default=True,
        ),
    ] = "json",
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Whether to overwrite existing files.")
    ] = False,
) -> None:
    """Save example requests to disk."""
    console = Console()
    output_directory.mkdir(parents=True, exist_ok=True)
    request = example_requests.api_status()
    saved = _save_a_request(
        request=request,
        output_directory=output_directory,
        file_name=f"api_status-request.{file_format}",
        file_format=file_format,
        overwrite=overwrite,
    )
    console.print(f"Saved api_status request: {saved}")

    server_status_request = example_requests.server_status()
    saved = _save_a_request(
        request=server_status_request,
        output_directory=output_directory,
        file_name=f"server_status-request.{file_format}",
        file_format=file_format,
        overwrite=overwrite,
    )
    console.print(f"Saved server_status request: {saved}")

    universe_types_request = example_requests.universe_types()
    saved = _save_a_request(
        request=universe_types_request,
        output_directory=output_directory,
        file_name=f"universe_types-request.{file_format}",
        file_format=file_format,
        overwrite=overwrite,
    )
    console.print(f"Saved universe_types request: {saved}")

    status_group_requests = example_requests.status_group()
    saved = _save_a_request(
        request=status_group_requests,
        output_directory=output_directory,
        file_name=f"status_group-request-group.{file_format}",
        file_format=file_format,
        overwrite=overwrite,
    )
    console.print(f"Saved status group request: {saved}")
    if character_id is not None:
        character_attributes_request = example_requests.character_attributes(
            character_id
        )
        saved = _save_a_request(
            request=character_attributes_request,
            output_directory=output_directory,
            file_name=f"character_attributes-request.{file_format}",
            file_format=file_format,
            overwrite=overwrite,
        )
        console.print(f"Saved character attributes request: {saved}")


def _save_a_request(
    request: Request | RequestGroup,
    output_directory: Path,
    file_name: str,
    file_format: Literal["json", "yaml"] = "json",
    overwrite: bool = False,
) -> Path:
    if isinstance(request, Request):
        root_model = RequestRoot(root=request)
    else:
        root_model = RequestGroupRoot(root=request)
    if file_format == "json":
        output = root_model.model_dump_json(indent=2)
    elif file_format == "yaml":
        json_compatible_dict = root_model.model_dump(mode="json")
        output = safe_dump(json_compatible_dict, sort_keys=False)
    else:
        raise ValueError(f"Unsupported format: {file_format}")
    saved = save_text_file(
        text=output,
        output_dir=output_directory,
        file_name=file_name,
        overwrite=overwrite,
    )
    return saved
