"""Polls each CI job to a terminal status and writes results/summary artifacts."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecw_client import request_json  # noqa: E402

# Real terminal statuses from JobStatus in api/ci_jobs.py -- there is no
# "passed" value, jobs that finish successfully report "succeeded".
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "invalid"}


def main() -> None:
    backend_url = os.environ["ECW_BACKEND_URL"].rstrip("/")
    api_key = os.environ["ECW_API_KEY"]
    job_ids = json.loads(os.environ["ECW_CI_JOB_IDS"])
    timeout_seconds = int(os.environ["ECW_JOB_WAIT_TIMEOUT_SECONDS"])
    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)

    summary_lines = ["# ECW CI Job Smoke Result", ""]
    any_failed = False

    for label, job_id in job_ids.items():
        deadline = time.monotonic() + timeout_seconds
        final_job = None

        while True:
            job = request_json(f"{backend_url}/v1/ci/jobs/{job_id}", api_key)
            status = str(job.get("status", "")).lower()
            print(f"{label} CI job {job_id} status: {status}")

            if status in TERMINAL_STATUSES:
                final_job = job
                break

            if time.monotonic() > deadline:
                final_job = job
                print(f"{label} CI job {job_id} did not finish within {timeout_seconds}s.")
                break

            time.sleep(2)

        logs = request_json(f"{backend_url}/v1/ci/jobs/{job_id}/logs", api_key)
        results = request_json(f"{backend_url}/v1/ci/jobs/{job_id}/results", api_key)

        (artifact_dir / f"ci-job-{label}-final.json").write_text(
            json.dumps(final_job, indent=2) + "\n", encoding="utf-8"
        )
        (artifact_dir / f"ci-job-{label}-logs.json").write_text(
            json.dumps(logs, indent=2) + "\n", encoding="utf-8"
        )
        (artifact_dir / f"ci-job-{label}-results.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8"
        )

        final_status = str(final_job.get("status", "timeout")).lower()
        summary_lines.append(f"- {label} job {job_id}: {final_status}")
        if final_status != "succeeded":
            any_failed = True
            print(f"FAIL: {label} CI job {job_id} finished with status {final_status}.")
        else:
            print(f"PASS: {label} CI job {job_id} succeeded.")

    summary_lines.extend(
        [
            "",
            f"- Booking ID: {os.environ.get('ECW_BOOKING_ID', '')}",
            f"- Board: {os.environ.get('ECW_BOARD_NAME', '')}",
            "",
        ]
    )
    (artifact_dir / "ci-job-summary.md").write_text(
        "\n".join(summary_lines), encoding="utf-8"
    )

    if any_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
