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
