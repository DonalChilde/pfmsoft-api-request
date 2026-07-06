"""Helper functions for working with ESI Oauth tokens."""

import logging
from collections.abc import Sequence
from typing import Any

from httpx2 import AsyncClient, Client, HTTPError
from jwt import ExpiredSignatureError, PyJWKClient, decode, get_unverified_header

logger = logging.getLogger(__name__)


class TokenValidationError(Exception):
    def __init__(self, *args: Any) -> None:
        """Custom exception for token validation errors."""
        super().__init__(*args)


class NewTokenRequestError(Exception):
    def __init__(self, *args: Any) -> None:
        """Custom exception for errors during new token requests."""
        super().__init__(*args)


class TokenRefreshError(Exception):
    def __init__(self, *args: Any) -> None:
        """Custom exception for errors during token refresh."""
        super().__init__(*args)


class TokenRevocationError(Exception):
    def __init__(self, *args: Any) -> None:
        """Custom exception for errors during token revocation."""
        super().__init__(*args)


class DecodeTokenError(Exception):
    def __init__(self, *args: Any) -> None:
        """Custom exception for errors during token decoding."""
        super().__init__(*args)


def request_token(
    client_id: str,
    authorization_code: str,
    code_verifier: str,
    token_endpoint: str,
    session: Client,
) -> dict[str, Any]:
    """Takes an authorization code and code verifier and exchanges it for an access token and refresh token."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    try:
        response = session.post(token_endpoint, headers=headers, data=payload)
        response.raise_for_status()
        result = response.json()
    except HTTPError as e:
        logger.error(f"HTTP error during token request: {e}")
        raise NewTokenRequestError(f"HTTP error during token request: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during token request: {e}")
        raise NewTokenRequestError(f"Unexpected error during token request: {e}") from e

    return result


def refresh_token(
    refresh_token: str,
    client_id: str,
    token_endpoint: str,
    session: Client,
) -> dict[str, Any]:
    """Takes a refresh token and exchanges it for a new oauth token."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload: dict[str, str] = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        response = session.post(token_endpoint, headers=headers, data=payload)
        response.raise_for_status()
        result = response.json()
    except HTTPError as e:
        logger.error(f"HTTP error during token refresh: {e}")
        raise TokenRefreshError(f"HTTP error during token refresh: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}")
        raise TokenRefreshError(f"Unexpected error during token refresh: {e}") from e
    return result


def revoke_refresh_token(
    refresh_token: str,
    revocation_endpoint: str,
    client_id: str,
    session: Client,
) -> Any:
    """Revoke a refresh token.

    Im not sure how to tell for sure if the refresh token got revoked, except to test a
    refresh after revocation and see if it fails. The SSO returns a 200 OK response even
    if the token is invalid or already revoked, so we have to rely on testing the token
    after revocation to confirm it worked.
    """
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload: dict[str, str] = {
        "token": refresh_token,
        "token_type_hint": "refresh_token",
        "client_id": client_id,
    }
    try:
        response = session.post(revocation_endpoint, headers=headers, data=payload)
        response.raise_for_status()
        return response.json()
    except HTTPError as e:
        logger.error(f"HTTP error during token revocation: {e}")
        raise TokenRevocationError(f"HTTP error during token revocation: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during token revocation: {e}")
        raise TokenRevocationError(
            f"Unexpected error during token revocation: {e}"
        ) from e


async def async_request_token(
    client_id: str,
    authorization_code: str,
    code_verifier: str,
    token_endpoint: str,
    session: AsyncClient,
) -> dict[str, Any]:
    """Takes an authorization code and code verifier and exchanges it for an access token and refresh token.

    Args:
        client_id: The client ID of the application.
        authorization_code: The authorization code received from the SSO.
        code_verifier: The code verifier used to generate the code challenge, as generated by `generate_code_challenge`.
        token_endpoint: The token endpoint URI for exchanging the authorization code.
        session: The httpx2.AsyncClient session for making requests.

    Returns:
        A dictionary containing the access token and refresh token.

    Raises:
        ValueError: If session is not initialized.
        httpx2.HTTPStatusError: If the token request fails.
    """
    if not session:
        raise ValueError("session must be initialized to request token.")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    try:
        response = await session.post(token_endpoint, headers=headers, data=payload)
        response.raise_for_status()
        result = await response.json()
    except HTTPError as e:
        logger.error(f"HTTP error during async token request: {e}")
        raise NewTokenRequestError(f"HTTP error during async token request: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during async token request: {e}")
        raise NewTokenRequestError(
            f"Unexpected error during async token request: {e}"
        ) from e

    return result


async def async_refresh_token(
    refresh_token: str,
    client_id: str,
    token_endpoint: str,
    session: AsyncClient,
) -> dict[str, Any]:
    """Takes a refresh token and exchanges it for a new oauth token.

    Args:
        refresh_token: The refresh token portion of the OAuth2 token.
        client_id: The client ID of the application.
        token_endpoint: The token endpoint URI for refreshing tokens.
        session: The httpx2.AsyncClient session for making requests.

    Returns:
        A dictionary containing the new access token and refresh token.

    Raises:
        ValueError: If session is not initialized.
        httpx2.HTTPStatusError: If the token request fails.
    """
    if not session:
        raise ValueError("session must be initialized to refresh token.")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload: dict[str, str] = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        response = await session.post(token_endpoint, headers=headers, data=payload)
        response.raise_for_status()
        result = await response.json()
    except HTTPError as e:
        logger.error(f"HTTP error during async token refresh: {e}")
        raise TokenRefreshError(f"HTTP error during async token refresh: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during async token refresh: {e}")
        raise TokenRefreshError(
            f"Unexpected error during async token refresh: {e}"
        ) from e
    return result


async def async_revoke_refresh_token(
    refresh_token: str,
    revocation_endpoint: str,
    client_id: str,
    session: AsyncClient,
) -> Any:
    """Revoke a refresh token.

    Im not sure how to tell for sure if the refresh token got revoked, except to test a
    refresh after revocation and see if it fails. The SSO returns a 200 OK response even
    if the token is invalid or already revoked, so we have to rely on testing the token
    after revocation to confirm it worked.

    Args:
        refresh_token: The refresh token to revoke.
        revocation_endpoint: The revocation endpoint URI.
        client_id: The client ID of the application.
        session: The httpx2.AsyncClient session for making requests.

    Raises:
        httpx2.HTTPStatusError: If the revocation request fails.
    """
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload: dict[str, str] = {
        "token": refresh_token,
        "token_type_hint": "refresh_token",
        "client_id": client_id,
    }

    try:
        response = await session.post(
            revocation_endpoint, headers=headers, data=payload
        )
        response.raise_for_status()
        if response.status_code == 200:
            logger.info("Token revoked successfully")
    except HTTPError as e:
        logger.error(f"HTTP error during async token revocation: {e}")
        raise TokenRevocationError(
            f"HTTP error during async token revocation: {e}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error during async token revocation: {e}")
        raise TokenRevocationError(
            f"Unexpected error during async token revocation: {e}"
        ) from e


def validate_jwt_token(
    access_token: str,
    jwks_client: PyJWKClient | None,
    audience: str,
    issuers: Sequence[str],
    user_agent: str | None = None,
    jwks_uri: str | None = None,
) -> dict[str, Any]:
    """Validates and decodes a JWT Token.

    Args:
        access_token: The JWT token to validate.

        jwks_client: An optional PyJWKClient instance to use for fetching keys.
            If None, a new client will be created.
        audience: Expected audience for the token.
        issuers: Valid issuers for the token.
        user_agent: The User-Agent string to use in requests.
        jwks_uri: The JWKS URI to fetch signing keys from. Required if jwks_client is None.

    Returns:
        The content of the validated JWT access token.

    Raises:
        ValueError: If jwks_uri is not provided when jwks_client is None.
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is invalid.
        Exception: If any other error occurs.
    """
    # NOTE the jwks_client can cache the keys, so we dont have to fetch them every time.
    # Pass in a jwks_client if you have one.

    if jwks_client is None:
        headers = {"User-Agent": user_agent or "Token validation without User-Agent"}
        if not jwks_uri:
            raise ValueError("jwks_uri must be provided if jwks_client is None")
        if not user_agent:
            logger.warning(
                "User-Agent is empty when fetching JWKS keys with PyJWKClient. It's recommended to provide a User-Agent string when fetching JWKS keys."
            )
        jwks_client = PyJWKClient(jwks_uri, headers=headers)
    unverified_header = get_unverified_header(access_token)
    kid = unverified_header["kid"]
    alg = unverified_header["alg"]
    signing_key = jwks_client.get_signing_key(kid).key
    try:
        # Decode and validate the token
        valid_decoded_token = decode(
            jwt=access_token,
            key=signing_key,
            algorithms=[alg],
            audience=audience,
            issuer=issuers,
            options={"verify_aud": True, "verify_iss": True},
        )

        return valid_decoded_token
    except ExpiredSignatureError as e:
        logger.error("Token has expired")
        raise DecodeTokenError(f"Token has expired. {e}") from e
    except Exception as e:
        logger.error(f"Invalid token or other error: {e}")
        raise DecodeTokenError(f"Invalid token or other error: {e}") from e
