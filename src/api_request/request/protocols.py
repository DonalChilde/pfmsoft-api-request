"""Protocols module for API requests."""

from collections.abc import Hashable
from typing import Protocol
from uuid import UUID

from api_request.request.models import FailedResponse, Request, Response


class ApiRequesterProtocol[T: Hashable](Protocol):
    async def process_requests(
        self,
        requests: dict[UUID, Request[T]],
    ) -> dict[UUID, Response[T] | FailedResponse[T]]:
        """Process a batch of API requests and return their corresponding cached responses."""
        ...
