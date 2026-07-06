"""Authentication-related CLI commands."""

import typer

from esi_link.cli.auth.add_token import app as add_token_app
from esi_link.cli.auth.credentials import app as credentials_app
from esi_link.cli.auth.list_tokens import app as list_tokens_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(
    credentials_app, help="Initialize the authentication store.", name="credentials"
)
app.add_typer(add_token_app, help="Add a token for a character.")
app.add_typer(list_tokens_app, help="List all available tokens.")
