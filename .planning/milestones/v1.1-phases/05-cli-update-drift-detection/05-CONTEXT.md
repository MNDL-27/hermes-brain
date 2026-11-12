# Phase 05 — CLI Update Drift Detection

## Goal
Users on any install mode (uv / pip venv / pip user / git clone) can run `notion_brain update --check` and get exact installed-vs-latest drift plus a copy-pasteable upgrade command for their environment — without the tool ever mutating their install.

## Scope
Detects drift + instructs. Does not run any install or git pull.

## Requirements
- **UPD-01**: Print installed version and latest GitHub release; show drift.
- **UPD-02**: Print copy-pasteable upgrade command matching detected install mode.
- **UPD-03**: Integer-tuple SemVer comparison with pre-release ranking (1.10.0 > 1.9.0; 1.1.0 > 1.1.0b1).
- **UPD-04**: `--check` exits 0 (current) or 2 (drift); `--json` emits machine-readable payload.
- **UPD-05**: Detect + instruct only. No `pip install`, `git pull`, or venv mutation by this command.

## Current State
- `notion_brain/__main__.py:_cmd_update()` (lines 177–213) MUTATES — it calls `_checkout_tag_and_install()` which runs `git checkout`, `pip install -e`. Violates UPD-05.
- `notion_brain/bootstrap.py:_check_for_update()` (lines 642–656) — string-only drift detection, no pre-release ranking, no install mode detection, no JSON.
- `bootstrap.py:_find_latest_tag()` (lines 618–639) — already unauthenticated GitHub API call with 3s timeout, returns string. Reuse.

## Files Touched
- **New**: `notion_brain/update.py` — version parsing, install-mode detection, upgrade-command generation, JSON payload assembly.
- **Modified**: `notion_brain/__main__.py` — `_cmd_update` becomes detect+instruct only; add `--json`, `--check` exit codes; remove mutation paths (or gate them under a separate explicit command, e.g. `update --apply` — deferred, see below).
- **New**: `tests/test_update.py` — offline unit tests for semver parsing, comparison, install-mode detection, JSON payload.

## Out of Scope (deferred to Phase 06 or later)
- Commit-level drift (UPD-06): needs git plumbing beyond current `_check_for_update`.
- Release-notes URL banner (UPD-07): trivial, fold into Phase 06 if a single line.
- Cached background refresh on the provider (CHK-01..05): belongs to Phase 06 by design.

## Tests
Offline; monkeypatch `urllib.request.urlopen` for the GitHub call. Cover:
- `parse_semver("1.10.0") > parse_semver("1.9.0")` (integer-tuple beats naive string sort)
- `parse_semver("1.1.0") > parse_semver("1.1.0b1")` (release ranks above pre-release of same base)
- `detect_install_mode()` returns `"git_clone"` when `pip show` Location is the repo path; `"uv"` when venv path contains `/uv/`; `"pip_user"` when Location is under `~/.local/lib/...`; `"pip_venv"` otherwise
- `build_upgrade_command(mode, version)` returns the expected exact string per mode
- `check_for_update()` returns the structured payload (no mutation, no exception on network failure)
- `_cmd_update` with `--check --json` produces parseable JSON and exits 0 when current, 2 when drift

## Acceptance
- `uv run --no-sync pytest tests/test_update.py -v` passes
- `uv run --no-sync pytest -q` (excluding the 3 pre-existing hanging modules) still green
- `uv run --no-sync ruff check notion_brain tests` clean
- `uv run --no-sync mypy notion_brain tests` clean
- `notion_brain update --check` exits 0 or 2 with no network on cached result, prints human-readable drift + command
- `notion_brain update --check --json` exits 0 or 2, prints JSON, no mutation
