# DSV / DB Schenker tracking MCP server

An MCP server that looks up shipments on DSV's public tracking site
(formerly `dbschenker.com`), exposing one tool: `track_shipment(reference_number)`.

## Install / use it

See [`docs/installation.md`](docs/installation.md) — Docker is the only prerequisite; the published image is
`ghcr.io/alesch/dsv-mcp:master`.

## How it works

This MCP simulates a human user looking up shipments on DSV's public tracking site. This is to avoid anti-bot measures from DSV.  

A Playwright browser drives the whole interaction. No simultaneous lookups are supported and delays are added on pourpose.     
This MCP is distribuited as a docker image to simplify the installation of Playwright's dependencies. 

## Documentation

- [`docs/dsv-tracking-api.md`](docs/dsv-tracking-api.md) — the
  reverse-engineered tracking API this server talks to: endpoints, request/response shapes.
- [`docs/anti-bot-puzzle.md`](docs/anti-bot-puzzle.md) — a deeper look at that anti-bot puzzle.
- [`docs/adr.md`](docs/adr.md) — Architecture Decision Records.

## Development

```
dsv_tracking/    the package: browser_client.py (Playwright), models.py
                 (Pydantic), server.py (the MCP tool)
scripts/         try_tracking.py -- standalone CLI, no MCP needed
test/            pytest suite -- see below
Dockerfile       Debian-slim image published to GHCR
```

Tests are tiered by marker (`pyproject.toml`):

```
uv run pytest                   # offline, no network -- runs by default
uv run pytest -m integration    # real lookups against the live DSV site
uv run pytest -m docker         # same, against a locally built image
```

`docker build -t dsv-tracking-mcp:demo .` builds the local test image used by the `docker`-marked tests.

Lint and type-check with [ruff](https://docs.astral.sh/ruff/) and [mypy](https://mypy.readthedocs.io/):

```
uv run ruff check .                       # lint
uv run ruff format .                      # auto-format
uv run mypy dsv_tracking test scripts     # type-check
```
