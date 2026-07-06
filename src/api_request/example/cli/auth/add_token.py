"""CLI command for adding a token for a character."""

# pyright: standard
import asyncio
import webbrowser
from typing import Annotated

import typer
from rich.console import Console

from esi_link.auth.helpers.request_authentication_code import (
    generate_request_params,
    start_web_server_and_listen_for_code,
)
from esi_link.cli.helpers import get_esi_link_settings_from_context
from esi_link.esi_link_api import EsiLink

app = typer.Typer(no_args_is_help=True)


@app.command(name="add")
def add_token(
    ctx: typer.Context,
    character_id: Annotated[
        int,
        typer.Argument(
            help="The character ID to add a token for.",
        ),
    ],
    browser_auto_open: Annotated[
        bool, typer.Option(help="Whether to automatically open the browser.")
    ] = True,
    server_timeout: Annotated[
        int, typer.Option(help="Seconds to wait for authentication code.")
    ] = 120,
) -> None:
    """Add a token for a character."""
    console = Console()
    settings = get_esi_link_settings_from_context(ctx)

    async def _add_token() -> None:
        esi_link = EsiLink(settings)
        async with esi_link:
            if esi_link.app_data.token_manager is None:
                console.print(
                    "Token manager not initialized. Have you added credentials?"
                )
                raise typer.Exit(1)
            token_tool = esi_link.token_tool
            if character_id in esi_link.app_data.token_manager.available_characters:
                console.print(
                    f"[yellow]A token for character ID {character_id} already exists.[/yellow]"
                )
                raise typer.Exit(1)
            credentials = esi_link.app_data.get_credentials()
            if credentials is None:
                console.print(
                    "[red]No credentials found. Please add credentials before adding tokens.[/red]"
                )
                raise typer.Exit(1)
            request_params = generate_request_params(
                client_id=credentials.clientId,
                callback_url=credentials.callbackUrl,
                authorization_endpoint=token_tool._oauth_metadata.authorization_endpoint,
                scopes=credentials.scopes,
            )
            if browser_auto_open:
                opened = webbrowser.open(request_params.redirect_url)
                if opened:
                    console.print("Opened browser for authorization.")
                else:
                    console.print(
                        "Could not automatically open browser. Visit this URL to continue:"
                    )
                    console.print(request_params.redirect_url)
            else:
                console.print("Visit this URL to continue:")
                console.print(request_params.redirect_url)
            authorization_code = start_web_server_and_listen_for_code(
                redirect_url=credentials.callbackUrl,
                expected_state=request_params.state,
                timeout_seconds=server_timeout,
            )
            if not authorization_code:
                console.print(
                    f"[red]Did not receive authentication code within {server_timeout} seconds.[/red]"
                )
                raise typer.Exit(1)
            console.print("Received authentication code, exchanging for token...")

            oauth_token = token_tool.request_new_token(
                client_id=credentials.clientId,
                authorization_code=authorization_code,
                code_verifier=request_params.code_verifier,
            )
            character_token = token_tool.create_character_token(oauth_token)
            if character_token.character_id != character_id:
                console.print(
                    f"[red]Received token for character ID {character_token.character_id}, but expected {character_id}.[/red]"
                )
                raise typer.Exit(1)
            esi_link.app_data.token_manager.save_character(character_token)
        console.print(
            f"[green]Successfully added token for character ID {character_id}.[/green]"
        )

    asyncio.run(_add_token())
