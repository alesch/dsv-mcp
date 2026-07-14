"""Offline check of the track_shipment tool's advertised output schema.

No network calls, no browser -- importing dsv_tracking.server registers
the tool but doesn't start TrackingClient (that only happens once the
server's lifespan actually runs).
"""

from __future__ import annotations

import pytest

from dsv_tracking.server import mcp


@pytest.mark.asyncio
async def test_track_shipment_output_schema_is_structured():
    tools = await mcp.list_tools()
    track_shipment = next(t for t in tools if t.name == "track_shipment")

    # Since the Phase 2 dataclass -> Pydantic BaseModel migration,
    # track_shipment returns a TrackShipmentResult model directly, so
    # FastMCP now advertises a real nested schema instead of None.
    schema = track_shipment.outputSchema
    assert schema is not None
    assert set(schema["properties"]) == {"summary", "detail", "trip", "error"}
