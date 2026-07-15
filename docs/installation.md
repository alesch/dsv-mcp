# Installing the DSV tracking MCP server

## Prerequisites

Just Docker. See their [installation guide](https://docs.docker.com/engine/install/) for details.

The image is public — no `docker login` needed.

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

- **Claude Code**

```
claude mcp add dsv-tracking -- docker run -i --rm ghcr.io/alesch/dsv-mcp:master
```

- **Cursor** — add it to `~/.cursor/mcp.json` (global, all projects) or
  `.cursor/mcp.json` in a project root (project-only, safe to commit for a
  shared team config). No CLI needed; also editable via Settings → MCP.

- **Windsurf** — same block, in `~/.codeium/windsurf/mcp_config.json`.

- **Antigravity** — same block, in
  `~/.gemini/config/mcp_config.json` (shared by the Antigravity IDE and
  CLI). Also reachable in-app: agent panel's MCP Servers dropdown → Manage
  MCP Servers → View raw config.

- **VS Code** (GitHub Copilot) — in `.vscode/mcp.json` (workspace) or
  your user profile. Equivalently from the command line:

  ```
  code --add-mcp "{\"name\":\"dsv-tracking\",\"command\":\"docker\",\"args\":[\"run\",\"-i\",\"--rm\",\"ghcr.io/alesch/dsv-mcp:master\"]}"
  ```

- **Zed editor** — in `~/.config/zed/settings.json` (open it
  from the command palette with "zed: open settings"):

  ```json
  {
    "context_servers": {
      "dsv-tracking": {
        "source": "custom",
        "command": "docker",
        "args": ["run", "-i", "--rm", "ghcr.io/alesch/dsv-mcp:master"]
      }
    }
  }
  ```

- **opencode** — in `opencode.json` (project root) or
  `~/.config/opencode/opencode.json` (global):

  ```json
  {
    "mcp": {
      "dsv-tracking": {
        "type": "local",
        "command": ["docker", "run", "-i", "--rm", "ghcr.io/alesch/dsv-mcp:master"]
      }
    }
  }
  ```

- **Pi** (pi.dev coding agent) — same `mcpServers` block as the generic
  example above, in `~/.pi/agent/mcp.json`. Also configurable interactively
  by running `/mcp` inside Pi.


## 2. Understanding the first-run delay

Your MCP client doesn't fetch the image itself — it spawns `docker run`,
and **`docker` decides whether to pull** based on whether the image tag
already exists locally:

- **First time ever** this tag runs on your machine: it isn't cached
  locally, so `docker` pulls the full image from GHCR before starting the
  server. The image is 600MB uncompressed (Chromium plus its system
  libraries dominate that size). Your MCP client may look like it's hung
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
API. The per-call delay happens on every single lookup, by design.

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

### Send it a reference number and read the output directly

The image also ships the standalone CLI script (`scripts/try_tracking.py`)
that the server itself is built on, so you can send it a real reference
number and see human-readable output on your console — no MCP client
needed. Override the image's default entrypoint (which normally starts
the MCP stdio server) to run the script instead:

```
docker run --rm --entrypoint uv ghcr.io/alesch/dsv-mcp:master \
  run python scripts/try_tracking.py 3476236157
```

This drives the same real, paced browser lookup `track_shipment` would
(see the per-lookup pacing note above — expect it to take up to ~30
seconds) and prints the shipment's status, route, and full event
timeline. It's the fastest way to confirm the image actually works
end-to-end after installing, before wiring it into an MCP client at all.

### Through an MCP client

Once the above works, use it through your MCP client with a real
reference number (e.g. one from
[`../test/reference_numbers.txt`](../test/reference_numbers.txt)) to
confirm the `track_shipment` tool itself responds correctly.
