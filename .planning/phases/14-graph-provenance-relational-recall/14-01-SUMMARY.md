---
phase: 14-graph-provenance-relational-recall
plan: "01"
subsystem: provenance
tags: [provenance, sqlite-cache, prefetch, timeline, audit]
requires:
  - phase: 13-user-gated-certification-flow
    provides: Certification and truth status on Memory rows
provides:
  - Source agent/session and original created time persisted in the SQLite cache
  - Provenance backfill on read-population conflicts without overwriting accepted rows
  - Prefetch provenance suffix and timeline provenance block
affects: [15-answerability-gate-contradiction-detection]
tech-stack:
  added: []
  patterns: [additive cache schema migration, conditional provenance reconstruction, append-only rendered provenance]
key-files:
  created: []
  modified:
    - notion_brain/brain_cache.py
    - notion_brain/provider.py
    - tests/test_brain_cache.py
    - tests/test_provenance.py
    - tests/test_prefetch_hydration.py
key-decisions:
  - Cache schema v3 adds source agent, session and original created time through the existing additive ALTER pattern; newer schemas remain untouched.
  - Population conflicts may backfill empty provenance fields only; accepted title/content/status/truth are never overwritten.
  - `list_active` omits unknown/empty provenance keys so the existing exact-equality cache contract stays valid.
  - Prefetch keeps the existing `[fact:truth:agent]` tag and appends a `[provenance: session=… created=… status=…]` suffix.
requirements-completed: [PROV-01]
coverage:
  - id: D1
    description: Known provenance survives cache write-through, cold-read population and offline recall.
    requirement: PROV-01
    verification:
      - kind: unit
        ref: tests/test_brain_cache.py::test_provenance_round_trip
        status: pass
      - kind: unit
        ref: tests/test_brain_cache.py::test_population_backfills_provenance_without_overwriting_accepted_row
        status: pass
      - kind: unit
        ref: tests/test_brain_cache.py::test_population_does_not_erase_stored_provenance
        status: pass
    human_judgment: false
  - id: D2
    description: Prefetch and timeline expose the available provenance.
    requirement: PROV-01
    verification:
      - kind: unit
        ref: tests/test_provenance.py::test_prefetch_surfaces_full_provenance_suffix
        status: pass
      - kind: unit
        ref: tests/test_provenance.py::test_timeline_includes_provenance_block
        status: pass
      - kind: unit
        ref: tests/test_provenance.py::test_cached_prefetch_preserves_known_provenance
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-12
---

# Phase 14 plan 01 summary

**Known source, session and created-time provenance now survives the SQLite cache and reaches prefetch and timeline output**

## Performance

- **Tasks:** 3
- **Files modified:** 5
- **Commits:** pending review (execution left uncommitted)

## Accomplishments

- `brain_cache` schema v3 adds `source_agent`, `source_session` and `created_at` using the same additive ALTER pattern as earlier columns; a newer on-disk schema is never mutated.
- `upsert_active` accepts and redacts provenance; empty/unknown values never overwrite known stored values.
- `populate_from_read` stores provenance and upgrades its conflict clause to backfill empty provenance only, leaving accepted content/status/truth untouched.
- `list_active` reconstructs `Source Agent`, `Source Session` and `Created At` only when known, preserving the existing exact-equality round-trip contract.
- `_provenance` reads `Created At`, `_mirror_memory_cache` passes the session, prefetch appends a provenance suffix, and timeline returns the full block.

## Evidence

- Cache/provenance suite: **23 passed in 0.25s**.
- Scoped suite (`test_provenance` + `test_certification` + `test_prefetch_gap_closure`): **46 passed in 0.24s**.
- Full repository gate: **579 passed, 1 deselected in 5.77s** (Phase 13 baseline 573 plus six new regressions).
- Ruff, mypy and whitespace clean.
- Three exact-line prefetch tests were updated to include the new provenance suffix; no assertion was weakened.

## Decisions Made

- Provenance is additive at every layer: schema columns, cache parameters, rendered suffix. Existing callers keep working.
- Unknown/empty provenance is not rendered as a fake value; missing data keeps the `unknown` sentinel inside the compact tag.
- A cold read may enrich provenance but never replace an accepted local row.

## Deviations from Plan

The prefetch change required updating three exact-line expectations in `tests/test_prefetch_hydration.py` to include the new suffix. This is an intentional output change from PROV-01, not a weakened assertion.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Phase 14 is verified; Phase 15 answerability closure is next.

## Self-Check

All checks passed: cache and provenance suites are green, six new regressions cover continuity and backfill, the full suite passes, and static gates report no issues.
