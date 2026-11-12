---
phase: 07-update-ux-commit-level-drift-release-notes-link
plan: "01"
subsystem: update-ux
tags: [git, drift-detection, release-notes, cli]
requires:
  - phase: 06-cached-non-blocking-auto-update-check
    provides: Cached update check with offline-tolerant payload and banner integration
provides:
  - Commit-level git drift detection (local rev-list with GitHub compare fallback)
  - Canonical release-notes URL derived from the resolved tag
  - CLI exit codes separating commit-only drift from version drift
affects: [08-developer-tooling-test-reliability, 06-cached-non-blocking-auto-update-check]
tech-stack:
  added: []
  patterns: [local-first git drift check with HTTP fallback, non-mutating update inspection]
key-files:
  created: []
  modified:
    - notion_brain/update.py
    - notion_brain/__main__.py
    - tests/test_update.py
    - tests/characterization/test_cli_contract.py
key-decisions:
  - Detect commit drift only on `main`; feature branches and detached HEAD report a skipped check rather than a misleading count.
  - Prefer local `git rev-list --left-right --count HEAD...origin/main`; fall back to the GitHub compare API only when the local ref is absent.
  - `_cmd_update` exits 0 for commit-only drift and 2 for version/both drift, preserving the established exit-code contract.
  - The command never mutates the environment; no fetch, pull or install runs on the inspection path.
requirements-completed: [UPD-06, UPD-07]
coverage:
  - id: D1
    description: Commit-level drift reports behind/ahead counts for a git-clone install on main.
    requirement: UPD-06
    verification:
      - kind: unit
        ref: tests/test_update.py
        status: pass
    human_judgment: false
  - id: D2
    description: The update payload and banner carry the canonical release-notes URL from the resolved tag.
    requirement: UPD-07
    verification:
      - kind: unit
        ref: tests/test_update.py
        status: pass
      - kind: integration
        ref: tests/characterization/test_cli_contract.py
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-07
---

# Phase 7 plan 01 summary

**Commit-level git drift detection with local rev-list, GitHub compare fallback, and canonical release-notes URLs**

## Performance

- **Tasks:** 3
- **Files modified:** 4
- **Commit:** `4c7afdf`

## Accomplishments

- `detect_git_drift(repo_dir)` verifies the current branch is `main`, then reads ahead/behind counts from `git rev-list --left-right --count HEAD...origin/main`.
- When the local `origin/main` ref is unavailable, the check falls back to the GitHub compare API for the same ahead/behind metrics.
- `check_for_update` now returns `drift_type` (`version`, `commit`, `both`, `none`), `behind_commits`, `ahead_commits` and a canonical `release_url` built as `https://github.com/MNDL-27/hermes-brain/releases/tag/v{latest}`.
- Human and JSON formatting expose the commit drift; `_cmd_update` returns 0 for commit-only drift and 2 when a version drift exists.
- The inspection path performs no fetch, pull, install or other mutation.

## Files Created/Modified

- `notion_brain/update.py` — drift detection, enriched payload, human/JSON formatting.
- `notion_brain/__main__.py` — exit-code reconciliation.
- `tests/test_update.py` — local parsing, API fallback, non-main skip, precedence and URL tests.
- `tests/characterization/test_cli_contract.py` — CLI contract updated for the new exit codes.

## Decisions Made

- Non-main branches skip commit drift instead of comparing against a branch the user is not tracking.
- Commit drift is additive information: version drift still determines the stronger exit code.
- Release URL construction stays deterministic from the resolved tag; no repository-root fallback.

## Deviations from Plan

None — the implemented behavior matches the plan's three tasks.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

The payload fields are consumed by `update_cache` in plan 07-02 and by the Phase 6 banner/health paths.

## Self-Check

All checks passed: implementation files exist, `64 passed` across `tests/test_update.py` and `tests/test_update_cache.py`, and commit `4c7afdf` is present in this repository's history.
