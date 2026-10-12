"""Registers a session-activation trigger so ECW wakes the "Stage 2" workflow
the moment this booking becomes active, instead of a runner sitting there
polling for it (that's what the plain `wait` job in the main
ci-job-smoke.yml pipeline does instead -- pick one pattern, not both).

PUT /v1/ci/bookings/{booking_id}/activation-trigger

ECW injects booking_id/board_id/board_type_id/board_name/starts_at/ends_at as
workflow_dispatch inputs when it fires Stage 2; this script adds
run_id/sha/backend_url via inputs_extra so that triggered run can fetch this
run's firmware artifact, check out the same commit, and talk to the same
backend.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecw_client import request_json  # noqa: E402


def main() -> None:
    backend_url = os.environ["ECW_BACKEND_URL"].rstrip("/")
    api_key = os.environ["ECW_API_KEY"]
    booking_id = int(os.environ["ECW_BOOKING_ID"])

    dispatch_pat = os.environ.get("ECW_DISPATCH_PAT", "")
    if not dispatch_pat:
        raise SystemExit(
            "Missing ECW_DISPATCH_PAT repository secret (fine-grained PAT, "
            "Actions: Read and write -- see docs/07-trigger-mode.md)."
        )

    body = {
        "repository": os.environ["GITHUB_REPOSITORY"],
        "workflow": os.environ.get("ECW_ACTIVE_WORKFLOW", "ci-job-trigger-stage2.yml"),
        "git_ref": os.environ.get("ECW_ACTIVE_REF") or os.environ["GITHUB_REF_NAME"],
        "credential": dispatch_pat,
        "inputs_extra": {
            "run_id": os.environ["GITHUB_RUN_ID"],
            "sha": os.environ["GITHUB_SHA"],
            "backend_url": backend_url,
        },
    }

    # Override the GitHub REST base for GHES or local testing against a mock.
    dispatch_api_base = os.environ.get("ECW_DISPATCH_API_BASE", "")
    if dispatch_api_base:
        body["api_base_url"] = dispatch_api_base

    trigger = request_json(
        f"{backend_url}/v1/ci/bookings/{booking_id}/activation-trigger",
        api_key,
        method="PUT",
        body=body,
        timeout=30,
    )

    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)
    (artifact_dir / "activation-trigger.json").write_text(
        json.dumps(trigger, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Registered activation trigger {trigger.get('id')} "
        f"for booking {booking_id} -> {body['repository']} "
        f"({body['workflow']}@{body['git_ref']}), status={trigger.get('status')}"
    )


if __name__ == "__main__":
    main()
