"""These are requests that are made to the live API.

They are not run by default, but can be run with the `--runlive` flag.
"""

from uuid import uuid4

from api_request.request.models import Request

esi_status_request = Request(
    request_key=uuid4(),
    method="GET",
    url="https://esi.evetech.net/latest/status/",
    headers={"Accept": "application/json"},
    cache_key=uuid4(),  # A cache key only used for testing this request, not a real cache key\
    rate_key="esi-status-request",  # A rate key only used for testing this request, not a real rate key
)
"""This request demonstrates a simple GET request to the ESI status endpoint. 
    
    It is used to test the live request functionality of the API client.
    
    It can test the following:
    - The request is made successfully and returns a 200 status code.
    - The response is a valid JSON object.
    - The response contains the expected keys and values.
    - The request is cachable and can be retrieved from the cache.
    """
