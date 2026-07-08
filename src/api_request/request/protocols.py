"""Protocols module for API requests."""

from typing import Protocol

from api_request.request.models import (
    Requests,
    Responses,
)


class ApiRequesterProtocol(Protocol):
    async def process_requests(
        self,
        requests: Requests,
    ) -> Responses:
        """Process a batch of API requests and return their corresponding cached responses."""
        ...
