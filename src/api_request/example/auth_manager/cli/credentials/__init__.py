import typer

app = typer.Typer(
    no_args_is_help=True,
    name="credentials",
    help="Manage ESI authentication credentials.",
)
