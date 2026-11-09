"""Finds a booking for the board that is usable now (or soon), or creates one.

In order:

1. One of the caller's bookings for the board is active right now -> reuse it.
2. Otherwise, if any active board of the board type is free right now (no
   booked slot overlapping "now"), reserve it via POST /auto-bookings.
3. Otherwise (all boards occupied), reuse the caller's earliest upcoming
   booking for the board that starts within ECW_BOOKING_MAX_LEAD_MINUTES.
4. Otherwise, auto-book the next free slot -- and, if even that starts later
   than ECW_BOOKING_MAX_LEAD_MINUTES, cancel it again and fail, so the run
   never leaves a far-future booking (with a pending trigger) behind.

GET /bookings/me returns only the caller's non-cancelled bookings whose
end_utc hasn't passed, ordered by start_utc ascending.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecw_client import request_json, write_github_output  # noqa: E402

ARTIFACT_DIR = Path("artifacts")


def _parseDatetime(value: str) -> datetime:
    # all requests below pass tz=UTC, so a naive timestamp is UTC
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _isoUtc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bookingStart(booking: dict) -> datetime:
    # /bookings/me returns start_utc, /auto-bookings returns start_time
    return _parseDatetime(booking.get("start_utc") or booking["start_time"])


def _bookingEnd(booking: dict) -> datetime:
    return _parseDatetime(booking.get("end_utc") or booking["end_time"])


def _dump(name: str, data: object) -> None:
    (ARTIFACT_DIR / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _myBookings(backend_url: str, api_key: str, board_name: str) -> list[dict]:
    bookings = request_json(
        f"{backend_url}/bookings/me",
        api_key,
        params={"page_no": "1", "page_size": "100"},
    )
    _dump("my-bookings.json", bookings)
    return [
        booking
        for booking in bookings
        if str(booking.get("board_name", "")).lower() == board_name.lower()
    ]


def _isBoardTypeFreeNow(backend_url: str, api_key: str, board_type_id: int, now: datetime) -> bool:
    boards = request_json(f"{backend_url}/boards/", api_key, params={"page_no": "1", "page_size": "100"})
    candidates = {
        int(board["id"])
        for board in boards
        if int(board.get("board_type_id", -1)) == board_type_id and board.get("active") is not False
    }
    if not candidates:
        raise SystemExit(f"No active board of board type {board_type_id} exists.")

    # a one-minute window starting now; /booked-slots returns every booking overlapping it
    slots = request_json(
        f"{backend_url}/booked-slots",
        api_key,
        params={
            "board_type_id": str(board_type_id),
            "start_iso": _isoUtc(now),
            "end_iso": _isoUtc(now + timedelta(minutes=1)),
            "tz": "UTC",
        },
    )
    _dump("booked-slots.json", slots)

    # shape: {"bookings": {"<board_id>": [{start_time, end_time, tz}, ...]}};
    # a board without bookings in the window may be missing from the map
    occupied = set()
    for board_id, board_slots in (slots.get("bookings") or {}).items():
        for slot in board_slots or []:
            if _parseDatetime(slot["start_time"]) <= now < _parseDatetime(slot["end_time"]):
                occupied.add(int(board_id))
                break

    free = sorted(candidates - occupied)
    print(f"Boards of type {board_type_id}: {sorted(candidates)}, occupied now: {sorted(occupied)}")
    return bool(free)


def _createBooking(backend_url: str, api_key: str, board_name: str) -> dict:
    return request_json(
        f"{backend_url}/auto-bookings",
        api_key,
        method="POST",
        params={"board_name": board_name},
    )


def _cancelBooking(backend_url: str, api_key: str, booking_id: object) -> None:
    request_json(f"{backend_url}/cancel-booking", api_key, params={"booking_id": str(booking_id)})


def _selectBooking(backend_url: str, api_key: str, board_name: str, board_type_id: int, max_lead: timedelta) -> dict:
    now = datetime.now(timezone.utc)
    horizon = now + max_lead
    mine = _myBookings(backend_url, api_key, board_name)

    # 1. already active
    for booking in mine:
        if _bookingStart(booking) <= now < _bookingEnd(booking):
            print(f"Reusing booking {booking.get('id')}: active now (until {_isoUtc(_bookingEnd(booking))})")
            return booking

    # 2. free right now -> reserve
    if _isBoardTypeFreeNow(backend_url, api_key, board_type_id, now):
        booking = _createBooking(backend_url, api_key, board_name)
        print(f"Created booking {booking.get('id')}: board free now (starts {_isoUtc(_bookingStart(booking))})")
        return booking

    # 3. occupied -> an upcoming booking of ours within the allowed lead time
    for booking in mine:
        start = _bookingStart(booking)
        if now < start <= horizon:
            print(f"Reusing booking {booking.get('id')}: board occupied, ours starts {_isoUtc(start)}")
            return booking
    if mine:
        print(
            "Ignoring existing booking(s) starting after the "
            f"{max_lead} lead time: {[(b.get('id'), _isoUtc(_bookingStart(b))) for b in mine]}"
        )

    # 4. next free slot, but only if it is within the lead time
    booking = _createBooking(backend_url, api_key, board_name)
    start = _bookingStart(booking)
    if start > horizon:
        _cancelBooking(backend_url, api_key, booking.get("id"))
        raise SystemExit(
            f"Board '{board_name}' is occupied; the next free slot starts {_isoUtc(start)}, later than "
            f"ECW_BOOKING_MAX_LEAD_MINUTES ({max_lead}) from now. Cancelled booking {booking.get('id')} again."
        )
    print(f"Created booking {booking.get('id')}: board occupied, next free slot starts {_isoUtc(start)}")
    return booking


def main() -> None:
    backend_url = os.environ["ECW_BACKEND_URL"].rstrip("/")
    api_key = os.environ["ECW_API_KEY"]
    board_name = os.environ["ECW_BOARD_NAME"]
    board_type_id = int(os.environ["ECW_BOARD_TYPE_ID"])
    max_lead = timedelta(minutes=float(os.environ.get("ECW_BOOKING_MAX_LEAD_MINUTES") or "30"))

    ARTIFACT_DIR.mkdir(exist_ok=True)

    booking = _selectBooking(backend_url, api_key, board_name, board_type_id, max_lead)
    _dump("booking.json", booking)

    booking_id = booking.get("id")
    if not booking_id:
        raise SystemExit("Booking response is missing id.")

    write_github_output("booking_id", str(booking_id))


if __name__ == "__main__":
    main()
