"""A sqlite3 based cache provider with factory function for use with ApiRequester."""

import sqlite3

from api_request.helpers import json_io

from ..protocols import CacheFactoryProtocol, CacheProtocol
