---
phase: 10-event-driven-supersession
verified: 2026-11-09
status: gaps_found
source_snapshot: 45c8ca2
score: "1/3 scoped contracts demonstrated; gap tests still to be added"
gaps:
  - truth: Background memory writes receive the same subject-key inference as explicit remember calls.
    requirements: [SUP-01]
    reason: The integration audit found inference in _tool_remember but no matching inference step in the background classified-entry path.
    artifacts:
      - path: notion_brain/provider.py
        issue: _process_sync_turn passes entries to storage without the explicit tool's subject-key inference.
    missing:
      - Reproduce the missing background subject key in an offline provider regression.
      - Apply existing inference and explicit override semantics consistently before storage.
  - truth: A changed fact with the same title retains the prior value as a superseded historical row.
    requirements: [SUP-02]
    reason: _write_entry_raw currently finds the existing title and updates that page in place, losing its previous content.
    artifacts:
      - path: notion_brain/provider.py
        issue: Same-title update bypasses the new-row supersession history path.
    missing:
      - Reproduce a same-title changed-value correction and prove the old value remains in timeline recall.
      - Preserve no-op/deduplication behavior while retaining changed facts non-destructively.
      - Verify cache, status and graph history remain consistent.
---

# Phase 10 verification handoff

The next approved work is gap closure for SUP-01/SUP-02. These are source-confirmed integration findings from the [milestone audit](../../v1.4-MILESTONE-AUDIT.md); no new Phase 10 execution or passing verification is claimed here.

Phase 9 plan 09-02 has already corrected active-only cold prefetch, so that part of the audit's SUP-02 finding does not need to be implemented again. Existing timeline/as-of behavior is covered by `tests/test_supersession.py`; preserve it while adding regression cases for background inference and same-title history.

Use `.planning/dispatch-phase10.md`, the existing provider/cache/catalog implementation, and the audited requirements to write a gap-closure plan. Later adapter, certification-failure and provenance gaps remain in their own phases. This work introduces no v1.5 scope.
