"""Selects a board type whose name contains BOARD_NAME and writes board_name."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecw_client import request_json, write_github_output  # noqa: E402


def main() -> None:
    backend_url = os.environ["ECW_BACKEND_URL"].rstrip("/")
    api_key = os.environ["ECW_API_KEY"]
    search = os.environ["BOARD_NAME"].lower()

    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)

    board_types_response = request_json(
        f"{backend_url}/board_types",
        api_key,
        params={"page_no": "1", "page_size": "100"},
    )
    (artifact_dir / "board-types.json").write_text(
        json.dumps(board_types_response, indent=2) + "\n", encoding="utf-8"
    )

    board_types = board_types_response
    if isinstance(board_types, dict):
        board_types = (
            board_types.get("items")
            or board_types.get("board_types")
            or board_types.get("results")
            or board_types.get("data")
            or []
        )

    matches = [
        board_type
        for board_type in board_types
        if search in str(board_type.get("board_name", "")).lower()
    ]
    if not matches:
        raise SystemExit(f"No board type found containing '{search}'.")

    selected = matches[0]
    board_name = selected.get("board_name", "")
    if not board_name:
        raise SystemExit("Selected board type did not include board_name.")

    write_github_output("board_name", board_name)
    print(f"Selected board type: {board_name} (id: {selected.get('id')})")


if __name__ == "__main__":
    main()
