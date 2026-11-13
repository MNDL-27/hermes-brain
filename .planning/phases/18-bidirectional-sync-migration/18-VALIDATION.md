---
phase: "18"
slug: bidirectional-sync-migration
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-13"
plan: "18-01"
requirements: [SYNC-01, SYNC-02]
validated: "2026-11-13"
---

# Phase 18 validation strategy

Validation for explicit bidirectional sync. All tests are offline and use temporary homes/vaults.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest with temporary vaults, legacy/unified state files and monkeypatched Notion |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_vault_sync.py tests/test_adapters.py -q` |
| Full gate | `env -u PYTHONPATH UV_NO_SYNC=1 .venv/bin/python -m pytest -q` |
| Static gates | `.venv/bin/python -m ruff check notion_brain tests`; `.venv/bin/python -m mypy notion_brain` |

## Per-task verification map

| Task | Requirements | Behavior | Command | Status |
| --- | --- | --- | --- | --- |
| 18-01-01 | SYNC-01, SYNC-02 | Module state, parsers, bootstrap, ingest, status | `.venv/bin/python -m pytest tests/test_vault_sync.py -q` | Pass |
| 18-01-02 | SYNC-01, SYNC-02 | Vault CLI subcommands and dispatch | `.venv/bin/python -m pytest tests/test_vault_sync.py -q` | Pass |
| 18-01-03 | SYNC-01, SYNC-02 | Sync and CLI regressions | `.venv/bin/python -m pytest tests/test_vault_sync.py tests/test_adapters.py -q` | Pass |

## Required observations

| Behavior | Test setup and assertion |
| --- | --- |
| Parsers | Memory and journal headings parse; template stubs are dropped; memory is certified and journal inferred. |
| Legacy state | A legacy mirror state migrates to the unified ingest shape with entries and last_run preserved. |
| Ingest idempotency | First run writes both entries; second run writes zero and skips both; state file is `0600`. |
| Ingest dry-run | Reports pending without creating the state file. |
| Error isolation | One failing entry does not stop the other; the error is redacted and capped. |
| Bootstrap | Active rows export with preserved truth/provenance; re-run skips existing; dry-run writes nothing; unentitled runs raise. |
| Status | Reports backend, entitlement, counts and last sync/bootstrap. |
| CLI | `vault status --json` works offline; `vault sync --dry-run --json` returns counts. |

## Sampling and final gate

- Sync suite: **11 passed in 0.21s**.
- Full repository gate: **607 passed, 1 deselected in 5.67s**.
- Ruff, mypy and whitespace clean.

## Sign-off

- [x] Every task has an executable automated command.
- [x] Regressions cover both directions, state migration, dedupe, dry-run, errors and CLI.
- [x] Full and static gates pass.
- [x] Summary and verification fingerprint exist in `18-01-SUMMARY.md` and `18-VERIFICATION.md`.

**Validation status:** validated. No human-only check applies to these deterministic sync contracts.
