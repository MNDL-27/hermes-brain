---
phase: "11"
slug: storage-adapters
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-12"
plan: "11-01"
requirements: [ADAPT-01, ADAPT-02, ADAPT-03, ADAPT-04]
validated: "2026-11-12"
---

# Phase 11 validation strategy

Validation contract for the `11-01` adapter-wiring gap plan. The protocol and vault scaffold already existed at `71e7122`; this plan verifies the missing production connection. Existing pytest infrastructure covers every referenced path, so no Wave 0 dependency is missing.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest, standard-library mocks, temporary vault and SQLite files |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_adapters.py -q` |
| Scoped regression command | `.venv/bin/python -m pytest tests/test_adapters.py tests/test_provider.py tests/test_catalog.py tests/test_provenance.py tests/test_supersession.py -q` |
| Full gate on this host | `env -u PYTHONPATH UV_NO_SYNC=1 .venv/bin/python -m pytest -q` |
| Static gates | `.venv/bin/python -m ruff check notion_brain tests`; `.venv/bin/python -m mypy notion_brain` |

## Per-task verification map

| Task | Wave | Requirements | Behavior | Command | Status |
| --- | --- | --- | --- | --- | --- |
| 11-01-01 | 1 | ADAPT-02 | Provider recall fetches rows through `NotionAdapter`, preserving database scoping and catalog mapping | `.venv/bin/python -m pytest tests/test_adapters.py tests/test_provider.py tests/test_catalog.py -q` | Pass |
| 11-01-02 | 1 | ADAPT-03 | `initialize()` selects a backend through the entitlement-checked factory and falls back to Notion on `EntitlementError` | `.venv/bin/python -m pytest tests/test_adapters.py tests/test_provider.py -q` | Pass |
| 11-01-03 | 1 | ADAPT-04 | Entitled premium selection exposes the vault adapter and its rows reach recall output | `.venv/bin/python -m pytest tests/test_adapters.py -q` | Pass |

## Required observations

| Behavior | Test setup and assertion |
| --- | --- |
| Notion prefetch adapter use | Provider with a memory database id and a stubbed `NotionAdapter.prefetch`; assert the adapter is called with `limit=10` and its rows are returned. |
| Notion search adapter use | Provider with a memory database id and a stubbed `NotionAdapter.search`; assert `database_id`, `limit` and query are forwarded and the row reaches the tool payload. |
| Free-tier default | `initialize()` without a premium request wires `NotionAdapter` and leaves `_adapter_name == "notion"`. |
| Entitlement fallback | `get_adapter` raises `EntitlementError`; assert the session stays usable, `_obsidian_adapter` is `None`, and the Notion adapter is present. |
| Entitled selection | License file plus vault path; assert the Obsidian adapter is the selected backend. |
| Premium recall merge | Vault row written through the adapter; unscoped provider search returns the row with normalized `properties.Content`. |
| Existing behavior | The complete existing suite, including uninitialized-provider paths that patch `store.query_database`, stays green without edits. |

## Sampling and final gate

- Targeted adapter suite: **13 passed**.
- Full repository gate: **568 passed, 1 deselected in 5.59s** (previous baseline 561; +7 new regressions).
- Ruff clean; mypy clean.
- No live Notion call, external confirmation UI, new dependency or watch mode is required.

## Sign-off

- [x] Existing infrastructure covers every verification path.
- [x] Each task has an executable automated command.
- [x] Baseline recorded independently (561 passed before the new tests).
- [x] New regressions pass after implementation.
- [x] Full repository and static gates pass.
- [x] Factual summary and verification fingerprint exist in `11-01-SUMMARY.md` and `11-VERIFICATION.md`.

**Validation status:** validated. ADAPT-02's Memory write path is a documented ceiling rather than a hidden gap; see the summary and verification record.
