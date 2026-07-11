"""Validate an api request."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate an api request."""
    typer.echo("Validation Placeholder...")
