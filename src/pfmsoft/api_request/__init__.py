"""api-request: A command line first interface to the Eve Online API."""

from importlib.metadata import version

__project_namespace__ = "pfmsoft"
__author__ = "Chad Lowe"
__email__ = "pfmsoft.dev@gmail.com"
__app_name__ = "pfmsoft-api-request"
"""Name of this module is defined here for consitency, used in determining the app_dir 
and other paths."""
__description__ = "A command line first interface to the Eve Online API"
__version__ = version(__app_name__)
__release__ = __version__
__url__ = "https://github.com/DonalChilde/pfmsoft-api-request"
__license__ = "MIT"

from .request.api_requester import ApiRequester
from .request.models import (
    FailedResponse,
    Request,
    Requests,
    Response,
    ResponseMetadata,
    Responses,
    Source,
)

__all__ = [
    "ApiRequester",
    "FailedResponse",
    "Request",
    "Requests",
    "Response",
    "ResponseMetadata",
    "Responses",
    "Source",
]
