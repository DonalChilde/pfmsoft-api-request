# validate a request or request group file without sending it. This is useful for checking that the file is well-formed and that all required fields are present.
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def validate(
    ctx: typer.Context,
    request_file: Annotated[
        Path,
        typer.Argument(
            help="The path to the request file to validate. This should be a JSON or YAML file containing either a Request or RequestGroup object.",
            file_okay=True,
            dir_okay=False,
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Validate a request or request group file without sending it. This is useful for checking that the file is well-formed and that all required fields are present."""
