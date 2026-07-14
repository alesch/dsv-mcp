# Architecture Decision Records

---

## ADR-0001: Drive a real browser (Playwright) instead of reimplementing DSV's anti-bot challenge

**Context:** DSV's public tracking API (`nges-portal/api/public/tracking-public/*`)
rejects every request with `HTTP 429` on first attempt, carrying a
`captcha-puzzle` response header: three proof-of-work JWT puzzles
(Friendly-Captcha-style). A request only succeeds once retried with a
`Captcha-Solution` header proving the puzzles were solved. This is
verified from a HAR capture of the real site — see
[`dsv-tracking-api.md`](./dsv-tracking-api.md) and
[`anti-bot-puzzle.md`](./anti-bot-puzzle.md).

**Decision:** Don't reverse-engineer and reimplement the puzzle-solving
hash/nonce algorithm in Python. Instead, drive an actual Chromium instance
via Playwright so DSV's own shipped JavaScript solves its own challenge —
the same way it does for any human visitor — and read the resulting JSON
responses off the network.

**Consequences:** Every lookup costs the overhead of a real browser
navigation (slower, heavier dependency) instead of a bare
HTTP call, but we're never isolating or automating the anti-bot solving
logic outside of a genuine browser session. This was treated as a hard
line, not just a performance tradeoff.

---

## ADR-0002: Pace and serialize lookups to resemble a single human session

**Context:** To avoid anti-bot detection, simulate been a slow human.

**Decision:** `TrackingClient` (`dsv_tracking/browser_client.py`) wraps
every lookup in an `asyncio.Lock` (no concurrent lookups), inserts random
1–3s delays before navigation, enforces a cooldown between consecutive
lookups, and launches a **persistent** browser context
(`~/.cache/dsv-tracking-mcp/browser-profile`) so cookie-consent state
survives across runs instead of re-triggering the consent banner every
single lookup, like a returning human visitor would.

**Consequences:** A single `track_shipment` call can take up to ~30
seconds — documented explicitly in
[`installation.md`](./installation.md) so it isn't mistaken for the tool
hanging. Batch lookups (`test/fetch_shipments.py`) are deliberately
sequential, not parallelized, for the same reason.

---

## ADR-0003: Model API responses as typed dataclasses, not raw dicts

**Context:** The reverse-engineered endpoints return sizeable, nested JSON
(shipment summary, full detail with events/packages, trip GPS points).

**Decision:** Parse responses into `ShipmentSummary`, `ShipmentDetail`,
`TrackingEvent`, `Trip`, and `TripPoint` dataclasses
(`dsv_tracking/models.py`), each with a `from_json` classmethod, rather
than passing raw dicts through the client and MCP layers.

**Consequences:** Call sites get typed attribute access instead of dict
key lookups; the MCP tool serializes back to dicts at the boundary
(`dataclasses.asdict`) since that's what needs to cross the wire.

---

## ADR-0004: Expose one `track_shipment` MCP tool, not one tool per endpoint

**Context:** The underlying site exposes several endpoints (resolve
reference → id, shipment detail, trip points, reference-type validation
metadata) that could each have become a separate MCP tool.

**Decision:** Collapse the whole reference-number → summary → detail →
trip flow behind a single `track_shipment(reference_number)` tool
(`dsv_tracking/server.py`) that internally drives `TrackingClient` through
all the steps and returns one combined result.

**Consequences:** Simpler MCP surface for callers (one call, one paced
~30s operation, matching ADR-0002) at the cost of not exposing the
intermediate steps individually. Reasonable for a phase-1 tool; would need
revisiting if a future need (e.g. just resolving a reference without
fetching full detail) justified a finer-grained surface.

---

## ADR-0005: Package and distribute as a Docker image

**Context:** Playwright needs root access to install its dependencies.

**Decision:** Package as a Docker image. A `docker build` runs as
root by construction — no user to prompt, no interactive `sudo` — so
`RUN uv run playwright install --with-deps chromium` inside the
[`Dockerfile`](../Dockerfile) just works, unconditionally, on any machine
that can run `docker build`. Full rationale in
[`docker-packaging.md`](./docker-packaging.md).

**Consequences:** Consumers need only Docker itself — no `uv`, no matching
Python version, no manual Playwright step. Cost: a 600MB image over the network.

---

## ADR-0006: Base the image on Debian-slim, not the official Playwright/Ubuntu image

**Context:** Microsoft publishes official Playwright images
(`mcr.microsoft.com/playwright/python`) with Chromium and all system deps
already resolved, built on full Ubuntu (not `-slim`, since Chromium's
dependency list is long enough that starting slim and adding most of it
back wouldn't save much). The tradeoff against a plain slim base is
usually maintenance: the official image tracks compatible dependency
versions for you as things update.

**Decision:** Use `python:3.12-slim-bookworm` instead, explicitly because
this needed to work **now, for a demo**, not be a long-lived,
auto-updating package — the maintenance argument for the official image
mattered less than usual, and `--with-deps` already resolves the exact
`apt` package list for us at build time regardless of base image.

**Consequences:** We own reproducing this build if Debian bookworm's
package versions shift under us later; acceptable given the demo-now
framing. Exact versions are pinned via `uv sync --frozen` against the
existing `uv.lock` regardless, so the Python dependency side is
reproducible independent of this choice.

---

## ADR-0007: Rule out Alpine as the base image

**Context:** Considered Alpine for a smaller base image while deciding
ADR-0006.

**Decision:** Ruled out. Playwright's Chromium build is glibc-only and
doesn't run on Alpine's musl libc. An unofficial workaround exists
(install Chromium via Alpine's own `apk` package, point Playwright at it
via `executable_path`), but that decouples Playwright's Python bindings
from the Chromium version they're actually tested against — a real
flakiness risk.

**Consequences:** None directly (Debian-slim was chosen instead), but
recorded because the size argument for Alpine is weaker than it looks:
Chromium itself (300MB+) dominates image size regardless of base distro,
so switching Alpine's ~5MB base vs. Debian-slim's ~80MB base saves maybe
50–100MB out of a 1GB+ image — not the dramatic cut it initially sounds
like.

---

## ADR-0008: Tag images with both a moving branch tag and an immutable SHA tag

**Context:** Needed a tagging scheme for images pushed by
[`docker-publish.yml`](../.github/workflows/docker-publish.yml) — this is
the Docker-side continuation of the "pin the ref, don't float it".

**Decision:** Push both `ghcr.io/alesch/dsv-mcp:<branch>` (moving, tracks
the latest build off that branch) and `ghcr.io/alesch/dsv-mcp:<commit-sha>`
(immutable), computed dynamically via `${{ github.ref_name }}` /
`${{ github.sha }}` rather than a hardcoded branch name.

**Consequences:** The dynamic ref name actually mattered in practice: the
workflow originally hardcoded `main`, but this repo's default branch is
`master` — the first run silently never triggered until that mismatch was
caught and fixed. Using `github.ref_name` means this class of bug can't
recur even if the default branch changes again later.

---

## ADR-0009: No `--pull always`; rely on a manual one-time pre-pull instead

**Context:** `docker run` only pulls an image tag if it isn't already
cached locally — a moving tag like `:master` won't auto-refresh on
repeated runs. Docker supports forcing a fresh registry check every time
via `--pull always`, at the cost of a round-trip on every single
container start.

**Decision:** Don't add `--pull always` to the MCP client config. Instead,
document a manual `docker pull ghcr.io/alesch/dsv-mcp:master` as a
one-time step before first real use (see
[`installation.md`](./installation.md)), so the image is already cached
before it matters (e.g. before a demo).

**Consequences:** Every session after the first cached pull starts in a
couple seconds with zero network dependency. The cost is that picking up
a new build later requires remembering to re-pull manually — acceptable
since this isn't being updated on a schedule.

---

## ADR-0010: Accept an ephemeral browser profile inside the container

**Context:** `TrackingClient`'s persistent browser profile (ADR-0002)
normally survives across runs on a host machine. Inside a `--rm`'d
container, that profile is thrown away every time the container exits.

**Decision:** Accept this rather than add a bind-mounted volume for the
profile directory. `_accept_cookies_if_present()` already treats "no
consent banner present" as a no-op, so the only cost is re-clicking
cookie consent on every container run instead of just the first.

**Consequences:** Slightly less "continuous session" fidelity than
running on bare metal, but no added deployment complexity (no volume to
provision or document). Revisit if this ever needs to run high-frequency
enough that the extra consent-banner round trip becomes a real cost.
