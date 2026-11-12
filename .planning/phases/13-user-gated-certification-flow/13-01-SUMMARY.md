---
phase: 13-user-gated-certification-flow
plan: "01"
subsystem: certification
tags: [certification, truth, failure-isolation, cache, provenance]
requires:
  - phase: 10-event-driven-supersession
    provides: Subject-key slots and non-destructive supersession of inferred predecessors
provides:
  - Failure-isolated certification bookkeeping after an accepted Truth flip
  - Per-peer supersession, metadata, catalog and cache work that cannot abort the loop
  - Truth-write failure boundary preserved
affects: [14-provenance-graph-relational-recall]
tech-stack:
  added: []
  patterns: [accepted-write success boundary, per-concern failure isolation in a peer loop]
key-files:
  created: []
  modified:
    - notion_brain/provider.py
    - tests/test_certification.py
key-decisions:
  - The accepted Truth write is the certification success boundary; provenance and cache failures are warnings, not a failed certification.
  - Each predecessor concern (status flip, `Superseded Page ID`, catalog edge, cache mirror) has its own try/except, mirroring `_supersede_matching_active`.
  - A rejected status flip skips that peer's metadata/graph/cache work but does not stop later peers.
  - The schema is read once before the peer loop; a schema-read failure logs and leaves predecessor statuses untouched rather than guessing.
requirements-completed: [CERT-03]
coverage:
  - id: D1
    description: An accepted certification completes predecessor supersession and cache mirroring despite catalog or metadata failures.
    requirement: CERT-03
    verification:
      - kind: unit
        ref: tests/test_certification.py::test_certify_catalog_failure_still_updates_cache_and_remaining_peers
        status: pass
      - kind: unit
        ref: tests/test_certification.py::test_certify_metadata_failure_does_not_abort_peer_loop
        status: pass
    human_judgment: false
  - id: D2
    description: A rejected Truth write returns an error and performs no predecessor transitions.
    requirement: CERT-03
    verification:
      - kind: unit
        ref: tests/test_certification.py::test_certify_truth_write_failure_returns_error_without_predecessor_updates
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-12
---

# Phase 13 plan 01 summary

**Certification survives recoverable provenance and cache failures after the Truth flip, and still fails closed on a rejected Truth write**

## Performance

- **Tasks:** 2
- **Files modified:** 2
- **Commits:** pending review (execution left uncommitted)

## Accomplishments

- `_tool_certify` now isolates the certified-row cache mirror, the optional `Superseded Page ID` update, the catalog `supersedes` edge and each predecessor's cache mirror.
- A catalog, metadata or cache failure logs a redacted warning and the peer loop continues; the method returns `Certified: ...` once the Truth write was accepted.
- A predecessor whose status flip is rejected is skipped without blocking later peers.
- A rejected Truth write still returns `Error: certification update failed` before any predecessor, graph or cache work.
- The schema is read once before the loop; a schema-read failure is isolated and leaves statuses untouched.

## Evidence

- `tests/test_certification.py` — **25 passed**, including three new failure-injection regressions.
- Scoped suite (`test_certification` + `test_supersession` + `test_write_provenance`) — **63 passed in 0.47s**.
- Full repository gate — **573 passed, 1 deselected in 7.66s**; ruff, mypy and whitespace clean.
- The catalog-failure regression includes a secret-bearing exception and asserts the log is redacted.

## Decisions Made

- Certification success is defined by the Truth write, not by optional bookkeeping. This matches the accepted-write ordering used by ordinary supersession.
- Failures are logged per concern rather than accumulated into a single error, so later peers always get their chance.
- No new dependency or schema change was needed.

## Deviations from Plan

None — both planned tasks were implemented as specified.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Phase 13 is verified; Phase 14 provenance and graph work is next.

## Self-Check

All checks passed: both files exist, the three new regressions pass, the scoped and full suites are green, and static gates report no issues.
