"""Polls a booking until it becomes active, or exits once it can never be."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecw_client import request_json  # noqa: E402


def _parseDatetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> None:
    backend_url = os.environ["ECW_BACKEND_URL"].rstrip("/")
    api_key = os.environ["ECW_API_KEY"]
    booking_id = os.environ["ECW_BOOKING_ID"]
    timeout_seconds = int(os.environ["ECW_BOOKING_WAIT_TIMEOUT_SECONDS"])

    deadline = time.monotonic() + timeout_seconds
    print(f"Waiting for booking {booking_id} to become active...")

    while True:
        booking = request_json(
            f"{backend_url}/booking",
            api_key,
            params={"booking_id": booking_id},
        )
        start = _parseDatetime(booking["start_utc"])
        end = _parseDatetime(booking["end_utc"])
        status = str(booking.get("status", "")).lower()
        now = datetime.now(timezone.utc)

        active = start <= now < end and status in {"active", "confirmed"}
        if active:
            print(f"Booking {booking_id} is active.")
            return

        if now >= end:
            raise SystemExit(f"Booking {booking_id} ended before it became active.")
        if time.monotonic() > deadline:
            raise SystemExit(
                f"Booking {booking_id} did not become active within "
                f"{timeout_seconds} seconds."
            )

        wait_seconds = min(max((start - now).total_seconds() + 0.5, 1), 5)
        print(
            f"Booking status={status}, starts={start.isoformat()}, "
            f"waiting {wait_seconds:.1f}s..."
        )
        time.sleep(wait_seconds)


if __name__ == "__main__":
    main()
