import typer

app = typer.Typer(no_args_is_help=True)


app.command()


def info(ctx: typer.Context) -> None:
    """Display information about the cache database."""
    typer.echo("Cache Info Placeholder...")
