"""Create preconfigured sync and async HTTP clients for Eve Auth Manager."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from httpx2 import AsyncClient, Client

from pfmsoft.api_request.settings import USER_AGENT


def config_http_client(user_agent: str = USER_AGENT) -> Client:
    """Create an HTTP client configured with the project User-Agent header.

    Args:
        user_agent: User-Agent header value to send with requests. Defaults to
            the project setting.

    Returns:
        Configured synchronous HTTP client.

    Note:
        The caller owns the returned client and must close it when finished.
    """
    return Client(headers={"User-Agent": user_agent})


async def config_async_http_client(user_agent: str = USER_AGENT) -> AsyncClient:
    """Create an async HTTP client configured with the project User-Agent header.

    Args:
        user_agent: User-Agent header value to send with requests. Defaults to
            the project setting.

    Returns:
        Configured asynchronous HTTP client.

    Note:
        The caller owns the returned client and must close it when finished.
    """
    return AsyncClient(headers={"User-Agent": user_agent})


@contextmanager
def client_manager(user_agent: str = USER_AGENT) -> Iterator[Client]:
    """Yield a configured HTTP client and close it automatically on exit.

    Args:
        user_agent: User-Agent header value to send with requests.

    Yields:
        Configured synchronous HTTP client.
    """
    client: Client | None = None
    try:
        client = config_http_client(user_agent)
        yield client
    finally:
        if client is not None:
            client.close()


@asynccontextmanager
async def async_client_manager(
    user_agent: str = USER_AGENT,
) -> AsyncIterator[AsyncClient]:
    """Yield a configured async HTTP client and close it automatically on exit.

    Args:
        user_agent: User-Agent header value to send with requests.

    Yields:
        Configured asynchronous HTTP client.
    """
    client: AsyncClient | None = None
    try:
        client = await config_async_http_client(user_agent)
        yield client
    finally:
        if client is not None:
            await client.aclose()
