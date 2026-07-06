"""Helper functions for requesting an OAuth token for ESI API access."""

import json
import logging
import sys
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from esi_link.auth.helpers.code_challenge import (
    generate_code_challenge_and_verifier,
)
from esi_link.auth.helpers.oauth_tokens import request_token
from esi_link.auth.helpers.secure_random_string import (
    generate_secure_random_string,
)
from esi_link.auth.models import EsiAppCredentials

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class AuthenticationRequestParams:
    redirect_url: str
    """URL to redirect the user to for authentication."""
    state: str
    """CSRF protection string to validate the callback."""
    code_verifier: str
    """Code verifier for PKCE."""
    code_challenge: str
    """Code challenge for PKCE."""


def generate_url(
    code_challenge: str,
    client_id: str,
    callback_url: str,
    authorization_endpoint: str,
    scopes: list[str],
    state: str,
    code_challenge_method: str = "S256",
) -> str:
    """Generate the URL.

    The URL for the user to visit to authorize the application.
    """
    query_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback_url,
        "scope": " ".join(scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }
    query_string = urlencode(query_params)
    return f"{authorization_endpoint}?{query_string}"


def generate_request_params(
    client_id: str, callback_url: str, authorization_endpoint: str, scopes: list[str]
) -> AuthenticationRequestParams:
    """Generate the request parameters for the authentication request."""
    pkce_codes = generate_code_challenge_and_verifier()
    state = generate_secure_random_string(16)
    return AuthenticationRequestParams(
        redirect_url=generate_url(
            code_challenge=pkce_codes.code_challenge,
            client_id=client_id,
            callback_url=callback_url,
            authorization_endpoint=authorization_endpoint,
            scopes=scopes,
            state=state,
        ),
        state=state,
        code_verifier=pkce_codes.code_verifier,
        code_challenge=pkce_codes.code_challenge,
    )


def start_web_server_and_listen_for_code(
    redirect_url: str,
    expected_state: str,
    timeout_seconds: int = 300,
) -> str:
    """Listen for the OAuth callback and return the authorization code.

    The HTTP server runs on a background thread and this function blocks until the
    callback is received, an error occurs, or timeout is reached.
    """
    parsed_callback = urlparse(redirect_url)
    if not parsed_callback.hostname:
        raise ValueError("redirect_url must include a hostname")

    callback_host = parsed_callback.hostname
    callback_port = parsed_callback.port
    if callback_port is None:
        callback_port = 443 if parsed_callback.scheme == "https" else 80
    callback_path = parsed_callback.path or "/"

    result: dict[str, str | None] = {"code": None, "error": None}
    callback_received = threading.Event()

    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_html(self, status_code: int, body: str) -> None:
            encoded_body = body.encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded_body)))
            self.end_headers()
            self.wfile.write(encoded_body)

        def do_GET(self) -> None:
            parsed_request = urlparse(self.path)
            if parsed_request.path != callback_path:
                self._send_html(404, "<h1>Not Found</h1>")
                return

            query_params = parse_qs(parsed_request.query)
            oauth_error = query_params.get("error", [None])[0]
            oauth_error_description = query_params.get("error_description", [None])[0]
            callback_state = query_params.get("state", [None])[0]
            authorization_code = query_params.get("code", [None])[0]

            if oauth_error:
                description = oauth_error_description or "No description provided"
                result["error"] = (
                    f"OAuth authorization failed: {oauth_error} ({description})"
                )
                self._send_html(
                    400,
                    "<h1>Authorization Failed</h1><p>You can close this window and return to the terminal.</p>",
                )
                callback_received.set()
                return

            if not callback_state:
                result["error"] = "Missing state in callback query parameters"
                self._send_html(
                    400,
                    "<h1>Invalid Callback</h1><p>Missing state. You can close this window.</p>",
                )
                callback_received.set()
                return

            if callback_state != expected_state:
                result["error"] = "State mismatch in OAuth callback"
                self._send_html(
                    400,
                    "<h1>Invalid Callback</h1><p>State mismatch. You can close this window.</p>",
                )
                callback_received.set()
                return

            if not authorization_code:
                result["error"] = (
                    "Missing authorization code in callback query parameters"
                )
                self._send_html(
                    400,
                    "<h1>Invalid Callback</h1><p>Missing authorization code. You can close this window.</p>",
                )
                callback_received.set()
                return

            result["code"] = authorization_code
            self._send_html(
                200,
                "<h1>Authorization Complete</h1><p>You can close this window and return to the terminal.</p>",
            )
            callback_received.set()

    server = HTTPServer((callback_host, callback_port), OAuthCallbackHandler)
    server_thread = threading.Thread(
        target=server.serve_forever,
        name="oauth-callback-server",
        kwargs={"poll_interval": 0.2},
    )
    server_thread.start()

    try:
        if not callback_received.wait(timeout=timeout_seconds):
            raise TimeoutError(
                f"Timed out after {timeout_seconds} seconds waiting for OAuth callback"
            )

        if result["error"]:
            raise ValueError(result["error"])

        if not result["code"]:
            raise RuntimeError("OAuth callback completed without an authorization code")

        return result["code"]
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)


if __name__ == "__main__":
    import argparse

    import httpx2

    METADATA_ENDPOINT = (
        "https://login.eveonline.com/.well-known/oauth-authorization-server"
    )
    AUTHORIZATION_ENDPOINT = "https://login.eveonline.com/v2/oauth/authorize"
    TOKEN_ENDPOINT = "https://login.eveonline.com/v2/oauth/token"
    USER_AGENT = "esi-examples/0.1"

    parser = argparse.ArgumentParser(
        description="Get Authorization code for ESI API Oauth Token."
    )
    parser.add_argument(
        "infile",
        nargs="?",
        default=None,
        help="input app credential file or '-' for stdin (default: stdin)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="The output YAML file to save the authorization code to (default: stdout)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="The number of spaces to use for indentation in the JSON output (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Seconds to wait for the OAuth callback before failing (default: %(default)s)",
    )
    args = parser.parse_args()

    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than 0")

    # Read JSON input, either from file or stdin ('-' means stdin)
    if args.infile and args.infile != "-":
        input_path = Path(args.infile)
        with input_path.open("r", encoding="utf-8") as f:
            json_input = f.read()
    else:
        json_input = sys.stdin.read()

    # Convert JSON to credential model
    credentials = EsiAppCredentials(**json.loads(json_input))
    auth_request_params = generate_request_params(
        client_id=credentials.clientId,
        callback_url=credentials.callbackUrl,
        authorization_endpoint=AUTHORIZATION_ENDPOINT,
        scopes=credentials.scopes,
    )

    writing_to_file = args.output_file is not None

    opened = webbrowser.open(auth_request_params.redirect_url)
    if writing_to_file:
        if opened:
            print("Opened browser for authorization.")
        else:
            print("Could not automatically open browser. Visit this URL to continue:")
            print(auth_request_params.redirect_url)
    elif not opened:
        print(
            f"Could not automatically open browser. Visit this URL to continue: {auth_request_params.redirect_url}",
            file=sys.stderr,
        )

    authorization_code = start_web_server_and_listen_for_code(
        redirect_url=credentials.callbackUrl,
        expected_state=auth_request_params.state,
        timeout_seconds=args.timeout_seconds,
    )
    session = httpx2.Client(headers={"User-Agent": USER_AGENT})
    oauth_token = request_token(
        client_id=credentials.clientId,
        authorization_code=authorization_code,
        code_verifier=auth_request_params.code_verifier,
        token_endpoint=TOKEN_ENDPOINT,
        session=session,
    )
    json_output = json.dumps(oauth_token, indent=args.indent)

    if args.output_file:
        output_path = args.output_file
        with output_path.open("w", encoding="utf-8") as f:
            f.write(json_output)
            f.write("\n")
        print(f"OAuth token saved to {output_path.resolve()}")
    else:
        print(json_output, end="")
