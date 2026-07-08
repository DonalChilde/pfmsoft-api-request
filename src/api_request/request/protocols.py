"""Protocols module for API requests."""

from collections.abc import Hashable
from typing import Protocol

from api_request.request.models import (
    Requests,
    Responses,
)


class ApiRequesterProtocol[T: Hashable](Protocol):
    async def process_requests(
        self,
        requests: Requests[T],
    ) -> Responses[T]:
        """Process a batch of API requests and return their corresponding cached responses."""
        ...
