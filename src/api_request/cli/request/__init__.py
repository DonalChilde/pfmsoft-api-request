"""Commands for working with requests."""

import typer

from .request import app as request_app
from .validate import app as validate_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(request_app)
app.add_typer(validate_app)
