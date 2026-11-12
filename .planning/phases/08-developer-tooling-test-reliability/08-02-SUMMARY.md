---
phase: 08-developer-tooling-test-reliability
plan: "02"
subsystem: developer-tooling
tags: [git-hooks, pre-push, github-actions, pre-commit, maintenance]
requires:
  - phase: 08-developer-tooling-test-reliability
    provides: Hermetic offline suite and named network-test deselection from plan 08-01
provides:
  - Opt-in pre-push hook running the CI-equivalent offline suite with a 300s cap
  - Documented skip escape hatch
  - Weekly pre-commit autoupdate workflow opening a maintenance PR
affects: [08-developer-tooling-test-reliability]
tech-stack:
  added: []
  patterns: [opt-in git hook via cp, shell timeout guard, least-privilege scheduled workflow, bot PR with human merge]
key-files:
  created:
    - scripts/pre-push
    - .github/workflows/pre-commit-autoupdate.yml
  modified:
    - CONTRIBUTING.md
key-decisions:
  - The hook runs `uv run --no-sync pytest -q` to match CI exactly, with a `python -m pytest` fallback when uv is absent.
  - A 300s shell timeout fails fast and blocks the push on a hang; no new timeout dependency.
  - Install stays opt-in via `cp scripts/pre-push .git/hooks/pre-push`; clone does not auto-install hooks.
  - The autoupdate workflow runs Mondays at 06:17 UTC, uses workflow-level read permissions and job-level write permissions, cancels duplicate runs, and opens a PR for human merge.
requirements-completed: [TOOL-01, TOOL-02]
coverage:
  - id: D1
    description: The opt-in pre-push hook blocks a push when the offline suite fails or hangs.
    requirement: TOOL-01
    verification:
      - kind: integration
        ref: "bash scripts/pre-push (uv on PATH): 570 passed, 1 deselected, exit 0"
        status: pass
      - kind: integration
        ref: "HERMES_BRAIN_SKIP_PRE_PUSH=1 bash scripts/pre-push: skip notice, exit 0"
        status: pass
      - kind: other
        ref: "bash -n scripts/pre-push; executable mode"
        status: pass
    human_judgment: false
  - id: D2
    description: The weekly workflow runs pre-commit autoupdate and opens a maintenance PR with least privilege.
    requirement: TOOL-02
    verification:
      - kind: other
        ref: ".github/workflows/pre-commit-autoupdate.yml parses; cron 17 6 * * 1; peter-evans/create-pull-request@v6; scoped permissions; concurrency group"
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-07
---

# Phase 8 plan 02 summary

**Opt-in pre-push test gate and weekly pre-commit autoupdate workflow with human-merged bot PRs**

## Performance

- **Tasks:** 3
- **Files modified:** 3
- **Commits:** `c1659df`, `752fc51`

## Accomplishments

- `scripts/pre-push` runs `timeout 300 uv run --no-sync pytest -q`, matching the CI test job's hermetic contract and default network-marker deselection. It falls back to `python -m pytest` when uv is not on PATH.
- The hook honors `HERMES_BRAIN_SKIP_PRE_PUSH=1` with a one-line notice and exit 0, and performs no environment mutation (no install, pull or sync).
- `.github/workflows/pre-commit-autoupdate.yml` runs weekly (`cron: "17 6 * * 1"`) plus `workflow_dispatch`, executes `pre-commit autoupdate`, and opens a PR via `peter-evans/create-pull-request@v6` when hook revs change.
- The workflow declares workflow-level `permissions: contents: read` and job-level `contents: write` + `pull-requests: write`, with a `concurrency` group that cancels duplicates.
- `CONTRIBUTING.md` documents the one-line install, the executable requirement, the skip escape hatch, and uninstall.

## Evidence

- `bash -n scripts/pre-push` — clean; file is executable.
- Skip path — prints the skip notice, exits 0.
- Full hook run with uv on PATH — **570 passed, 1 deselected in 6.69s**, hook exit 0.
- Without uv and without an active venv, the fallback `python3 -m pytest` fails closed and blocks the push with actionable guidance; activating the project venv (or having uv on PATH) is the documented supported path.
- Workflow YAML parses; cron, permissions, concurrency and PR action are present as specified.

## Files Created/Modified

- `scripts/pre-push` — CI-equivalent offline test gate.
- `.github/workflows/pre-commit-autoupdate.yml` — weekly maintenance automation.
- `CONTRIBUTING.md` — opt-in installation and escape-hatch documentation.

## Decisions Made

- Opt-in installation avoids surprising contributors with an automatic hook.
- No `pytest-timeout` dependency; a shell `timeout` wrapper is sufficient and portable enough for the documented environments.
- The bot never auto-merges; a maintainer reviews the autoupdate PR.

## Deviations from Plan

None — behavior matches the plan's two tasks and prohibitions.

## Issues Encountered

The hook's bare-`python3` fallback fails in a shell without the project venv; this is fail-closed and documented. No code change was needed for this retrospective.

## User Setup Required

None beyond the documented opt-in `cp` install for contributors who want the hook.

## Next Phase Readiness

Phase 8's suite is a usable release gate; later phases continue to run the same hermetic contract.

## Self-Check

All checks passed: hook syntax and executable mode verified, skip path exits 0, full hook run passes 570 tests with 1 named deselection, workflow YAML parses with the specified cron, permissions and PR action, and both commits exist in history.
