---
phase: 04-build-metadata-modernization-pypi-publishing
plan: 02
subsystem: distribution
tags: [publish, pypi, oidc, runbook]
requires-phase: 04-01
provides-phase: null
key-files:
  created:
    - .github/workflows/publish.yml
    - docs/RELEASES.md
  modified: []
---

# Phase 04 Plan 02 — OIDC Publish Workflow & Maintainer Runbook

## What Shipped

- `.github/workflows/publish.yml` — six-job gated OIDC release workflow: `test` (matrix 3.11/3.12/3.13) + `lint` (ruff+mypy) gate `build`, which performs ancestry + version + format + twine checks before producing artifacts. `publish` consumes the artifact via `pypa/gh-action-pypi-publish@release/v1` under `environment: pypi` with job-scoped `id-token: write`. `release` creates the GitHub release via native `gh release create --generate-notes`. `smoke-test` polls PyPI CDN with 12×10s exponential backoff.
- `docs/RELEASES.md` — four-section maintainer runbook: automated release path, one-time PyPI Trusted Publisher setup (both pending-publisher and manual-create paths), emergency manual twine fallback with env-var-only token handling, and release recovery (pre-publish tag-delete + post-publish yank).

## Verification

All three contract verifiers from `04-02-PLAN.md` pass:

- `publish.yml` — 14 assertions (tag trigger, concurrency group, single-scoped `id-token: write`, `environment: pypi`, ancestry guard, version guard via `tomllib`, pre-build cleanup, twine `--strict`, `pypa/gh-action-pypi-publish@release/v1`, `fetch-depth: 0`, native `gh release create`, no `softprops`, smoke loop, no token literal): **OK**.
- `docs/RELEASES.md` — 4 H2 sections, mandatory shell snippets, both version-bump targets named, all four PyPI Trusted Publisher fields (`hermes-brain` / `MNDL-27` / `publish.yml` / `pypi`), no real token literal: **OK**.
- YAML parse of `publish.yml`: **OK**.

`tests/test_packaging.py`: 3 passed, 1 skipped (offline-mode guard).

## Deviations from Plan

The previously-saved `publish.yml` had drifted from the plan contract — it used `secrets.PYPI_API_TOKEN`, triggered on `release: published`, had no ancestry/version/smoke-test guards, and no test/lint matrix. This was rewritten to match the plan's `must_haves` exactly. No static PyPI token exists in the repository after this fix.

## Test Suite Status

| Test File | Result |
|-----------|--------|
| test_auto_sync | 3 passed |
| test_bootstrap_schema | 8 passed |
| test_config_schema | 5 passed |
| test_coverage_gaps | **hangs (pre-existing, out of scope)** |
| test_custom_databases | 4 passed |
| test_extract | 65 passed |
| test_install_guard | 2 passed |
| test_migration_privacy_blockers | **hangs (pre-existing, out of scope)** |
| test_packaging | 3 passed, 1 skipped |
| test_provider | **hangs (pre-existing, out of scope)** |
| test_provider_contract | 44 passed |
| test_cli_contract | 8 passed |
| test_storage_recall_blockers | 5 passed |
| test_durability_blockers | 6 passed |
| test_store | 37 passed |

The three pre-existing hangs are unrelated to Phase 04 — none of the touched files (`publish.yml`, `docs/RELEASES.md`, `tests/test_packaging.py`) are imported by those test modules.

## Hand-off

Phase 04 complete. Phase 05 (CLI Update Drift Detection) is next per `.planning/state.json`.
