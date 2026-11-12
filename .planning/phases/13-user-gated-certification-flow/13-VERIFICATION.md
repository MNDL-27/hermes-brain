---
phase: 13-user-gated-certification-flow
verified: 2026-11-12
status: passed
source_snapshot: working tree on top of f8f01b7
score: "3/3 success criteria verified; CERT-01, CERT-02 and CERT-03 closed"
fingerprint: "Phase 13 closure: agent writes default to inferred, exact per-call confirmation is the only promotion path, certified facts rank first at equal recency, and certification now isolates predecessor metadata/catalog/cache failures after the accepted Truth flip while still failing closed on a rejected Truth write. 25 certification tests and 63 scoped tests pass; full suite 573 passed, 1 deselected; ruff and mypy clean."
gaps: []
closed:
  - truth: Agent-written memories default to inferred and certified facts rank above inferred facts at equal recency.
    requirements: [CERT-01]
    resolution: BrainEntry normalizes unknown truth to inferred; _database_properties writes Truth only on the Memory database; _truth_recency_key and prefetch/search ordering prefer certified at equal recency.
    evidence: tests/test_certification.py::test_agent_remember_defaults_truth_to_inferred, test_truth_is_normalized_to_inferred_for_agent_entries, test_search_and_prefetch_tiebreak_equal_recency_by_truth, test_memory_schema_match_accepts_truth_select_superset
  - truth: Only explicit per-call user confirmation promotes inferred to certified.
    requirements: [CERT-02]
    resolution: _tool_certify requires user_confirmed is True for that invocation; the tool schema does not expose confirmation, arguments cannot authorize it, and initialize cannot grant it.
    evidence: tests/test_certification.py::test_certify_requires_exact_user_confirmation, test_certify_schema_does_not_expose_confirmation, test_certify_tool_args_cannot_self_certify, test_initialize_cannot_grant_certification_permission, test_confirmation_applies_only_to_one_certification_call, test_confirmation_is_not_forwarded_to_other_tool_handlers
  - truth: A certified correction supersedes conflicting inferred rows and completes its bookkeeping independently of recoverable auxiliary failures.
    requirements: [CERT-03]
    resolution: After the accepted Truth write, each predecessor's status flip, Superseded Page ID write, catalog edge and cache mirror is isolated; a recoverable failure logs a redacted warning and the loop continues. A rejected Truth write still returns an error before any predecessor work.
    evidence: tests/test_certification.py::test_certify_promotes_and_supersedes_same_subject_inferred, test_certify_catalog_failure_still_updates_cache_and_remaining_peers, test_certify_metadata_failure_does_not_abort_peer_loop, test_certify_truth_write_failure_returns_error_without_predecessor_updates
---

# Phase 13 verification record

Phase 13 is verified. CERT-01 and CERT-02 were already demonstrated; the CERT-03 failure-isolation gap recorded in the 2026-11-09 milestone audit is closed by this plan.

## Verification scope

- Certification suite: **25 passed in 0.21s**.
- Scoped suite (`test_certification` + `test_supersession` + `test_write_provenance`): **63 passed in 0.47s**.
- Full repository gate: **573 passed, 1 deselected in 7.66s** (Phase 12 baseline 570 plus three new regressions).
- Ruff, mypy and CRLF-aware whitespace checks clean.
- No live Notion call or external confirmation UI was used.

## Closure evidence

`notion_brain/provider.py::_tool_certify`:

- The Truth update is attempted first and is the only fatal step.
- The certified-row cache mirror has its own try/except.
- The predecessor loop isolates status resolution, status flip, optional `Superseded Page ID`, catalog `supersedes` edge and cache mirror.
- A failed status flip skips that peer's remaining work and continues to later peers.
- The schema is read once; a schema-read failure logs and leaves statuses untouched.

`tests/test_certification.py`:

- `test_certify_catalog_failure_still_updates_cache_and_remaining_peers` — both peers flip and mirror despite a raising catalog save; the secret-bearing diagnostic is redacted.
- `test_certify_metadata_failure_does_not_abort_peer_loop` — a rejected metadata write does not stop the loop.
- `test_certify_truth_write_failure_returns_error_without_predecessor_updates` — the failure boundary holds.

## Scope note

No permission-model, ranking, schema or provenance-persistence behavior changed. Phase 14's full provenance continuity work remains separate.

## Remaining scope

Phase 14 (provenance continuity) and Phase 15 (answerability closeout) remain. Phase 13 does not mark the milestone released or merged to `main`.
