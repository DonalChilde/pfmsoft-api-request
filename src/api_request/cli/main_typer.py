"""Main entry point for the api-request CLI.

NOTE: This is not currently the entry point, as so far there is only one command.
If additional commands are added, this module will be the entry point and will
dispatch to subcommands.
"""

import logging
from dataclasses import asdict

import typer

from api_request import __app_name__, __version__
from api_request.cli import app as api_request_app
from api_request.cli.helpers import get_api_request_settings_from_context
from api_request.logging_config import setup_logging
from api_request.settings import SETTINGS_KEY, get_settings

logger = logging.getLogger(__name__)


def default_options(ctx: typer.Context) -> None:
    """Initialize settings and logging for standalone CLI execution.

    Args:
        ctx: Typer command context used to store shared application settings
            for downstream subcommands.

    Notes:
        The resolved ApiRequestSettings object is stored in ctx.obj under the
        `api-request-settings` key.
    """
    settings = get_settings()
    setup_logging(log_dir=settings.logging_directory)
    ctx.obj = {SETTINGS_KEY: settings}
    logger.info(
        f"Starting {__app_name__} v{__version__} with settings: {asdict(settings)!r}"
    )


app = typer.Typer(callback=default_options, no_args_is_help=True)


@app.command()
def version(ctx: typer.Context) -> None:
    """Print the version of the api-request CLI."""
    settings = get_api_request_settings_from_context(ctx)
    typer.echo(f"{__app_name__} v{__version__}")
    typer.echo(f"Settings: {asdict(settings)!r}")


app.add_typer(api_request_app)
