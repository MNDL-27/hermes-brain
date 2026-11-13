---
phase: "17"
slug: vault-primary-provider-routing
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-13"
plan: "17-01"
requirements: [OBS-03, SYNC-03]
validated: "2026-11-13"
---

# Phase 17 validation strategy

Validation for vault-primary provider routing. All tests are offline and use temporary vaults with a stubbed entitlement file.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest with temporary vaults and monkeypatched Notion store |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_adapters.py tests/test_certification.py tests/test_supersession.py tests/test_provenance.py -q` |
| Full gate | `env -u PYTHONPATH UV_NO_SYNC=1 .venv/bin/python -m pytest -q` |
| Static gates | `.venv/bin/python -m ruff check notion_brain tests`; `.venv/bin/python -m mypy notion_brain` |

## Per-task verification map

| Task | Requirements | Behavior | Command | Status |
| --- | --- | --- | --- | --- |
| 17-01-01 | OBS-03 | Adapter active/find/supersede helpers with certified protection | `.venv/bin/python -m pytest tests/test_adapters.py -q` | Pass |
| 17-01-02 | OBS-03 | Vault write and certification routing, fail-closed errors | `.venv/bin/python -m pytest tests/test_adapters.py tests/test_certification.py -q` | Pass |
| 17-01-03 | SYNC-03 | Vault-first search, prefetch allowance and `vault_status` | `.venv/bin/python -m pytest tests/test_adapters.py tests/test_provenance.py -q` | Pass |
| 17-01-04 | OBS-03, SYNC-03 | Eight routing regressions | `.venv/bin/python -m pytest tests/test_adapters.py -q` | Pass |

## Required observations

| Behavior | Test setup and assertion |
| --- | --- |
| Vault write | Premium provider remembers a Memory entry; one note exists and Notion create/update is never called. |
| Fail closed | Adapter remember/supersede raise; the tool returns the generic vault error and Notion is untouched. |
| Supersession | Two changed same-subject writes leave one Superseded note, one active note, the predecessor link and a catalog `supersedes` edge. |
| Certification | Confirmed certify flips truth, supersedes an inferred peer, writes the edge, and a later ordinary write cannot demote the certified note. |
| Search | A vault hit skips `store.query_database`; an empty vault falls back to Notion memory. |
| Status/config | `HERMES_OBSIDIAN_VAULT` alone selects the adapter; `vault_status` reports backend, entitlement, path, counts, schema version and `last_sync`. |
| Certified protection | Adapter supersession skips certified peers and returns the correct `superseded_ids`. |
| Free tier | Existing provider, certification, supersession and provenance suites stay green. |

## Sampling and final gate

- Adapter suite: **28 passed in 0.42s**.
- Full repository gate: **596 passed, 1 deselected in 5.73s**.
- Ruff, mypy and whitespace clean.
- No live Notion call or external service required.

## Sign-off

- [x] Every task has an executable automated command.
- [x] Eight new regressions cover routing, fail-closed, certification, search and status.
- [x] Existing free-tier suites remain green.
- [x] Full and static gates pass.
- [x] Summary and verification fingerprint exist in `17-01-SUMMARY.md` and `17-VERIFICATION.md`.

**Validation status:** validated. No human-only check applies to these deterministic backend contracts.
