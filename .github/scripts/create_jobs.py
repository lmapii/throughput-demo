"""Creates the CI jobs defined as JSON files under .github/user/jobs/."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecw_client import request_json, write_github_env  # noqa: E402

# Job payloads are project-owned data, not workflow logic: each JSON file
# under .github/user/jobs/ is one CI job spec -- request_id/name/
# duration_seconds/commands, keyed by command names from the
# _COMMAND_REGISTRY in api/ci_jobs.py. This script never needs to change to
# add/edit/reorder a CI job, only the files in that folder do.
#
# CI jobs run in creation order, so files are read in sorted filename order
# and a leading "NN_" prefix (01_, 02_, ...) controls that order; the
# prefix itself is stripped to make the label used for artifact filenames
# and ECW_CI_JOB_IDS keys (e.g. "01_wait.json" -> "wait").
JOBS_DIR = Path(__file__).resolve().parents[1] / "user" / "jobs"


def _label(job_file: Path) -> str:
    stem = job_file.stem
    prefix, _, rest = stem.partition("_")
    return rest if prefix.isdigit() and rest else stem


def _loadJobSpecs() -> dict[str, dict]:
    job_files = sorted(JOBS_DIR.glob("*.json"))
    if not job_files:
        raise SystemExit(f"No CI job specs found under {JOBS_DIR}.")
    return {_label(job_file): json.loads(job_file.read_text(encoding="utf-8")) for job_file in job_files}


def main() -> None:
    backend_url = os.environ["ECW_BACKEND_URL"].rstrip("/")
    api_key = os.environ["ECW_API_KEY"]
    booking_id = int(os.environ["ECW_BOOKING_ID"])

    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)

    job_ids: dict[str, int] = {}
    for label, spec in _loadJobSpecs().items():
        payload = {"booking_id": booking_id, **spec}
        job = request_json(
            f"{backend_url}/v1/ci/jobs",
            api_key,
            method="POST",
            body=payload,
            timeout=30,
        )

        (artifact_dir / f"ci-job-{label}-created.json").write_text(
            json.dumps(job, indent=2) + "\n", encoding="utf-8"
        )

        job_id = job.get("id")
        if not job_id:
            raise SystemExit(f"{label} job creation response is missing id.")

        job_ids[label] = job_id
        print(f"Created {label} CI job: {job_id}")

    write_github_env("ECW_CI_JOB_IDS", json.dumps(job_ids))


if __name__ == "__main__":
    main()
