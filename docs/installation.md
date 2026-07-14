# Installing the DSV tracking MCP server

## Prerequisites

Just [Docker](https://docs.docker.com/get-docker/). No Python, no `uv`, no
manual Playwright setup — all of that is baked into the published image
(see [`docker-packaging.md`](./docker-packaging.md) for why).

## 1. Add it to your MCP client config

```json
{
  "mcpServers": {
    "dsv-tracking": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/alesch/dsv-mcp:master"]
    }
  }
}
```

For Claude Code, equivalently:

```
claude mcp add dsv-tracking -- docker run -i --rm ghcr.io/alesch/dsv-mcp:master
```

The image is public — no `docker login` needed.

## 2. Understanding the first-run delay

Your MCP client doesn't fetch the image itself — it spawns `docker run`,
and **`docker` decides whether to pull** based on whether the image tag
already exists locally:

- **First time ever** this tag runs on your machine: it isn't cached
  locally, so `docker` pulls the full image from GHCR before starting the
  server. The image is ~2GB uncompressed (Chromium plus its system
  libraries dominate that size), so on a typical connection this is a
  **one-time delay of roughly a minute or two** before the MCP server
  responds to its first request. Your MCP client may look like it's hung
  during this — it isn't, `docker` is downloading in the background.
- **Every launch after that**: the tag is already cached locally, so
  `docker run` starts immediately (a couple seconds) with no network
  fetch at all. `:master` is a moving tag, but Docker does not
  automatically re-check the registry for a newer version of a tag it
  already has cached — so this stays fast indefinitely, until you
  explicitly pull again.

**To avoid hitting that delay live** (e.g. right before a demo), pre-pull
once ahead of time:

```
docker pull ghcr.io/alesch/dsv-mcp:master
```

then your MCP client's first real launch will already find the image
cached and start fast.

### A second, unrelated delay: per-lookup pacing

Once the server is running, each `track_shipment` call still takes up to
~30 seconds — that's not a download, it's the tool deliberately driving a
real browser with human-like pauses (see
[`anti-bot-puzzle.md`](./anti-bot-puzzle.md)) instead of hammering DSV's
API. Don't confuse this per-call pacing with the one-time image pull above
— pulling only ever happens on a cache miss; the per-call delay happens on
every single lookup, by design.

## 3. Getting updates later

Since `:master` won't auto-refresh, picking up a newer build (after a new
push to the repo triggers `.github/workflows/docker-publish.yml`) requires
an explicit re-pull:

```
docker pull ghcr.io/alesch/dsv-mcp:master
```

Restart your MCP client afterward so it spawns a fresh container from the
updated image.

## 4. Verifying it works

Run it directly (outside any MCP client) and confirm it starts without
errors:

```
docker run -i --rm ghcr.io/alesch/dsv-mcp:master
```

It speaks MCP over stdio and won't print anything on its own — Ctrl-C to
stop. To actually exercise the `track_shipment` tool end-to-end, use it
through your MCP client with a real reference number (e.g. one from
[`../test/reference_numbers.txt`](../test/reference_numbers.txt)).
