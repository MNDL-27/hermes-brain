---
phase: "14"
slug: graph-provenance-relational-recall
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-12"
plan: "14-01"
requirements: [PROV-01, PROV-02, PROV-03]
validated: "2026-11-12"
---

# Phase 14 validation strategy

Gap-closure validation for PROV-01 provenance continuity. PROV-02/03 were already demonstrated; this phase adds cache persistence, conflict-safe backfill and complete rendered provenance.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest with temporary SQLite caches and mocked store/cache collaborators |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_brain_cache.py tests/test_provenance.py -q` |
| Scoped command | `.venv/bin/python -m pytest tests/test_provenance.py tests/test_certification.py tests/test_prefetch_gap_closure.py -q` |
| Full gate | `env -u PYTHONPATH UV_NO_SYNC=1 .venv/bin/python -m pytest -q` |
| Static gates | `.venv/bin/python -m ruff check notion_brain tests`; `.venv/bin/python -m mypy notion_brain` |

## Per-task verification map

| Task | Requirements | Behavior | Command | Status |
| --- | --- | --- | --- | --- |
| 14-01-01 | PROV-01 | Cache persists/reconstructs source agent, session and created time with a safe v3 migration | `.venv/bin/python -m pytest tests/test_brain_cache.py -q` | Pass |
| 14-01-02 | PROV-01 | Prefetch suffix and timeline block expose the available provenance | `.venv/bin/python -m pytest tests/test_provenance.py tests/test_certification.py tests/test_prefetch_gap_closure.py -q` | Pass |
| 14-01-03 | PROV-01 | Regressions cover round-trip, backfill, non-erasure and rendered output | `.venv/bin/python -m pytest tests/test_brain_cache.py tests/test_provenance.py -q` | Pass |

## Required observations

| Behavior | Test setup and assertion |
| --- | --- |
| Cache round-trip | Upsert with known provenance; `list_active` reconstructs Source Agent/Session/Created At. |
| Backfill | Accepted row without provenance; population with provenance keeps local content/status/truth and fills provenance. |
| Non-erasure | Stored provenance survives a population with empty provenance. |
| Migration | v2 cache gains the new columns without losing rows; a newer schema is untouched. |
| Prefetch | Known provenance renders the suffix while the existing compact tag remains. |
| Timeline | Items include the full provenance block including superseded status. |
| Existing contracts | Exact-equality cache round-trip and existing `[fact:…]` assertions remain meaningful; three prefetch expectations were updated for the intentional suffix. |

## Sampling and final gate

- Cache/provenance suite: **23 passed in 0.25s**.
- Scoped suite: **46 passed in 0.24s**.
- Full repository gate: **579 passed, 1 deselected in 5.77s**; ruff, mypy and whitespace clean.
- No live Notion call required.

## Sign-off

- [x] Every task has an executable automated command.
- [x] New regressions cover continuity, backfill safety and rendered output.
- [x] Scoped and full repository gates pass.
- [x] Static gates pass.
- [x] Summary and verification fingerprint exist in `14-01-SUMMARY.md` and `14-VERIFICATION.md`.

**Validation status:** validated. No human-only check applies to these deterministic backend contracts.
