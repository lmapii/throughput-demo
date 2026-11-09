#!/usr/bin/env python3
"""Fetches the ECW results of one ci run and renders them as one HTML report.

Covers every Stage 2 run (one per board) that the ci run triggered, and lists
boards that were reserved but have no Stage 2 run (yet). Needs the `gh` CLI
(authenticated). Stdlib only.

    # latest ci run on the current branch that reserved ECW boards
    python3 scripts/ecw_results.py

    # a specific ci run
    python3 scripts/ecw_results.py 42643319065

Every file in the artifacts is rendered, without knowing its schema: JSON is
pretty-printed (collapsible), text/logs inline, images embedded, zips unpacked
recursively. Files named `ci-job-<label>-<kind>.*` are grouped per CI job, and
`*-final.json` / `*-results.json` feed a status table at the top.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import mimetypes
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

CI_WORKFLOW = "ci.yml"
STAGE2_WORKFLOW = "ci-job-trigger-stage2.yml"
RESERVE_JOB_SUFFIX = " / Reserve & register trigger"
REPO_ROOT = Path(__file__).resolve().parent.parent
JOB_FILE_RE = re.compile(r"^ci-job-(?P<label>.+?)-(?P<kind>created|final|logs|results|artifacts)\.\w+$")
TEXT_SUFFIXES = {".txt", ".log", ".md", ".csv", ".hex", ".yml", ".yaml", ".xml", ".ini", ".cfg"}
MAX_TEXT_BYTES = 512 * 1024


# --------------------------------------------------------------------- gh / GitHub

def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def gh_json(*args: str):
    return json.loads(gh(*args))


def current_repo() -> str:
    return gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner").strip()


def current_branch() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def workflow_runs(repo: str, workflow: str, query: str) -> list[dict]:
    return gh_json("api", f"repos/{repo}/actions/workflows/{workflow}/runs?{query}").get("workflow_runs", [])


def reserved_boards(repo: str, ci_run_id: int | str) -> list[str]:
    """Boards whose Stage 1 reserve job succeeded in this ci run (taken from the job name,
    whose matrix tuple ends with ecw_board_name)."""
    jobs = gh_json("api", f"repos/{repo}/actions/runs/{ci_run_id}/jobs?per_page=100").get("jobs", [])
    boards = []
    for job in jobs:
        name = job.get("name", "")
        if name.endswith(RESERVE_JOB_SUFFIX) and job.get("conclusion") == "success":
            tuple_part = name[: -len(RESERVE_JOB_SUFFIX)]
            boards.append(tuple_part.removeprefix("ecw (").removesuffix(")").rsplit(", ", 1)[-1])
    return boards


def latest_ecw_ci_run(repo: str, branch: str) -> dict:
    """Latest ci run on the branch in which at least one board was reserved."""
    for run in workflow_runs(repo, CI_WORKFLOW, f"branch={branch}&per_page=20"):
        if reserved_boards(repo, run["id"]):
            return run
    raise SystemExit(f"No ci run on '{branch}' among the latest 20 reserved an ECW board.")


def stage1_run_of(repo: str, run: dict) -> str | None:
    """The ci run id a Stage 2 run was dispatched for (run-name, else its log)."""
    match = re.search(r"\brun (\d+)\)", run.get("display_title", ""))
    if match:
        return match.group(1)
    # older runs have no run-name: the Announce step echoes "stage 1 run = <id>"
    jobs = gh_json("api", f"repos/{repo}/actions/runs/{run['id']}/jobs").get("jobs", [])
    for job in jobs:
        if job.get("name") == "Upload":
            log = subprocess.run(
                ["gh", "api", f"repos/{repo}/actions/jobs/{job['id']}/logs"],
                capture_output=True, text=True,
            ).stdout
            found = re.search(r"stage 1 run = (\d+)", log)
            return found.group(1) if found else None
    return None


def download(repo: str, run_id: int, dest: Path) -> Path:
    target = dest / str(run_id)
    if target.exists() and any(target.iterdir()):
        print(f"  run {run_id}: using cached download in {target}")
        return target
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["gh", "run", "download", str(run_id), "--repo", repo, "--dir", str(target)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  run {run_id}: no artifacts ({result.stderr.strip()})")
    else:
        print(f"  run {run_id}: downloaded to {target}")
    return target


# --------------------------------------------------------------------- rendering

def esc(value: object) -> str:
    return html.escape(str(value))


def render_json(data: object) -> str:
    return f"<pre class='json'>{esc(json.dumps(data, indent=2, ensure_ascii=False))}</pre>"


def render_bytes(name: str, data: bytes, depth: int = 0) -> str:
    """Renders any file content, generically, by type."""
    suffix = Path(name).suffix.lower()
    if suffix == ".zip" and depth < 3:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                parts = [
                    file_block(info.filename, archive.read(info), depth + 1)
                    for info in archive.infolist() if not info.is_dir()
                ]
            return "<div class='zip'>" + "".join(parts) + "</div>"
        except zipfile.BadZipFile:
            pass
    if suffix == ".json":
        try:
            return render_json(json.loads(data.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    mime = mimetypes.guess_type(name)[0] or ""
    if mime.startswith("image/"):
        return f"<img src='data:{mime};base64,{base64.b64encode(data).decode()}' alt='{esc(name)}'>"
    if not data:
        return "<p class='warn'>empty file (0 bytes)</p>"
    if suffix in TEXT_SUFFIXES or b"\0" not in data[:4096]:
        text = data[:MAX_TEXT_BYTES].decode("utf-8", errors="replace")
        more = f"\n… truncated ({len(data)} bytes total)" if len(data) > MAX_TEXT_BYTES else ""
        return f"<pre>{esc(text + more)}</pre>"
    return f"<p class='muted'>binary, {len(data)} bytes</p>"


def file_block(name: str, data: bytes, depth: int = 0, open_: bool = False) -> str:
    size = f"{len(data):,} B"
    flag = " class='empty'" if not data else ""
    return (
        f"<details{' open' if open_ else ''}><summary{flag}><code>{esc(name)}</code>"
        f"<span class='muted'> · {size}</span></summary>{render_bytes(name, data, depth)}</details>"
    )


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def status_badge(status: str) -> str:
    kind = "ok" if status == "succeeded" else "bad" if status else "muted"
    return f"<span class='badge {kind}'>{esc(status or 'n/a')}</span>"


def summarize_job(files: dict[str, Path]) -> dict:
    final = load_json(files["final"]) if "final" in files else None
    results = load_json(files["results"]) if "results" in files else None
    status = str((final or {}).get("status") or (results or {}).get("status") or "")
    commands = []
    for cmd_id, res in ((results or {}).get("results") or {}).items():
        output = res.get("output") or {}
        note = ""
        if isinstance(output, dict) and output.get("size_bytes") == 0:
            note = "empty output (0 bytes)"
        commands.append((cmd_id, bool(res.get("success")), res.get("error"), note))
    return {"id": (final or results or {}).get("id"), "status": status, "commands": commands}


def board_of(run_dir: Path, run: dict) -> str:
    for summary in run_dir.rglob("ci-job-summary.md"):
        found = re.search(r"^- Board: (.+)$", summary.read_text(encoding="utf-8"), re.M)
        if found:
            return found.group(1).strip()
    match = re.match(r"ECW Stage 2: (.+?) \(booking", run.get("display_title", ""))
    return match.group(1) if match else "unknown board"


def render_run(run: dict, run_dir: Path) -> tuple[str, str]:
    board = board_of(run_dir, run)
    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    jobs: dict[str, dict[str, Path]] = {}
    other: list[Path] = []
    for path in files:
        match = JOB_FILE_RE.match(path.name)
        if match:
            jobs.setdefault(match["label"], {})[match["kind"]] = path
        else:
            other.append(path)

    rows, sections = [], []
    for label, kinds in jobs.items():
        info = summarize_job(kinds)
        cmd_cells = "".join(
            f"<li>{'✅' if ok else '❌'} <code>{esc(cmd)}</code>"
            f"{f' — <span class=bad>{esc(err)}</span>' if err else ''}"
            f"{f' — <span class=warn>{esc(note)}</span>' if note else ''}</li>"
            for cmd, ok, err, note in info["commands"]
        )
        rows.append(
            f"<tr><td><a href='#r{run['id']}-{esc(label)}'>{esc(label)}</a></td><td>{esc(info['id'])}</td>"
            f"<td>{status_badge(info['status'])}</td><td><ul>{cmd_cells}</ul></td></tr>"
        )
        order = ["final", "results", "logs", "artifacts", "created"]
        blocks = "".join(
            file_block(kinds[k].name, kinds[k].read_bytes(), open_=(k == "logs"))
            for k in order if k in kinds
        )
        sections.append(f"<h4 id='r{run['id']}-{esc(label)}'>{esc(label)} {status_badge(info['status'])}</h4>{blocks}")

    if other:
        sections.append("<h4>other files</h4>" + "".join(
            file_block(str(p.relative_to(run_dir)), p.read_bytes(), open_=p.suffix == ".md") for p in other
        ))
    if not files:
        sections.append("<p class='warn'>no artifacts downloaded for this run</p>")

    overall = "succeeded" if run.get("conclusion") == "success" else str(run.get("conclusion") or run.get("status"))
    anchor = f"run-{run['id']}"
    toc = f"<li><a href='#{anchor}'>{esc(board)}</a> {status_badge(overall)} <span class='muted'>run {run['id']} · {esc(run.get('created_at', ''))}</span></li>"
    body = f"""
<section id='{anchor}'>
  <h2>{esc(board)} {status_badge(overall)}</h2>
  <p class='muted'><a href='{esc(run.get('html_url', ''))}'>Stage 2 run {run['id']}</a>
     · {esc(run.get('head_branch', ''))} @ <code>{esc(str(run.get('head_sha', ''))[:10])}</code>
     · {esc(run.get('created_at', ''))}</p>
  <table><tr><th>job</th><th>ECW id</th><th>status</th><th>commands</th></tr>{''.join(rows)}</table>
  {''.join(sections)}
</section>"""
    return toc, body


CSS = """
:root{--bg:#fff;--fg:#1d1f23;--muted:#6b7280;--line:#e5e7eb;--code:#f6f8fa;--ok:#15803d;--bad:#b91c1c;--warn:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#16181d;--fg:#e6e6e6;--muted:#9aa0a6;--line:#2d3139;--code:#1f2228;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24}}
body{background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:24px 16px}
a{color:inherit}code,pre{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
pre{background:var(--code);padding:10px;border-radius:6px;overflow:auto;max-height:480px}
table{border-collapse:collapse;width:100%;margin:8px 0 16px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
td ul{margin:0;padding-left:0;list-style:none}
details{border:1px solid var(--line);border-radius:6px;margin:6px 0;padding:4px 10px}summary{cursor:pointer}
.zip{padding-left:12px;border-left:2px solid var(--line)}
section{border-top:2px solid var(--line);margin-top:32px}
img{max-width:100%;border-radius:4px}
.muted{color:var(--muted)}.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.badge{font-size:12px;padding:1px 8px;border-radius:10px;border:1px solid currentColor;vertical-align:middle}
summary.empty code{color:var(--warn)}
"""


# --------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ci_run", nargs="?", help="ci run id (default: latest one on the branch that reserved boards)")
    parser.add_argument("--branch", help="branch for the default ci run (default: current)")
    parser.add_argument("--repo", help="owner/name (default: from gh)")
    parser.add_argument("--out", type=Path, help="report path (default: _results/ecw-report-<ci run>.html)")
    args = parser.parse_args()

    repo = args.repo or current_repo()
    dest = REPO_ROOT / "_results" / "ecw"

    if args.ci_run:
        ci_run = gh_json("api", f"repos/{repo}/actions/runs/{args.ci_run}")
    else:
        ci_run = latest_ecw_ci_run(repo, args.branch or current_branch())
    ci_id = str(ci_run["id"])
    boards = reserved_boards(repo, ci_id)

    # Stage 2 runs are dispatched by ECW after the ci run started, on the PR's head branch
    candidates = workflow_runs(
        repo, STAGE2_WORKFLOW,
        f"event=workflow_dispatch&branch={ci_run['head_branch']}&created=>={ci_run['created_at']}&per_page=100",
    )
    runs = [run for run in candidates if stage1_run_of(repo, run) == ci_id]
    runs.sort(key=lambda run: run["created_at"])

    print(f"{repo}: ci run {ci_id} ({ci_run['head_branch']}, {ci_run['created_at']})")
    print(f"  reserved boards: {', '.join(boards) or 'none'}; Stage 2 runs: {len(runs)}")

    tocs, bodies, seen = [], [], set()
    for run in runs:
        run_dir = download(repo, run["id"], dest)
        seen.add(board_of(run_dir, run))
        toc, body = render_run(run, run_dir)
        tocs.append(toc)
        bodies.append(body)
    for board in boards:
        if board not in seen:
            print(f"  {board}: no Stage 2 run yet (booking not started, board occupied?) - rerun later")
            tocs.append(
                f"<li>{esc(board)} <span class='badge warn'>no Stage 2 run yet</span> "
                "<span class='muted'>reserved, but ECW has not started the session yet "
                "(board occupied or booking starts later) - rerun the script later</span></li>"
            )

    title = f"ECW results · ci run {ci_id}"
    page = f"""<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title>
<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head><body>
<h1>{esc(title)}</h1>
<p class='muted'><a href='{esc(ci_run.get('html_url', ''))}'>ci run {ci_id}</a> · {esc(repo)}
   · {esc(ci_run.get('head_branch', ''))} @ <code>{esc(str(ci_run.get('head_sha', ''))[:10])}</code>
   · {esc(ci_run.get('created_at', ''))} · generated {datetime.now():%Y-%m-%d %H:%M}</p>
<ul>{''.join(tocs)}</ul>{''.join(bodies)}</body></html>"""

    out = args.out or REPO_ROOT / "_results" / f"ecw-report-{ci_id}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"report: {out}")


if __name__ == "__main__":
    sys.exit(main())
