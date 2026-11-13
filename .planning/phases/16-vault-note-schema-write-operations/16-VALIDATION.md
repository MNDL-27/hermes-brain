---
phase: "16"
slug: vault-note-schema-write-operations
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-13"
plan: "16-01"
requirements: [OBS-01, OBS-02]
validated: "2026-11-13"
---

# Phase 16 validation strategy

Validation for the vault note schema and write-operation foundation. All tests are offline and use temporary vaults.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest with temporary vault directories and SQLite indexes |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_adapters.py tests/test_catalog.py -q` |
| Full gate | `env -u PYTHONPATH UV_NO_SYNC=1 .venv/bin/python -m pytest -q` |
| Static gates | `.venv/bin/python -m ruff check notion_brain tests`; `.venv/bin/python -m mypy notion_brain` |

## Per-task verification map

| Task | Requirements | Behavior | Command | Status |
| --- | --- | --- | --- | --- |
| 16-01-01 | OBS-01 | Frontmatter and index v2, additive migration, row mapping | `.venv/bin/python -m pytest tests/test_adapters.py -q` | Pass |
| 16-01-02 | OBS-02 | Idempotent remember, supersede link, certification, health | `.venv/bin/python -m pytest tests/test_adapters.py -q` | Pass |
| 16-01-03 | OBS-01, OBS-02 | Six new regressions plus existing contracts | `.venv/bin/python -m pytest tests/test_adapters.py tests/test_catalog.py -q` | Pass |

## Required observations

| Behavior | Test setup and assertion |
| --- | --- |
| V2 round trip | Remember with truth/provenance/tags/domain/kind; assert frontmatter and index columns. |
| V1 migration | Manually create a v1 note/index; `get_note` returns defaults; a write with the same id upgrades frontmatter and preserves `created_at`. |
| Idempotency | Two identical active writes yield one id, one note and one index row. |
| Supersession | Old note becomes `Superseded`, replacement is active and carries the predecessor id, both notes remain. |
| Certification | `certify` flips truth; a later inferred write does not demote it. |
| Redaction | Secrets in title, body, source session and tags never reach the note or index. |
| Newer schema | Existing v1 index migration does not destroy rows; no downgrade path is introduced. |

## Sampling and final gate

- Adapter/catalog suite: **46 passed in 0.40s**.
- Full repository gate: **588 passed, 1 deselected in 5.98s**.
- Ruff, mypy and whitespace clean.
- No live Notion call or external service required.

## Sign-off

- [x] Every task has an executable automated command.
- [x] New regressions cover schema, migration, idempotency, history, certification and redaction.
- [x] Existing adapter and catalog contracts remain green.
- [x] Full and static gates pass.
- [x] Summary and verification fingerprint exist in `16-01-SUMMARY.md` and `16-VERIFICATION.md`.

**Validation status:** validated. No human-only check applies to these deterministic storage contracts.
