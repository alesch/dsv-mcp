"""Real, network-hitting check of TrackingClient against the live DSV site.

Slow (drives a real paced browser session, see docs/anti-bot-puzzle.md) --
opt in with `pytest -m integration`.
"""

from __future__ import annotations

import pytest

from dsv_tracking.browser_client import TrackingClient

KNOWN_REFERENCE = "3476236157"
KNOWN_STT = "SESOE620172194"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_track_known_shipment():
    async with TrackingClient() as client:
        summary, detail, trip = await client.track(KNOWN_REFERENCE)

    assert summary.stt == KNOWN_STT
    assert summary.transport_mode == "LAND"
    assert detail.stt_number == KNOWN_STT
    assert detail.active_step == "DELIVERED"
    assert len(detail.events) == 7
    assert trip is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_track_recovers_after_real_page_crash():
    """Kill the real Playwright page mid-session and confirm the next lookup
    transparently recovers instead of raising."""
    async with TrackingClient() as client:
        crashed_page = client._page
        assert crashed_page is not None
        await crashed_page.close()
        assert crashed_page.is_closed()

        summary, detail, trip = await client.track(KNOWN_REFERENCE)

        assert client._page is not None
        assert client._page is not crashed_page
        assert not client._page.is_closed()

    assert summary.stt == KNOWN_STT
    assert detail.stt_number == KNOWN_STT
    assert detail.active_step == "DELIVERED"
    assert trip is not None
