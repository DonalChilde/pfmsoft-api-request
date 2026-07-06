"""API request context manager."""

from types import TracebackType
from typing import Self
from uuid import UUID

from httpx2 import AsyncClient

from api_request.helpers.http_session_factory import config_async_http_client
from api_request.models import FailedResponse, Request, Response
from api_request.protocols import ApiRequestProtocol


class ApiRequest(ApiRequestProtocol):
    def __init__(self) -> None:
        self._client: AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = await config_async_http_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def process_requests(
        self,
        requests: dict[UUID, Request],
    ) -> dict[UUID, Response | FailedResponse]:
        """Process a batch of API requests and return their corresponding cached responses."""
        if self._client is None:
            raise RuntimeError(
                "HTTP client is not initialized. Use 'async with ApiRequest()' to initialize."
            )
        responses: dict[UUID, Response | FailedResponse] = {}

        return responses
