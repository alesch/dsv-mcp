# Why Docker

## The problem: Playwright's system deps need root

Running `dsv_tracking` requires more than a `pip install` — Playwright needs
an actual Chromium binary plus a long list of OS-level shared libraries
(GTK, font rendering, codecs, etc.) to run it. Playwright's own installer
can pull those in for you:

```
playwright install --with-deps chromium
```

We tried this on a normal dev machine early on and it failed:

```
Installing dependencies...
Switching to root user to install dependencies...
Place your finger on the fingerprint reader
Verification timed out
sudo: a terminal is required to read the password; either use the -S option to read from standard input or configure an askpass helper
sudo: a password is required
Failed to install browsers
Error: Installation process exited with code: 1
```

`--with-deps` shells out to `apt-get` under `sudo`, and `sudo` wants
interactive auth (password or fingerprint) that isn't available from a
non-interactive/automated shell. We worked around it at the time by
installing just the Chromium binary without `--with-deps` (the machine
already had the needed libs from other work), but that's not something we
can hand to someone else setting this up fresh — there's no guarantee their
machine has those libs, and no way to script past an interactive `sudo`
prompt.

## Why a container fixes this cleanly

Inside a `docker build`, the build process *is* root — there's no user to
prompt, no fingerprint reader, no TTY to wait on. `RUN uv run playwright
install --with-deps chromium` in the [`Dockerfile`](../Dockerfile) runs
`apt-get install` non-interactively and just... works, every time, on any
machine that can run `docker build`. This was the deciding factor over
other packaging options we considered (see below): it turns a step that
was failing on a real machine into a step that can't fail that way at all,
and bakes the result into an image so nobody downstream has to solve it
again.

It also happens to solve distribution more generally: a `docker run`
consumer needs nothing but Docker itself — no `uv`, no matching Python
version, no manual `playwright install` step, no risk of "works on my
machine" from differing OS package versions.

## Why Debian-slim, not the official Playwright image

Microsoft publishes official Playwright images (`mcr.microsoft.com/playwright/python`)
with Chromium and all system deps already baked in, built on full Ubuntu
(not a `-slim` variant, since Chromium's dependency list is long enough
that starting slim and adding back most of the OS doesn't save much). We
considered this and chose `python:3.12-slim-bookworm` instead, explicitly
because:

- **This needed to work now, for a demo** — not be a long-lived,
  auto-updating package. We're not chasing upstream Playwright image
  updates, so the maintenance argument for the official image (they track
  compatible dependency versions for you) mattered less here than usual.
- `--with-deps` already resolves the exact `apt` package list for us at
  build time — we don't hand-maintain it, we just don't start from an
  image that's already paid that cost on our behalf.

We also considered and ruled out **Alpine**: Playwright's Chromium build is
glibc-only and doesn't run on Alpine's musl libc. There's an unofficial
workaround (install Chromium via Alpine's own `apk` package and point
Playwright at it), but that decouples Playwright's Python bindings from the
Chromium version they're tested against — a real source of flakiness for
not much size benefit, since Chromium itself (not the base OS) is the bulk
of the image weight either way.

## Where the image lives

Published to GitHub Container Registry as `ghcr.io/alesch/dsv-mcp`, built
and pushed by [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml)
on every push to the repo's default branch, tagged both with the branch
name (`:master`, a moving tag) and the commit SHA (immutable). Both the
GitHub repo and the GHCR package are public, so `docker pull
ghcr.io/alesch/dsv-mcp:master` works for anyone, no `docker login` required.
