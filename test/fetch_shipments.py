#!/usr/bin/env -S uv run --project /home/alex/dev/Sendify/mcp python
"""Fetch multiple shipments sequentially and save results to a JSON file.

Usage:
    ./scripts/fetch_shipments.py [-i INPUT] [-o OUTPUT] [reference_number ...]

Reference numbers come from positional arguments if given, otherwise from
--input (default scripts/reference_numbers.txt, one reference per line;
non-numeric lines such as a header are ignored). Each one is looked up
sequentially through the same TrackingClient used by try_tracking.py, so
lookups stay serialized and paced like a single human user -- this is not
parallelized on purpose. Results are written as a JSON array to --output
(default: shipments.json in the repo root).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dsv_tracking.browser_client import TrackingClient
from dsv_tracking.models import ShipmentNotFound

DEFAULT_INPUT = Path(__file__).resolve().parent / "reference_numbers.txt"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "shipments.json"


def read_reference_numbers(path: Path) -> list[str]:
    refs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or not line[0].isdigit():
            continue
        refs.append(line)
    return refs


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_numbers", nargs="*")
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--show", action="store_true", help="run with a visible browser window")
    args = parser.parse_args()

    reference_numbers = args.reference_numbers or read_reference_numbers(args.input)
    if not reference_numbers:
        print("No reference numbers given.", file=sys.stderr)
        return 1

    results = []
    async with TrackingClient(headless=not args.show) as client:
        for i, ref in enumerate(reference_numbers, start=1):
            print(f"[{i}/{len(reference_numbers)}] Looking up {ref} ...", file=sys.stderr)
            try:
                summary, detail, trip = await client.track(ref)
            except ShipmentNotFound:
                print("  -> not found", file=sys.stderr)
                results.append({"reference_number": ref, "error": "not found"})
                continue
            except Exception as exc:  # noqa: BLE001 - keep the batch going on a per-item failure
                print(f"  -> error: {exc}", file=sys.stderr)
                results.append({"reference_number": ref, "error": str(exc)})
                continue

            print(f"  -> {detail.active_step}", file=sys.stderr)
            results.append(
                {
                    "reference_number": ref,
                    "summary": summary.model_dump(),
                    "detail": detail.model_dump(),
                    "trip": trip.model_dump() if trip is not None else None,
                }
            )

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {len(results)} results to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
