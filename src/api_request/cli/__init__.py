"""CLI command modules for api-request.

This package contains Typer applications and helper functions used by the
`eve-auth`/`api-request` command-line entrypoints.
"""

import typer

from .cache import app as cache_app
from .request import app as request_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(
    cache_app, name="cache", help="Commands for working with the cache database."
)
app.add_typer(request_app, name="request", help="Commands for making API requests.")
