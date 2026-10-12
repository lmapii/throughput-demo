# .github/user/

Project-owned scripts and data that `ci-job-smoke.yml` and its
`.github/scripts/*.py` helpers read, instead of containing project-specific
logic themselves. The workflow is general-purpose -- same YAML for any
board, any build process, any set of CI jobs -- and should never need to
change; only the contents of this folder do.

> **Edit freely inside this folder.** Editing `ci-job-smoke.yml`'s
> existing steps or `.github/scripts/*.py` themselves is unsupported --
> see [docs/06-support-and-liability.md](../../docs/06-support-and-liability.md)
> before you do.

## build/build.sh

Required, executable. The workflow's `Build` job runs it after checkout and
nothing else -- no board, core, or compiler knowledge lives in the YAML.

Contract:
- Runs from the repository root (not from inside `build/`).
- Must leave exactly one `*.bin` file inside `./build/` (the repo-root
  build output directory -- unrelated to this `.github/user/build/` folder,
  which just holds the script itself). The whole `build/` directory is
  uploaded as the artifact and the `Upload` job finds that one file by
  extension, not by name, so call it whatever you want -- zero or more
  than one `.bin` file fails the `Upload` job with a clear error.

If this file is missing or not executable, the `Build` job fails immediately
with a clear message instead of silently doing nothing.

## jobs/

One JSON file per CI job to create against the booked board, each shaped as
`{request_id, name, duration_seconds, commands}` -- see `_COMMAND_REGISTRY`
in `ECW_Backend`'s `api/ci_jobs.py` for the valid `commands[].command`
names. `.github/scripts/create_jobs.py` reads every `*.json` file here, in
sorted filename order, and creates one CI job per file.

CI jobs run in the order they were created, so filenames use a leading
`NN_` ordering prefix (`01_wait.json`, `02_serial.json`, ...); the prefix is
stripped to make each job's label (used for artifact filenames and the
`ECW_CI_JOB_IDS` keys downstream). Add, remove, reorder, or edit a job by
adding/removing/renaming/editing a file here -- `create_jobs.py` never
needs to change.
