# api-request

`api-request` is an API-first Python project for executing batched HTTP requests with:

- async request orchestration
- optional SQLite-backed caching
- configurable rate limiting
- JSON in / JSON out workflows

It includes a simple CLI for running request batches from stdin or files, and a Python API for integrating the same behavior in application code.

## Project Status

- Package manager: `uv`
- Distribution: source-only for now (no PyPI release yet)
- Python: `>=3.14`

## Installation

Clone the repository and sync dependencies with `uv`:

```bash
uv sync
```

This creates/updates the local `.venv` and installs app + dev dependencies.

## Quick Start (CLI)

Show CLI help:

```bash
uv run api-request --help
```

Run a batch from stdin and print plain JSON to stdout:

```bash
cat requests.json | uv run api-request --from - --to - --plain --indent 2
```

Run from file and write to file:

```bash
uv run api-request --from requests.json --to responses.json --overwrite --indent 2
```

Show version and resolved runtime directories:

```bash
uv run api-request --version
```

### Input JSON Shape

The CLI expects a JSON object keyed by request UUID. Each value is a request definition.

Minimal example:

```json
{
  "00000000-0000-0000-0000-000000000001": {
		"url": "https://esi.evetech.net/status/",
		"method": "GET"
  }
}
```

Supported request fields include:

- `url` (required)
- `method` (required)
- `headers` (optional map)
- `body` (optional)
- `parameters` (optional query param map)
- `cache_key` (optional UUID)
- `rate_key` (optional string)

### Output JSON Shape

The CLI returns a JSON object with:

- `successful`: map of request UUID -> response
- `failed`: map of request UUID -> failed response

## Python API Usage

```python
import asyncio
from uuid import uuid4

from api_request import ApiRequester, Request
from api_request.cache import InMemoryCache
from api_request.rate_limit import AiolimiterRateLimiterFactory


async def main() -> None:
    request = Request(
        request_key=uuid4(),
        method="GET",
        url="https://esi.evetech.net/status/",
        cache_key=uuid4(),
        rate_key="esi-status",
    )

    async with ApiRequester(
        cache_factory=InMemoryCache,
        rate_limiter_factory=AiolimiterRateLimiterFactory(
            max_rate=50.0,
            time_period=60.0,
        ),
    ) as requester:
        responses = await requester.process_requests({request.request_key: request})
        print(responses)


if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

Runtime settings use environment variables with the `API_REQUEST_` prefix.

- `API_REQUEST_APPLICATION_DIRECTORY`: overrides the app directory used for cache and logs.

You can also set this from the CLI with `--application-directory`.

## Development

Common commands:

```bash
uv sync
uv run ruff format
uv run ruff check
uv run pytest
```

## Repository Layout

- `src/api_request/`: package source
- `src/api_request/cli/`: Typer CLI entrypoints
- `src/api_request/request/`: request orchestration and models
- `src/api_request/cache/`: cache implementations and protocols
- `tests/`: test suite

## License

MIT. See `LICENSE`.
