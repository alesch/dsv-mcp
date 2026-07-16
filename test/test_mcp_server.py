"""Real, network-hitting end-to-end check of the MCP server over stdio.

Spawns `uv run python -m dsv_tracking.server` as a real subprocess and
talks MCP to it, same as a real MCP client would. Slow -- opt in with
`pytest -m integration`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWN_REFERENCE = "3476236157"
KNOWN_STT = "SESOE620172194"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_track_shipment_over_stdio():
    params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "dsv_tracking.server"],
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        tools = await session.list_tools()
        assert "track_shipment" in [t.name for t in tools.tools]

        result = await session.call_tool("track_shipment", {"reference_number": KNOWN_REFERENCE})
        assert not result.isError

        [block] = result.content
        assert isinstance(block, TextContent)
        payload = json.loads(block.text)
        assert payload["summary"]["stt"] == KNOWN_STT
        assert payload["detail"]["active_step"] == "DELIVERED"
