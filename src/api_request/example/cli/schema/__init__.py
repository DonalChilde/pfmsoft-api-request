import typer

app = typer.Typer(no_args_is_help=True)

from esi_link.cli.schema.cached_schemas import app as cached_schemas_app
from esi_link.cli.schema.fetch_schemas import app as fetch_schemas_app
from esi_link.cli.schema.generate_doc import app as generate_doc_app
from esi_link.cli.schema.valid_compatibility_dates import (
    app as valid_compatibility_dates_app,
)

app.add_typer(cached_schemas_app)
app.add_typer(valid_compatibility_dates_app)
app.add_typer(fetch_schemas_app)
app.add_typer(generate_doc_app)
