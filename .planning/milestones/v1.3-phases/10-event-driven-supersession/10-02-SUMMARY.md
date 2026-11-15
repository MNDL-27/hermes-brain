---
phase: 10-event-driven-supersession
plan: "02"
subsystem: supersession
status: complete
completed: 2026-11-09
requirements-completed: [SUP-01, SUP-02, SUP-03]
requires:
  - phase: 09-retrieval-correctness-local-cache
    provides: Active-only cold prefetch, read-through SQLite cache, deterministic two-lane injection
affects: [11-storage-adapters, 13-certification-failure, 14-provenance]
tech-stack:
  added: []
  patterns: [shared Memory subject-resolution boundary, non-destructive same-title versioning, accepted-transition graph ordering]
key-files:
  created: []
  modified: [notion_brain/provider.py, tests/test_supersession.py, tests/test_write_provenance.py, tests/test_certification.py, tests/test_coverage_gaps.py]
key-decisions:
  - Memory-only scope: only the configured Memory database acquires automatic subject inference and versioning; non-Memory destinations retain the legacy in-place title-dedup update.
  - A nonblank redacted explicit override wins over inference; blank overrides fall back to inference; unrecognized content stays keyless.
  - Changed same-title Memory values create a new page before any predecessor status transition; the predecessor's content and creation time are retained.
  - Exact active replay (same normalized title, same nonblank subject, proven-equal content) reuses the existing page with no new page, no status transition, no duplicate edge.
  - Notion truncates remote Content to 2,000 characters, so two full values sharing that prefix are never treated as equal; a trusted full cache row may establish equality only while the remote prefix still agrees. Without full-value evidence, a conservative new retained version is created instead of an unsafe overwrite.
  - Certified facts are protected: an ordinary inferred write may reuse an exact certified match but never demotes its Truth, overwrites its provenance, or superses it.
  - Creation failure leaves all predecessor state untouched; a rejected predecessor status update produces no cache flip or graph edge; optional predecessor-link or catalog failures cannot turn an accepted write into failure and independent later predecessors continue processing.
  - Timeline ordering prefers immutable fact creation time over Last Edited so a status-only edit cannot reorder history; existing-field fallbacks are documented for legacy rows.
coverage:
  - id: S1
    description: Background ingestion and explicit remember resolve the same deterministic subject key before persistence.
    requirement: SUP-01
    verification:
      - kind: integration
        ref: tests/test_supersession.py::test_background_blank_subject_override_falls_back_to_inference
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_background_secret_bearing_subject_override_is_redacted
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_background_non_memory_write_does_not_infer_subject_key
        status: pass
    human_judgment: false
  - id: S2
    description: A changed same-title Memory fact is stored as a new page without overwriting the predecessor.
    requirement: SUP-02
    verification:
      - kind: integration
        ref: tests/test_supersession.py::test_changed_same_title_value_creates_new_page_without_overwrite
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_correction_back_to_superseded_value_creates_new_version
        status: pass
    human_judgment: false
  - id: S3
    description: Idempotency and historical/subject boundaries hold for replay and collision cases.
    requirement: SUP-02
    verification:
      - kind: integration
        ref: tests/test_supersession.py::test_identical_active_replay_reuses_without_page_or_supersession
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_superseded_title_hit_preceding_active_match_reuses_active
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_different_subject_key_under_same_title_is_distinct
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_blank_subject_never_reuses_or_supersedes
        status: pass
    human_judgment: false
  - id: S4
    description: Long-value truncation never authorizes unsafe overwrite; cache-aided equality is conservative.
    requirement: SUP-02
    verification:
      - kind: integration
        ref: tests/test_supersession.py::test_distinct_long_values_sharing_prefix_create_new_version
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_identical_long_replay_with_trusted_cache_reuses
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_long_replay_without_trusted_cache_creates_new_version
        status: pass
    human_judgment: false
  - id: S5
    description: Certified facts are protected from ordinary inferred writes; non-Memory title update is preserved.
    requirement: SUP-02
    verification:
      - kind: integration
        ref: tests/test_certification.py
        status: pass
      - kind: integration
        ref: tests/test_coverage_gaps.py
        status: pass
    human_judgment: false
  - id: S6
    description: Retained history, active cache, graph, and failure isolation remain consistent across accepted transitions.
    requirement: SUP-03
    verification:
      - kind: integration
        ref: tests/test_supersession.py::test_stateful_correction_retains_both_values_and_orders_timeline_by_creation
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_stateful_correction_updates_active_cache_for_same_and_fresh_provider
        status: pass
      - kind: integration
        ref: tests/test_supersession.py::test_stateful_graph_preserves_chain_across_corrections
        status: pass
      - kind: integration
        ref: tests/test_write_provenance.py
        status: pass
    human_judgment: false
---

# Phase 10 plan 02 summary

Both source-confirmed Phase 10 gaps are closed. Background Memory writes and explicit `remember` now resolve the same deterministic subject key before persistence, and same-title changed Memory values are stored as new pages so predecessors remain auditable while the new fact becomes active.

## Commits

- `45c8ca2`: Phase 9 cache and context-budget paths, verified baseline and prerequisite pushed before this phase began.
- This commit: Phase 10 gap-closure implementation and regression suite.

## Verification

- Before implementation: 12+ new regressions failed against the previous in-place-update behavior; a subsequent PermissionError regression also reproduced unusable recall before its fix.
- Targeted Phase 10 suite (`tests/test_supersession.py`, `tests/test_write_provenance.py`, `tests/test_certification.py`, `tests/test_coverage_gaps.py`): **121 passed in 0.54s**.
- Final full suite: **561 passed, 1 deselected in 5.86s** (baseline was 532, so +29 new tests).
- Ruff: clean. Mypy: no issues in 53 source files. CRLF-aware whitespace check: clean.
- Automated checks exercised these backend contracts; no live Notion call or external confirmation UI was needed.

## Key implementation changes

`notion_brain/provider.py`:

- `_store_entry` now calls `_resolve_memory_subject` before `_write_entry_raw` so background ingestion and explicit remember share the same subject-key inference policy.
- `_write_entry_raw` routes Memory writes through `_reuse_or_create_memory`, which compares normalized title, subject key, and content (with 2,000-char truncation awareness) before deciding whether to reuse an existing page or create a new one.
- Non-Memory destinations retain the legacy in-place title-dedup update path.
- After a successful Memory write, the in-memory prefetch snapshot is invalidated so the same provider's next read observes the accepted cache mutation.
- `_supersede_matching_active` now skips certified predecessors and inactive inputs; graph edges and cache status transitions are recorded only after the predecessor status update is accepted.
- `_tool_timeline` prefers immutable fact creation time over Last Edited so a status-only edit cannot reorder history.

`tests/test_supersession.py`: 12+ new named regressions covering background inference, version identity, idempotency, long-value truncation, stateful timeline/cache/graph behavior, and failure isolation using a stateful in-memory Notion fake and real temporary SQLite/catalog files.

`tests/test_write_provenance.py`: accepted-status-to-graph/cache failure-isolation regressions.

`tests/test_certification.py`: ordinary-write protection for existing certified facts (same-title and different-title predecessors).

`tests/test_coverage_gaps.py`: replaced the old assumption that changed Memory content should overwrite a page with a real non-Memory title-update regression.

## Remaining scope

- Phase 11: StorageAdapter protocol, NotionAdapter refactor, premium entitlement gate, ObsidianVaultAdapter.
- Phase 13: certification-failure path in `_tool_certify`.
- Phase 14: provenance and audit trail.
- No live Notion mutation was required or performed during tests.

Phase 10 is complete. Phases 11–15 remain open in the milestone audit. Completing Phase 10 does not mark v1.4 released or merged to main.
