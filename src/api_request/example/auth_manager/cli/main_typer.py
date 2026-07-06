"""Main entry point for the ESI Auth Manager CLI.

NOTE: This is only used when the auth manager is run as a standalone application.
It is not used when the auth manager is used as a library by a third party,
or when the cli commands are run as part of a different cli program.

When used as part of another cli program, that program must ensure that the
AuthManagerSettings are properly initialized and placed in the typer context.obj under
the "esi-auth-manager-settings" key.

"""

import asyncio
import logging
from dataclasses import asdict

import typer

from .. import __app_name__, __version__
from ..logging_config import setup_logging
from ..settings import get_settings
from .characters import app as characters_app
from .credentials import app as credentials_app
from .helpers import config_async_http_client, config_http_client

logger = logging.getLogger(__name__)


def default_options(ctx: typer.Context):
    """Esi Auth Manager Command Line Interface.

    Insert pithy saying here
    """
    settings = get_settings()
    # Configure HTTP clients if not already set
    if settings.client_session is None:
        settings.client_session = config_http_client()
    if settings.async_client_session is None:
        settings.async_client_session = asyncio.run(config_async_http_client())
    setup_logging(log_dir=settings.logging_directory)
    ctx.obj = {"esi-auth-manager-settings": settings}
    logger.info(
        f"Starting {__app_name__} v{__version__} with settings: {asdict(settings)!r}"
    )


app = typer.Typer(
    no_args_is_help=True,
    callback=default_options,
    help="Manage ESI authentication credentials and tokens.",
)
app.add_typer(credentials_app)
app.add_typer(characters_app)
