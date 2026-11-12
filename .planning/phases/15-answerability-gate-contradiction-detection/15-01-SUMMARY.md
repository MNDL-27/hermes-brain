---
phase: 15-answerability-gate-contradiction-detection
plan: "01"
subsystem: answerability
tags: [answerability, contradiction, injection-budget, retrieval]
requires:
  - phase: 14-graph-provenance-relational-recall
    provides: Provenance and certification labels on recalled facts
provides:
  - Explicitly bounded prefetch contradiction notice
  - Deterministic omitted-entry marker
  - Complete structured contradiction payload
affects: []
tech-stack:
  added: []
  patterns: [notice-level cap before global injection budgeting]
key-files:
  created: []
  modified:
    - notion_brain/provider.py
    - tests/test_answerability.py
key-decisions:
  - Cap rendered conflict entries at four; the header plus labels fit the 400-token warning lane.
  - Append an exact `… N more conflicting entries omitted` line rather than silently truncating.
  - Keep `_contradictions` and the structured payload complete; only rendering is bounded.
requirements-completed: [ANS-02]
coverage:
  - id: D1
    description: The prefetch contradiction notice is explicitly bounded and reports omitted entries.
    requirement: ANS-02
    verification:
      - kind: unit
        ref: tests/test_answerability.py::test_prefetch_notice_caps_entries_and_reports_omitted
        status: pass
      - kind: unit
        ref: tests/test_answerability.py::test_prefetch_surfaces_contradiction
        status: pass
    human_judgment: false
  - id: D2
    description: The structured payload stays complete and the notice stays redacted.
    requirement: ANS-02
    verification:
      - kind: unit
        ref: tests/test_answerability.py::test_search_payload_keeps_all_contradiction_entries
        status: pass
      - kind: unit
        ref: tests/test_answerability.py::test_prefetch_notice_redacts_conflicting_values
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-12
---

# Phase 15 plan 01 summary

**The contradiction notice is now explicitly bounded, reports omitted entries, and keeps the structured payload complete**

## Performance

- **Tasks:** 2
- **Files modified:** 2
- **Commits:** `cf12265`

## Accomplishments

- `prefetch` renders at most `MAX_CONTRADICTION_NOTICE_ENTRIES` (4) conflict entry lines.
- Every skipped entry increments a counter; a deterministic `- … N more conflicting entries omitted` line is appended.
- Small conflicts still render both values with timestamps and certification labels and no omitted marker.
- `_contradictions` and the search payload keep every entry, so callers are never silently given a partial dispute.
- Redaction still applies to rendered values.

## Evidence

- Answerability/budget suite: **37 passed in 0.27s**, including new large-conflict, payload-completeness and redaction regressions.
- Full repository gate: **582 passed, 1 deselected in 5.92s** (Phase 14 baseline 579 plus three new regressions).
- The large-conflict notice stays within the 400-token warning lane and the 800-token total.
- Ruff, mypy and whitespace clean.

## Decisions Made

- The cap is notice-level, before the two-lane renderer, so the notice cannot crowd out unrelated pinned content through implicit line dropping.
- The omitted count is exact and deterministic, preserving auditability without rendering every candidate.

## Deviations from Plan

None — both planned tasks were implemented as specified.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

All 15 roadmap phases now have current closure evidence; the milestone-level integrity check and merge/release decision remain separate.

## Self-Check

All checks passed: the notice cap and overflow marker are covered, small conflicts remain fully visible, the payload is complete, redaction holds, and full/static gates pass.
