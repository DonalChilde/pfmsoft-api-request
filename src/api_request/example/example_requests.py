"""Example requests for testing and documentation purposes."""

from uuid import uuid4

from esi_link.request.models import Request, RequestGroup

# TODO: More examples.
#   - Example of query parameters.
#   - Example of a paged request, with query parameters.
#   - Example of a request with a JSON body. - Post request.
#   - Example of a failed validation request, with validation errors.
#   - Example of a failed runtime request. NOTE include warning not to spam server with failures.


def api_status() -> Request:
    """Example request for the EVE ESI api status endpoint."""
    return Request(
        request_id=uuid4(),
        operation_id="GetMetaStatus",
        description="Example request for the EVE ESI api status endpoint.",
    )


def server_status() -> Request:
    """Example request for the EVE ESI server status endpoint."""
    return Request(
        request_id=uuid4(),
        operation_id="GetStatus",
        description="Example request for the EVE ESI server status endpoint.",
    )


def status_group() -> RequestGroup:
    """Example request group for the EVE ESI status endpoints."""
    api_status_request = api_status()
    server_status_request = server_status()
    return RequestGroup(
        group_id=uuid4(),
        description="Example request group for the EVE ESI status endpoints.",
        requests={
            api_status_request.request_id: api_status_request,
            server_status_request.request_id: server_status_request,
        },
    )


def character_attributes(character_id: int) -> Request:
    """Example request for the EVE ESI character attributes endpoint."""
    return Request(
        request_id=uuid4(),
        operation_id="GetCharactersCharacterIdAttributes",
        description=f"Example request for the EVE ESI character attributes endpoint for "
        f"character ID {character_id}. Showing the use of an authorized request with path parameters.",
        path_parameters={"character_id": character_id},
        authorization_id=character_id,
    )


def universe_types() -> Request:
    """Example request for the EVE ESI universe types endpoint."""
    return Request(
        request_id=uuid4(),
        operation_id="GetUniverseTypes",
        description="Example request for the EVE ESI universe types endpoint, showing the use of query parameters and paged requests.",
        query_parameters={"page": 1},
    )
