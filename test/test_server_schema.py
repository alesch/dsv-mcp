"""Offline check of the track_shipment tool's advertised output schema.

No network calls, no browser -- importing dsv_tracking.server registers
the tool but doesn't start TrackingClient (that only happens once the
server's lifespan actually runs).
"""

from __future__ import annotations

import pytest

from dsv_tracking.server import mcp


@pytest.mark.asyncio
async def test_track_shipment_output_schema_is_currently_unstructured():
    tools = await mcp.list_tools()
    track_shipment = next(t for t in tools if t.name == "track_shipment")

    # Baseline as of Phase 1: a bare `-> dict` return annotation does NOT
    # trigger FastMCP structured output. This assertion is expected to
    # flip once Phase 2 switches the return type to a Pydantic model.
    assert track_shipment.outputSchema is None
