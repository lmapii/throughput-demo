"""Downloads each CI job's collected artifacts as a zip bundle."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecw_client import request_bytes  # noqa: E402


def main() -> None:
    backend_url = os.environ["ECW_BACKEND_URL"].rstrip("/")
    api_key = os.environ["ECW_API_KEY"]
    job_ids = json.loads(os.environ["ECW_CI_JOB_IDS"])
    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)

    for label, job_id in job_ids.items():
        try:
            data = request_bytes(
                f"{backend_url}/v1/ci/jobs/{job_id}/artifacts.zip",
                api_key,
                timeout=30,
            )
        except urllib.error.HTTPError as exc:
            print(f"WARN: failed to download artifacts for {label} job {job_id}: {exc}")
            continue

        out_path = artifact_dir / f"ci-job-{label}-artifacts.zip"
        out_path.write_bytes(data)
        print(f"Downloaded {label} CI job {job_id} artifacts -> {out_path}")


if __name__ == "__main__":
    main()
