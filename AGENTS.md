# AGENTS.md - api request

## Project Overview

A cli and api for aquiring, storing, retrieving, and refreshing the Oauth tokens used to access the authorization required endpoints of the EVE Online ESI

## Current State and Goals

### State

This project is under a major reorganization, with lots of code being copy pasted in and then refactored.

NOTE: The entire `src/api_request/example` package is purely for reference. It contains non-working code, and it will be deleted as the important ideas are transfered over to the new code base. Ignore it.

### Goals

Initial project setup and copying over code.

### Key Dependencies

see [pyproject,toml](pyproject.toml)

## Commands

- Generate project .venv and install app and dev dependencies: `uv sync`
- Run tests: `uv run pytest`
- Lint: `uv run ruff check`
- Format check .py files: `uv run ruff format --check`
- Format .py files: `uv run ruff format`
- run app cli: `uv run api-request`

NOTE: run Format command on python files before linting. This will fix many of the lint errors automatically.

## Environment

see [pyproject,toml](pyproject.toml)

This project uses `uv`, and has a `.venv` at the project root.

## Project Structure

- `src/` - application source code
- `tests/` - test files. Mirror src/ structure.

## Code Style

```python
# example.py
"""This is an example of a python code file.

This doc string provides a brief overview of the file's purpose and contents. It can
include information about the module, its functions, classes, and any other relevant
details.

When docstrings are generated, they should follow the Google style guide for consistency
and clarity.

They should also try to respect a line length of about 88 characters before wrapping to
the next line.

"""

# Use Google style docstrings for documentation.

from collections.abc import Iterator
from types import TracebackType
from typing import Self


def example_function(
    primary_arg: int, *, secondary_arg: int, other_args: str
) -> Iterator[int]:
    """Some work is done here.

    Args:
        primary_arg: The primary argument for the function.
        secondary_arg: The secondary argument for the function.
        other_args: Other arguments for the function.

    Returns:
        An iterator of integers resulting from the function's work.

    Raises:
        ValueError: If primary_arg is negative.
    """
    # Function implementation goes here
    if primary_arg < 0:
        raise ValueError("primary_arg must be non-negative")
    return iter(range(primary_arg + secondary_arg))


class ExampleClass:
    """An example class demonstrating Google style docstrings."""

    def __init__(self, value: int) -> None:
        """Initializes the ExampleClass with a value.

        Args:
            value: An integer value to initialize the class.
        """
        self.value = value

    def __enter__(self) -> Self:
        """Enter the context manager."""
        raise NotImplementedError("ExampleClass.__enter__ is not implemented")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the context manager."""
        raise NotImplementedError("ExampleClass.__exit__ is not implemented")
```

- Python code should be documented using Google style docstrings.
- Generated code should come with docstings, even if they are place holders because behavior has not been nailed down.
- Docstrings should explain the purpose of a function when it is unclear.
- Docstrings should be kept current after refactors.
- Type hints should always be used in python code.
- Python Functions with multiple args should prefer required key word arguments using `*,`
- Prefer match case over complicated if then statements.
- Prefer python language features from the project python version
- Prefer multiple short functions over one long one, except where this makes the code harder to understand.

## Typer CLI Documentation Style

Use these rules for Typer command docs across the repository.

- Treat option and argument `help=` text as the primary user-facing guidance.
- Keep `help=` text brief and scannable, including key behavior and constraints.
- Keep key behavior in both places when helpful: brief in `help=`, expanded in the command docstring.
- Use command docstrings for expanded and structured details such as Notes, Output, field lists, and JSON shapes.
- Keep command docstrings user-facing. Do not document invisible internal context parameters.
- Place developer-only context in nearby code comments below the docstring when needed.
- Keep terminology and option names consistent across commands (prefer kebab-case option names).
- Validate help rendering after doc updates with `uv run eve-auth <group> <command> --help`.

## Non Obvious Patterns

## Testing Rules

- Write tests for all new functions using Red/Green methodology
- Keep tests current through refactors.
- Mock all external dependencies.

## Boundries

### Allowed without asking

- Read files
- List directory contents
- Run tests in this project
- Lint files in this project
- Format python files in this project

### Ask First

- install or remove packages
- delete files

### Never Do This!

- push to git or open PRs

## Key Files
