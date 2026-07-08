"""Main entry point for the api-request CLI."""

from dataclasses import asdict

import typer

from api_request import __app_name__, __version__
from api_request.logging_config import setup_logging
from api_request.settings import get_settings

app = typer.Typer(
    name="api-request",
    help="A command-line tool for managing API requests.",
    no_args_is_help=True,
)
import logging

logger = logging.getLogger(__name__)


def default_options(ctx: typer.Context) -> None:
    """Initialize settings and logging for standalone CLI execution.

    Args:
        ctx: Typer command context used to store shared application settings
            for downstream subcommands.

    Notes:
        The resolved EveAuthManagerSettings object is stored in ctx.obj under
        the eve-auth-manager-settings key.
    """
    settings = get_settings()
    setup_logging(log_dir=settings.logging_directory)
    ctx.obj = {"api-request-settings": settings}
    logger.info(
        f"Starting {__app_name__} v{__version__} with settings: {asdict(settings)!r}"
    )
