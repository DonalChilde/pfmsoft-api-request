"""Request-related commands for the CLI."""

import typer

from esi_link.cli.request.outline import app as outline_app
from esi_link.cli.request.samples import app as samples_app
from esi_link.cli.request.send import app as send_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(samples_app, help="Commands for saving example requests to disk.")
app.add_typer(send_app, help="Commands for sending requests from JSON files.")
app.add_typer(outline_app, help="Commands for generating request outlines.")
