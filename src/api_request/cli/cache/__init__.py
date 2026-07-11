"""Commands for working with the cache database."""

import typer

from .info import app as info_app

app = typer.Typer(
    no_args_is_help=True,
    name="cache",
    help="Commands for working with the cache database.",
)
app.add_typer(info_app)
