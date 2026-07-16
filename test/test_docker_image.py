"""Real, network-hitting end-to-end check against a locally built Docker image.

Requires `docker build -t dsv-tracking-mcp:demo .` to have been run first.
Slow -- opt in with `pytest -m docker`.
"""

from __future__ import annotations

import json

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

IMAGE = "dsv-tracking-mcp:demo"
KNOWN_REFERENCE = "3476236157"
KNOWN_STT = "SESOE620172194"


@pytest.mark.docker
@pytest.mark.asyncio
async def test_track_shipment_via_docker_run():
    params = StdioServerParameters(
        command="docker",
        args=["run", "-i", "--rm", IMAGE],
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        tools = await session.list_tools()
        assert "track_shipment" in [t.name for t in tools.tools]

        result = await session.call_tool("track_shipment", {"reference_number": KNOWN_REFERENCE})
        assert not result.isError

        [block] = result.content
        payload = json.loads(block.text)
        assert payload["summary"]["stt"] == KNOWN_STT
        assert payload["detail"]["active_step"] == "DELIVERED"
