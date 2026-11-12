---
phase: 05-cli-update-drift-detection
plan: 01
subsystem: distribution
tags: [update, drift-detection, semver, cli]
requires-phase: null
provides-phase: 06
key-files:
  created:
    - notion_brain/update.py
    - tests/test_update.py
  modified:
    - notion_brain/__main__.py
    - tests/characterization/test_cli_contract.py
    - tests/test_packaging.py
---

# Phase 05 Plan 01 — CLI Update Drift Detection

## What Shipped

- `notion_brain/update.py` — new module exposing `parse_semver`, `compare_versions`, `detect_install_mode`, `build_upgrade_command`, `check_for_update`, `format_human`, `format_json`. Integer-tuple SemVer with pre-release ranking; release sorts above any pre-release of the same base.
- `notion_brain/__main__.py:_cmd_update` — slimmed to a thin wrapper over `notion_brain.update.check_for_update`. Detects drift, prints the report, exits 0 (no drift) or 2 (drift). Added `--json` flag. Removed `_git_pull_and_install`, `_checkout_tag_and_install`, `_reinstall` — the command now never mutates the running environment (UPD-05).
- `tests/test_update.py` — 26 offline tests covering semver ranking, mode detection, JSON payload round-trip, CLI exit codes, and the no-mutation guarantee.
- `tests/characterization/test_cli_contract.py` — renamed `test_update_command_checks_tag_then_installs` to `test_update_command_detects_drift_without_mutating`; rewritten to assert the new bare-`update` contract: exit 2 on drift, prints `UPDATE AVAILABLE`, never invokes `pip install`/`git pull`. Read-only `pip show` for install-mode detection is allowed.
- `tests/test_packaging.py` — removed leftover `http.client`, `socket`, and duplicate `pytest` imports from the Phase 04 offline-mode patch.

## Verification

| Check | Result |
|-------|--------|
| `tests/test_update.py` — 26 tests | **all passed** (0.84s) |
| `tests/characterization/test_cli_contract.py` — 8 tests | **all passed** (3.06s) |
| `tests/test_packaging.py` — 4 tests | **3 passed, 1 skipped** (offline) |
| `notion_brain/update.py` inline verifier (semver + commands) | **OK** |
| `notion_brain/__main__.py` refactor check (no mutating calls, both flags, delegation) | **OK** |
| `uv run --no-sync ruff check notion_brain tests` | **clean** |
| `uv run --no-sync mypy notion_brain tests` | **clean** (30 source files) |
| `python -m notion_brain update --check --json` (live, offline-tolerant) | **valid JSON, exit 0** |
| Regression sweep on 7 pre-existing fast test files | **all pass** |

## Per-Mode Upgrade Commands (UPD-02)

| Install mode | Command |
|--------------|---------|
| `uv` | `uv pip install --upgrade hermes-brain==<v>` |
| `pip_venv` | `pip install --upgrade hermes-brain==<v>` |
| `pip_user` | `pip install --user --upgrade hermes-brain==<v>` |
| `git_clone` | `git -C <repo> fetch --tags && git -C <repo> checkout v<v> && python -m pip install --upgrade --force-reinstall <repo>` |
| `unknown` | falls back to `pip install --upgrade hermes-brain==<v>` (safe default) |

## Acceptance Criteria

- UPD-01: `notion_brain update --check` prints installed and latest versions, drift line when versions differ. **Met.**
- UPD-02: Per-mode upgrade command table generated. **Met.**
- UPD-03: Integer-tuple SemVer with pre-release ranking. `1.10.0 > 1.9.0`, `1.1.0 > 1.1.0b1`. **Met.**
- UPD-04: `--check` exits 0 (current) or 2 (drift); `--json` emits parseable JSON. **Met.**
- UPD-05: No `pip install`, `git pull`, `git checkout`, or venv mutation by `update` (verified by `test_update_command_detects_drift_without_mutating`). **Met.**

## Hand-off

Phase 05 complete. Phase 06 (Cached Non-Blocking Auto-Update Check, CHK-01..CHK-05) is the natural successor — it reuses `notion_brain.update.check_for_update` as the refresh engine and adds a `$HERMES_HOME/.update_cache.json` with TTL-based background refresh on the `notion-brain-sync-worker` thread.
