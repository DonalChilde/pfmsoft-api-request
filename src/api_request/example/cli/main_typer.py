"""Main entry point for the Esi Link CLI using Typer."""

import typer

from esi_link.cli.auth import app as auth_app
from esi_link.cli.callback import default_options
from esi_link.cli.request import app as request_app
from esi_link.cli.schema import app as schema_app

app = typer.Typer(
    no_args_is_help=True,
    callback=default_options,
    help="Esi Link Command Line Interface.",
)
app.add_typer(auth_app, name="auth", help="Authentication-related commands.")
app.add_typer(schema_app, name="schema", help="ESI schema-related commands.")
app.add_typer(request_app, name="request", help="Request-related commands.")
