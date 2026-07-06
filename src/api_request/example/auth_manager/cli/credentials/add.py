"""CLI command to add credentials to the auth manager."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ...models import EsiAppCredentialsRoot
from ...sqlite.manager import SqliteAuthManager
from ..helpers import get_auth_manager_settings_from_context, get_stdin

app = typer.Typer(
    no_args_is_help=True, name="credentials", help="Manage ESI app credentials."
)


@app.command(name="add")
def add_credentials(
    ctx: typer.Context,
    credentials_file: Annotated[
        Path,
        typer.Option(
            "--from",
            help="Path to the credentials file. Use '-' to read from stdin.",
            file_okay=True,
            dir_okay=False,
            readable=True,
            allow_dash=True,
        ),
    ] = Path("-"),
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            help="Suppress output messages.",
        ),
    ] = False,
) -> None:
    """Add credentials.

    Fails if credentials already exist.
    """
    if credentials_file == Path("-"):
        quiet = True  # Force quiet mode when reading from stdin
    if quiet:
        messenger = Console(stderr=True, quiet=True)
    else:
        messenger = Console(stderr=True)
    settings = get_auth_manager_settings_from_context(ctx)
    if credentials_file == Path("-"):
        creds_text = get_stdin()
    else:
        messenger.print(f"Loading credentials from {credentials_file}...")
        creds_text = credentials_file.read_text()
    credentials = EsiAppCredentialsRoot.model_validate_json(creds_text).root
    with SqliteAuthManager(settings.auth_db_path) as auth_manager:
        cred_id = auth_manager.add_credentials(credentials)
    messenger.print(f"Credentials added successfully with ID: {cred_id}")
