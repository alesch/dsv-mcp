# Anti-bot proof-of-work puzzle, explained

Companion to the "Anti-bot: proof-of-work challenge" section in
[`dsv-tracking-api.md`](./dsv-tracking-api.md). That section documents what
was observed on the wire; this doc explains what the puzzle is and how this
project deals with it.

## What the challenge is for

Every call to `nges-portal/api/public/tracking-public/*` gets rejected with
`HTTP 429` on first attempt, even mid-session on internal navigations. The
429 carries a puzzle the client must solve before a retried request will
succeed. This is DSV's defense against automated scraping of the public
tracking API — no image grid, no "click the traffic lights", it happens
silently in JS while the page loads.

## What the puzzle actually is

It matches the [Friendly Captcha](https://friendlycaptcha.com/) proof-of-work
scheme:

1. The server issues 3 JWTs (`alg: HS256`) in the `captcha-puzzle` response
   header. Each JWT payload has a `puzzle` string (difficulty + a per-puzzle
   prefix, base64-encoded) and a 60-second expiry (`iat`/`exp`).
2. The browser must find, for each puzzle, an 8-byte **nonce** such that
   `hash(puzzle_bytes || nonce)` satisfies some difficulty condition (e.g.
   hashes below a target) — a brute-force search, not something solvable
   analytically, similar in spirit to Bitcoin mining but much cheaper.
3. The client resubmits the original request with a `Captcha-Solution`
   header: a base64 JSON array of `{jwt, solution}`, one entry per puzzle,
   where `solution` is the base64-encoded nonce found.
4. The server re-hashes and verifies before returning `200`.

It's "proof of work" in the literal sense: solving costs real (if small,
sub-second on a modern CPU) compute, which is cheap for one legitimate
browser tab but expensive at the scale of mass automated requests.

Crucially, no third-party CAPTCHA domain (e.g. `*.friendlycaptcha.com`) is
contacted — the puzzle is issued and verified same-origin (`www.dsv.com`),
proxied through DSV's own backend, and **solved by DSV's own bundled
client-side JS** (shipped in their `shell`/`tracking-public` bundles).

## How we use the page's original JS to solve it

Because the solving logic already exists in DSV's own shipped JS and runs
automatically the moment a real browser loads `www.dsv.com`, we don't need
(and deliberately don't build) a standalone solver. Instead,
`dsv_tracking/browser_client.py`'s `TrackingClient` drives a real Chromium
instance via Playwright:

- `start()` launches a persistent browser context and navigates to the
  actual tracking page.
- `_track_locked()` navigates to the tracking URL with the reference number
  as a query param (`self._page.goto(...)`). DSV's own JS executes in that
  page exactly as it would for a human visitor — it receives the 429,
  brute-forces the nonce for each puzzle, and retries with
  `Captcha-Solution` — entirely inside the browser, invisible to our code.
- We never see or touch the puzzle at all. We attach a `response` listener
  (`self._page.on("response", on_response)`) that watches for the specific
  API URLs we care about (search / detail / trip) to come back with
  `status == 200`, and read `.json()` off those responses directly.

So "using the page's original JS to solve the puzzle" means: don't
reimplement the hash/nonce brute-force algorithm in Python — instead drive
one real browser tab per lookup so the site's own shipped code solves its
own challenge, and passively observe the resulting network traffic.

## Why this matters (implication for automation)

Reimplementing the puzzle-solving algorithm standalone (outside a real
browser) would amount to building a dedicated anti-bot bypass tool that
could run at a scale and speed no human browsing session ever would — a
materially different (and more sensitive) thing than automating a single
real browser session per lookup. This project instead:

- Drives one real Chromium session per lookup via Playwright.
- Paces requests with human-scale delays and a cooldown between calls
  (`_human_delay`, `_respect_cooldown` in `browser_client.py`).
- Never runs lookups concurrently.

The intent is to resemble a single human user browsing the public tracking
page, not to defeat or work around the anti-bot challenge itself.
