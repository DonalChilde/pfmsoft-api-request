"""Callback functions for the ESI Link CLI."""

import logging
from dataclasses import asdict

import typer

from esi_link import __app_name__, __version__
from esi_link.logging_config import setup_logging
from esi_link.settings import get_settings

logger = logging.getLogger(__name__)


def default_options(ctx: typer.Context):
    """Esi Link Command Line Interface.

    Insert pithy saying here
    """
    settings = get_settings()
    setup_logging(log_dir=settings.log_directory)
    ctx.obj = {"esi-link-settings": settings}
    logger.info(
        f"Starting {__app_name__} v{__version__} with settings: {asdict(settings)!r}"
    )
