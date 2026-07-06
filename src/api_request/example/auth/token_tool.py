"""Tools for managing ESI Oauth tokens."""

import logging
from typing import Any

from httpx2 import AsyncClient, Client
from jwt.jwks_client import PyJWKClient

from esi_link import USER_AGENT
from esi_link.auth.helpers import oauth_tokens as oauth_helpers
from esi_link.auth.models import (
    AUDIENCE,
    CharacterToken,
    OAuthMetadataTimestamped,
    OauthToken,
    ValidatedToken,
)
from esi_link.helpers.http_client import config_async_http_client, config_http_client

logger = logging.getLogger(__name__)


class TokenTool:
    """Tool for managing ESI Oauth tokens."""

    def __init__(
        self,
        oauth_metadata: OAuthMetadataTimestamped,
        *,
        session: Client | None = None,
        async_session: AsyncClient | None = None,
    ) -> None:
        """Initialize the TokenTool."""
        self._oauth_metadata = oauth_metadata
        self._jwks_client = PyJWKClient(
            self._oauth_metadata.jwks_uri, headers={"User-Agent": USER_AGENT}
        )
        if session is None:
            self._session = config_http_client()
        else:
            self._session = session
        self._async_session = async_session

    def request_new_token(
        self,
        client_id: str,
        authorization_code: str,
        code_verifier: str,
    ) -> OauthToken:
        """Request a new token using the authorization code flow."""
        token_response = oauth_helpers.request_token(
            client_id=client_id,
            authorization_code=authorization_code,
            code_verifier=code_verifier,
            token_endpoint=self._oauth_metadata.token_endpoint,
            session=self._session,
        )
        return OauthToken(token_data=token_response)

    async def async_request_new_token(
        self,
        client_id: str,
        authorization_code: str,
        code_verifier: str,
    ) -> OauthToken:
        """Asynchronously request a new token using the authorization code flow."""
        if self._async_session is None:
            self._async_session = await config_async_http_client()
        token_response = await oauth_helpers.async_request_token(
            client_id=client_id,
            authorization_code=authorization_code,
            code_verifier=code_verifier,
            token_endpoint=self._oauth_metadata.token_endpoint,
            session=self._async_session,
        )
        return OauthToken(token_data=token_response)

    def refresh_existing_token(
        self,
        refresh_token: str,
        client_id: str,
    ) -> OauthToken:
        """Refresh an existing token using the refresh token."""
        token_response = oauth_helpers.refresh_token(
            refresh_token=refresh_token,
            client_id=client_id,
            token_endpoint=self._oauth_metadata.token_endpoint,
            session=self._session,
        )
        return OauthToken(token_data=token_response)

    async def async_refresh_existing_token(
        self,
        refresh_token: str,
        client_id: str,
    ) -> OauthToken:
        """Asynchronously refresh an existing token using the refresh token."""
        if self._async_session is None:
            self._async_session = await config_async_http_client()
        token_response = await oauth_helpers.async_refresh_token(
            refresh_token=refresh_token,
            client_id=client_id,
            token_endpoint=self._oauth_metadata.token_endpoint,
            session=self._async_session,
        )
        return OauthToken(token_data=token_response)

    def revoke_refresh_token(
        self,
        refresh_token: str,
        client_id: str,
    ) -> Any:
        """Revoke a refresh token."""
        return oauth_helpers.revoke_refresh_token(
            refresh_token=refresh_token,
            revocation_endpoint=self._oauth_metadata.revocation_endpoint,
            client_id=client_id,
            session=self._session,
        )

    def validate_token(self, access_token: str) -> ValidatedToken:
        """Validate an access token and return the decoded token data if valid."""
        validated_token_data = oauth_helpers.validate_jwt_token(
            access_token=access_token,
            audience=AUDIENCE,
            jwks_client=self._jwks_client,
            issuers=self._oauth_metadata.issuers,
        )
        return ValidatedToken(token_data=validated_token_data)

    def create_character_token(self, oauth_token: OauthToken) -> CharacterToken:
        """Create a CharacterToken from an OauthToken by validating it and extracting character info."""
        validated_token = self.validate_token(oauth_token.access_token)
        return CharacterToken(
            oauth_token=oauth_token,
            character_id=validated_token.character_id,
            character_name=validated_token.character_name,
            # created=validated_token.issued_at,
            expires_at=validated_token.expires_at,
        )
