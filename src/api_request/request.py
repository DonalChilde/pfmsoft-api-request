"""API request context manager."""

from types import TracebackType
from typing import Self

from httpx2 import AsyncClient

from api_request.helpers.http_session_factory import config_async_http_client


class ApiRequest:
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
