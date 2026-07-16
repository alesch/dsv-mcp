#!/usr/bin/env -S uv run --project /home/alex/dev/Sendify/mcp python
"""Standalone CLI to exercise dsv_tracking.browser_client directly.

Usage:
    uv run python scripts/try_tracking.py <reference_number> [--show]

--show launches a headed (visible) browser instead of headless, useful for
debugging the cookie-consent banner or the proof-of-work challenge visually.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dsv_tracking.browser_client import TrackingClient
from dsv_tracking.models import ShipmentNotFound


async def main() -> int:
    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("reference_number")
    parser.add_argument("--show", action="store_true", help="run with a visible browser window")
    args = parser.parse_args()

    async with TrackingClient(headless=not args.show) as client:
        try:
            summary, detail, trip = await client.track(args.reference_number)
        except ShipmentNotFound:
            print(f"No shipment found for reference {args.reference_number!r}")
            return 1

        print(f"STT number:      {summary.stt}")
        print(f"Transport mode:  {summary.transport_mode}")
        print(f"Route:           {summary.from_location} -> {summary.to_location}")
        print(
            f"Progress:        {summary.percentage_progress}% "
            f"(last event: {summary.last_event_code})"
        )
        print()
        print(f"Status:          {detail.active_step}")
        print(f"Steps:           {' -> '.join(detail.steps)}")
        print(f"Waybill numbers: {', '.join(detail.waybill_numbers)}")
        print(f"Pieces / weight: {detail.pieces} / {detail.weight_value} {detail.weight_unit}")
        print(f"Collect from:    {detail.collect_from}")
        print(f"Deliver to:      {detail.deliver_to}")
        print(f"Delivery est.:   {detail.delivery_date_estimated}")
        print()
        print("Events:")
        for event in detail.events:
            print(
                f"  {event.date}  {event.code:5s}  {event.comment or '':20s}  {event.location_name}"
            )

        if trip is not None:
            print()
            print(f"Trip points: {len(trip.points)} (delivered: {trip.is_delivered})")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
