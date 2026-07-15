from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from pathlib import Path
from typing import Any

from playwright.async_api import Response, async_playwright

from dsv_tracking.models import ShipmentDetail, ShipmentNotFound, ShipmentSummary, Trip

TRACKING_URL = "https://www.dsv.com/mydsv/tracking-public/"
DEFAULT_LANGUAGE_REGION = "en-GB_GB"

_SEARCH_RE = re.compile(r"/nges-portal/api/public/tracking-public/shipments\?query=")
_DETAIL_RE = re.compile(r"/nges-portal/api/public/tracking-public/shipments/[a-z]+/[^/]+$")
_TRIP_RE = re.compile(r"/nges-portal/api/public/tracking-public/shipments/[a-z]+/[^/]+/trip$")

_PROFILE_DIR = Path.home() / ".cache" / "dsv-tracking-mcp" / "browser-profile"

logger = logging.getLogger(__name__)


class TrackingClient:
    """Drives a real Chromium browser against DSV's public tracking site.

    We rely on the site's own JavaScript to solve its proof-of-work anti-bot
    challenge (see docs/dsv-tracking-api.md) exactly as it would for a human
    visitor; we only read the resulting API responses off the network. Calls
    are serialized and paced with human-scale delays -- this is not meant to
    run many lookups quickly.
    """

    def __init__(
        self,
        headless: bool = True,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        cooldown: float = 7.0,
        response_timeout: float = 45.0,
    ):
        self._headless = headless
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._cooldown = cooldown
        self._response_timeout = response_timeout

        self._lock = asyncio.Lock()
        self._last_call_at: float | None = None

        self._playwright = None
        self._context = None
        self._page = None

    async def start(self) -> None:
        _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Starting Playwright Chromium browser using profile: %s", _PROFILE_DIR)
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(_PROFILE_DIR),
            headless=self._headless,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="en-GB",
        )
        self._page = await self._context.new_page()
        await self._warm_up()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def __aenter__(self) -> TrackingClient:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    async def _warm_up(self) -> None:
        """Load the bare tracking page once so cookie consent is settled."""
        url = f"{TRACKING_URL}?language_region={DEFAULT_LANGUAGE_REGION}"
        logger.info("Warming up browser context by loading %s", url)
        await self._page.goto(
            url,
            wait_until="networkidle",
        )
        await self._accept_cookies_if_present()

    async def _accept_cookies_if_present(self) -> None:
        try:
            for frame in self._page.frames:
                button = frame.get_by_role("button", name=re.compile("accept", re.I))
                if await button.count() > 0:
                    logger.info("Found cookie consent banner. Accepting...")
                    await button.first.click(timeout=3000)
                    await self._human_delay()
                    return
        except Exception as exc:
            logger.debug("Cookie consent banner check failed or already accepted: %s", exc)
            pass

    async def _human_delay(self) -> None:
        await asyncio.sleep(random.uniform(self._min_delay, self._max_delay))

    async def _respect_cooldown(self) -> None:
        if self._last_call_at is None:
            return
        elapsed = time.monotonic() - self._last_call_at
        remaining = self._cooldown - elapsed
        if remaining > 0:
            logger.info("Enforcing rate limit cooldown. Sleeping for %.2f seconds...", remaining)
            await asyncio.sleep(remaining)

    async def track(self, reference_number: str) -> tuple[ShipmentSummary, ShipmentDetail, Trip | None]:
        """Look up a shipment by reference number.

        Raises ShipmentNotFound if the site has no match.
        """
        async with self._lock:
            await self._respect_cooldown()
            try:
                return await self._track_locked(reference_number)
            finally:
                self._last_call_at = time.monotonic()

    async def _track_locked(
        self, reference_number: str
    ) -> tuple[ShipmentSummary, ShipmentDetail, Trip | None]:
        logger.info("Initiating tracking request for reference: %s", reference_number)
        search_future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        detail_future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        trip_future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()

        def on_response(response: Response) -> None:
            url = response.url
            if response.status != 200:
                return
            if _SEARCH_RE.search(url) and not search_future.done():
                search_future.set_result(response)
            elif _TRIP_RE.search(url) and not trip_future.done():
                trip_future.set_result(response)
            elif _DETAIL_RE.search(url) and not detail_future.done():
                detail_future.set_result(response)

        self._page.on("response", on_response)
        try:
            logger.debug("Applying random human pacing delay...")
            await self._human_delay()
            url = f"{TRACKING_URL}?language_region={DEFAULT_LANGUAGE_REGION}&refNumber={reference_number}"
            logger.info("Navigating browser to tracking URL: %s", url)
            await self._page.goto(
                url,
                wait_until="networkidle",
            )
            await self._accept_cookies_if_present()

            logger.info("Waiting for API search response resolving reference...")
            search_response = await asyncio.wait_for(search_future, timeout=self._response_timeout)
            search_data = await search_response.json()
            results = search_data.get("result", [])
            if not results:
                logger.warning("No shipment found for reference: %s", reference_number)
                raise ShipmentNotFound(reference_number)
            summary = ShipmentSummary.model_validate(results[0])
            logger.info("Shipment resolved. ID: %s, STT: %s", summary.id, summary.stt)

            logger.info("Waiting for API shipment details response...")
            detail_response = await asyncio.wait_for(detail_future, timeout=self._response_timeout)
            detail_data = await detail_response.json()
            detail = ShipmentDetail.model_validate(detail_data)
            logger.info("Shipment details received (active step: %s)", detail.active_step)

            trip: Trip | None = None
            try:
                logger.info("Waiting for optional API trip route details response...")
                trip_response = await asyncio.wait_for(trip_future, timeout=self._response_timeout)
                trip = Trip.model_validate(await trip_response.json())
                logger.info("Trip route data loaded successfully (%d points)", len(trip.points))
            except asyncio.TimeoutError:
                logger.info("Trip route request timed out (trip route not available)")
                trip = None

            return summary, detail, trip
        except Exception as exc:
            logger.error("Tracking lookup failed for reference %s: %s", reference_number, exc, exc_info=True)
            raise
        finally:
            self._page.remove_listener("response", on_response)
