"""Settings for the api-request module."""

from api_request import __app_name__, __url__, __version__

USER_AGENT = f"{__app_name__} ({__version__}) (+{__url__})"
