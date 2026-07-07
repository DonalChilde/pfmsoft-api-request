"""api-request: A command line first interface to the Eve Online API."""

__author__ = "Chad Lowe"
__email__ = "pfmsoft.dev@gmail.com"
__app_name__ = "api-request"
"""Name of this module is defined here for consitency, used in determining the app_dir 
and other paths."""
#######################################################################################
# Update in pyproject.toml, as uv build backend does not yet support dynamic metadata #
# https://github.com/astral-sh/uv/issues/11718                                        #
#######################################################################################
__description__ = "A command line first interface to the Eve Online API"
__version__ = "0.1.0"
__release__ = __version__
#######################################################################################=
__url__ = "https://github.com/DonalChilde/api-request"
__license__ = "MIT"

from .request.api_requester import ApiRequester
from .request.models import Request, Response

__all__ = ["ApiRequester", "Request", "Response"]
