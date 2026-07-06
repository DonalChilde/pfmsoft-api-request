"""CLI command to add a character to the auth manager."""

import webbrowser
from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console

from ...auth.request_authentication_code import (
    generate_request_params,
    start_web_server_and_listen_for_code,
)
from ...sqlite.manager import SqliteAuthManager
from ...token_tool import TokenTool
from ..helpers import get_auth_manager_settings_from_context

app = typer.Typer(no_args_is_help=True)


@app.command(name="add")
def add(
    ctx: typer.Context,
    character_id: Annotated[int, typer.Argument(help="ID of the character to add")],
    cred_id: Annotated[str, typer.Argument(help="ID of the credentials to use")],
    browser_auto_open: Annotated[
        bool, typer.Option(help="Whether to automatically open the browser.")
    ] = True,
    server_timeout: Annotated[
        int, typer.Option("--timeout", help="Seconds to wait for authentication code.")
    ] = 120,
) -> None:
    """Add a character."""
    messenger = Console(stderr=True)
    settings = get_auth_manager_settings_from_context(ctx)
    cred_uuid = UUID(cred_id)
    if settings.client_session is None:
        messenger.print(
            "[red]Client session is not initialized. Please check your settings.[/red]"
        )
        raise typer.Exit(1)
    with SqliteAuthManager(settings.auth_db_path) as auth_manager:
        if not auth_manager.get_credentials(cred_uuid):
            messenger.print(
                f"[red]Credentials with ID {cred_id} not found. Please add credentials first.[/red]"
            )
            raise typer.Exit(1)
        if character_id in auth_manager.get_all_character_ids(cred_uuid):
            messenger.print(
                f"[yellow]Character ID {character_id} is already authorized with credentials ID {cred_id}.[/yellow]"
            )
            raise typer.Exit(1)
        oauth_metadata = auth_manager.get_oauth_metadata()
        credentials = auth_manager.get_credentials(cred_uuid)
        token_tool = TokenTool(oauth_metadata)
        request_params = generate_request_params(
            client_id=credentials.clientId,
            callback_url=credentials.callbackUrl,
            authorization_endpoint=token_tool.authorization_endpoint,
            scopes=credentials.scopes,
        )
        if browser_auto_open:
            opened = webbrowser.open(request_params.redirect_url)
            if opened:
                messenger.print("Opened browser for authorization.")
            else:
                messenger.print(
                    "Could not automatically open browser. Visit this URL to continue:"
                )
                messenger.print(request_params.redirect_url)
        else:
            messenger.print("Visit this URL to continue:")
            messenger.print(request_params.redirect_url)
        authorization_code = start_web_server_and_listen_for_code(
            redirect_url=credentials.callbackUrl,
            expected_state=request_params.state,
            timeout_seconds=server_timeout,
        )
        if not authorization_code:
            messenger.print(
                f"[red]Did not receive authentication code within {server_timeout} seconds.[/red]"
            )
            raise typer.Exit(1)
        messenger.print("Received authentication code, exchanging for token...")
        with settings.client_session as session:
            oauth_token = token_tool.request_new_token(
                client_id=credentials.clientId,
                authorization_code=authorization_code,
                code_verifier=request_params.code_verifier,
                session=session,
            )
        character_token = token_tool.create_character_token(
            cred_id=cred_uuid, oauth_token=oauth_token
        )
        if character_token.character_id != character_id:
            messenger.print(
                f"[red]Received token for character ID {character_token.character_id}, but expected {character_id}.[/red]"
            )
            raise typer.Exit(1)
        auth_manager.add_character(character_token)
        messenger.print(
            f"[green]Successfully added character ID {character_id} with credentials ID {cred_id}.[/green]"
        )
