from contextlib import AsyncExitStack
from types import TracebackType

from esi_link.app_data.app_data import AppDataSqlite
from esi_link.auth.token_tool import TokenTool
from esi_link.helpers.http_client import config_async_http_client, config_http_client
from esi_link.helpers.settings_factories import app_data_db_uri_factory
from esi_link.request.models import Request, RequestGroup
from esi_link.request_dispatch_esi_link import (
    dispatch_request,
    dispatch_request_group,
)
from esi_link.response.models import ResponseDebugGroup, ResponseGroup
from esi_link.settings import EsiLinkSettings
from httpx2 import AsyncClient, Client


class EsiLink:
    def __init__(self, settings: EsiLinkSettings):
        self._settings = settings
        self._session: Client | None = None
        self._async_session: AsyncClient | None = None
        self._stack = AsyncExitStack()
        # instance resources
        self._app_data: AppDataSqlite | None = None

    async def __aenter__(self):
        """Initialize resources for the EsiLink instance, including HTTP sessions and app data context."""
        # Initialize resources here if needed
        self._session = self._stack.enter_context(config_http_client())
        self._async_session = await self._stack.enter_async_context(
            await config_async_http_client()
        )
        self._app_data = await self._stack.enter_async_context(
            AppDataSqlite(
                db_uri=app_data_db_uri_factory(self._settings),
                session=self._session,
                async_session=self._async_session,
            )
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Clean up resources by closing sessions and the app data context."""
        self._session = None
        self._async_session = None
        self._app_data = None
        # This automatically calls __exit__ on all contained context managers
        # and forwards any exceptions correctly
        return await self._stack.__aexit__(exc_type, exc_value, traceback)

    async def send_request(
        self, request: Request
    ) -> tuple[ResponseGroup, ResponseDebugGroup | None]:
        if not self._session or not self._async_session:
            raise ValueError(
                "EsiLink instance must be used as an async context manager to send requests."
            )
        if self._app_data is None:
            raise RuntimeError("App data context is not initialized.")

        return await dispatch_request(
            request=request,
            schema_cache=self._app_data.schema_cache,
            web_cache=self._app_data.web_cache,
            date_cache=self._app_data.compatibility_dates_cache,
            async_session=self._async_session,
            token_store=self._app_data.token_manager,
        )

    async def send_request_group(
        self, request_group: RequestGroup
    ) -> tuple[ResponseGroup, ResponseDebugGroup | None]:
        if not self._session or not self._async_session:
            raise ValueError(
                "EsiLink instance must be used as an async context manager to send requests."
            )
        if self._app_data is None:
            raise RuntimeError("App data context is not initialized.")

        return await dispatch_request_group(
            request_group=request_group,
            schema_cache=self._app_data.schema_cache,
            web_cache=self._app_data.web_cache,
            date_cache=self._app_data.compatibility_dates_cache,
            async_session=self._async_session,
            token_store=self._app_data.token_manager,
        )

    @property
    def app_data(self) -> AppDataSqlite:
        """Get the app data context manager, which provides access to cached OAuth metadata, credentials, and schema cache."""
        if self._app_data is None:
            raise RuntimeError("App data context is not initialized.")
        return self._app_data

    @property
    def token_tool(self) -> TokenTool:
        """Get the token tool for managing OAuth tokens."""
        if self._app_data is None:
            raise RuntimeError("App data context is not initialized.")
        oauth_metadata = self._app_data.oauth_metadata
        token_tool = TokenTool(
            oauth_metadata, session=self._session, async_session=self._async_session
        )
        return token_tool
