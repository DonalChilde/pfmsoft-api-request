"""CLI command for listing authentication tokens."""

# pyright: standard

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown

from esi_link.auth.models import CharacterToken
from esi_link.cli.helpers import get_esi_link_settings_from_context
from esi_link.esi_link_api import EsiLink

app = typer.Typer(no_args_is_help=True)


@app.command(name="list")
def list_tokens(ctx: typer.Context) -> None:
    """List all available tokens."""
    console = Console()
    settings = get_esi_link_settings_from_context(ctx)

    async def _list_tokens() -> None:
        esi_link = EsiLink(settings)
        async with esi_link:
            if esi_link.app_data.token_manager is None:
                console.print(
                    "Token manager not initialized. Have you added credentials?"
                )
                raise typer.Exit(1)
            all_tokens = esi_link.app_data.token_manager.get_all_characters()
            if not all_tokens:
                console.print("No tokens found.")
                raise typer.Exit(0)
            console.print("Available Tokens:")
            token_dict = {token.character_id: token for token in all_tokens}
            markdown_table = _markdown_format_character_tokens(token_dict)
            console.print(Markdown(markdown_table))

    asyncio.run(_list_tokens())


def _markdown_format_character_tokens(
    character_tokens: dict[int, CharacterToken],
) -> str:
    """Format the character tokens as a markdown table."""
    if not character_tokens:
        return "No tokens found."
    lines = [
        "| Character ID | Character Name | Expires In |",
        "|--------------|----------------|------------|",
    ]
    for character_id, token in character_tokens.items():
        if token.expires_in < 0:
            expires_in = "Expired"
        else:
            expires_in = f"{token.expires_in} seconds"
        lines.append(f"| {character_id} | {token.character_name} | {expires_in} |")
    return "\n".join(lines)
