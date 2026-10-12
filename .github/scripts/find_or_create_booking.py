"""Reuses the closest existing booking for the board, or creates a new one.

GET /bookings/me already returns only the caller's non-cancelled bookings
whose end_utc hasn't passed, ordered by start_utc ascending -- so the first
entry matching the selected board is already the closest one to "now"
(a currently active booking, whose start_utc is in the past, sorts ahead of
any merely-reserved future booking). Reusing it instead of always calling
POST /auto-bookings avoids piling up a fresh reservation on every workflow
run.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecw_client import request_json, write_github_output  # noqa: E402


def _findExistingBooking(backend_url: str, api_key: str, board_name: str) -> dict | None:
    bookings = request_json(
        f"{backend_url}/bookings/me",
        api_key,
        params={"page_no": "1", "page_size": "100"},
    )
    for booking in bookings:
        if str(booking.get("board_name", "")).lower() == board_name.lower():
            return booking
    return None


def _createBooking(backend_url: str, api_key: str, board_name: str) -> dict:
    return request_json(
        f"{backend_url}/auto-bookings",
        api_key,
        method="POST",
        params={"board_name": board_name},
    )


def main() -> None:
    backend_url = os.environ["ECW_BACKEND_URL"].rstrip("/")
    api_key = os.environ["ECW_API_KEY"]
    board_name = os.environ["ECW_BOARD_NAME"]

    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)

    existing = _findExistingBooking(backend_url, api_key, board_name)
    if existing is not None:
        booking = existing
        print(f"Reusing existing booking {booking.get('id')} for {board_name}")
    else:
        booking = _createBooking(backend_url, api_key, board_name)
        print(f"Created booking: {booking.get('id')}")

    (artifact_dir / "booking.json").write_text(
        json.dumps(booking, indent=2) + "\n", encoding="utf-8"
    )

    booking_id = booking.get("id")
    if not booking_id:
        raise SystemExit("Booking response is missing id.")

    write_github_output("booking_id", str(booking_id))


if __name__ == "__main__":
    main()
