from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel

from dsv_tracking.browser_client import TrackingClient
from dsv_tracking.models import ShipmentDetail, ShipmentNotFound, ShipmentSummary, Trip


@dataclass
class AppContext:
    tracking_client: TrackingClient


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    client = TrackingClient()
    await client.start()
    try:
        yield AppContext(tracking_client=client)
    finally:
        await client.close()


mcp = FastMCP(
    name="dsv-tracking",
    instructions=(
        "Track shipments on DSV / DB Schenker's public tracking site. "
        "Only one lookup runs at a time and each call is paced with human-like "
        "delays, so expect a single track_shipment call to take up to ~30 seconds."
    ),
    lifespan=lifespan,
)


class TrackShipmentResult(BaseModel):
    summary: ShipmentSummary | None = None
    detail: ShipmentDetail | None = None
    trip: Trip | None = None
    error: str | None = None


@mcp.tool()
async def track_shipment(reference_number: str, ctx: Context) -> TrackShipmentResult:
    """Look up a shipment on DSV/DB Schenker's public tracking site.

    reference_number can be a waybill number, STT number, or other reference
    accepted by https://www.dsv.com/mydsv/tracking-public/ (e.g. "3476236157").

    Returns shipment status, route, event timeline, and package details, or
    a result with only `error` set if no shipment matches the reference.
    """
    app_ctx: AppContext = ctx.request_context.lifespan_context
    try:
        summary, detail, trip = await app_ctx.tracking_client.track(reference_number)
    except ShipmentNotFound:
        return TrackShipmentResult(error=f"No shipment found for reference {reference_number!r}")

    return TrackShipmentResult(summary=summary, detail=detail, trip=trip)


def main() -> None:
    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    mcp.run()


if __name__ == "__main__":
    main()
