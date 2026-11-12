---
phase: 14-graph-provenance-relational-recall
verified: 2026-11-12
status: passed
source_snapshot: edec36a
score: "3/3 success criteria verified; PROV-01, PROV-02 and PROV-03 closed"
fingerprint: "Phase 14 closure: known source agent/session and original created time survive the SQLite cache, read-population conflicts backfill provenance without overwriting accepted rows, prefetch renders a provenance suffix, timeline returns the full block, and supersession edges/traversal remain intact. 23 cache/provenance tests and 46 scoped tests pass; full suite 579 passed, 1 deselected; ruff and mypy clean."
gaps: []
covered_files:
  - notion_brain/brain_cache.py
  - notion_brain/provider.py
  - tests/test_brain_cache.py
  - tests/test_provenance.py
  - tests/test_prefetch_hydration.py
  - .planning/phases/14-graph-provenance-relational-recall/14-01-PLAN.md
  - .planning/phases/14-graph-provenance-relational-recall/14-01-SUMMARY.md
covered_digest: "v4:sha256:7e0ef85c372f5ed2577e6a7f723ba481115e94483a4e83f4170cf5ce4596ad52"
closed:
  - truth: Recall results expose source, session, timestamp and truth/status for each fact.
    requirements: [PROV-01]
    resolution: Cache schema v3 persists source_agent/source_session/created_at with an additive migration; upsert/populate/list reconstruct them; _provenance reads Created At; prefetch appends a provenance suffix and timeline returns the full block.
    evidence: tests/test_brain_cache.py::test_provenance_round_trip, test_population_backfills_provenance_without_overwriting_accepted_row, test_population_does_not_erase_stored_provenance; tests/test_provenance.py::test_prefetch_surfaces_full_provenance_suffix, test_timeline_includes_provenance_block, test_cached_prefetch_preserves_known_provenance
  - truth: Supersession writes an explicit relation edge while preserving historical recall.
    requirements: [PROV-02]
    resolution: Supersession records a catalog supersedes edge and the Superseded Page ID property; retained rows remain queryable through timeline.
    evidence: tests/test_provenance.py::test_supersession_creates_catalog_edge, test_memory_schema_adds_superseded_page_id_without_reset; tests/test_supersession.py
  - truth: Related facts are traversable by typed edges with cycle and depth handling.
    requirements: [PROV-03]
    resolution: Catalog.graph_traverse performs cycle-aware bounded BFS; search action related maps reachable ids to stored rows.
    evidence: tests/test_provenance.py::test_graph_traverse_chain_cycles_and_depth, test_related_action_returns_connected_facts
---

# Phase 14 verification record

Phase 14 is verified. PROV-02 and PROV-03 were already wired; the PROV-01 provenance-continuity gap recorded in the 2026-11-09 milestone audit is closed.

## Verification scope

- Cache/provenance suite: **23 passed in 0.25s**.
- Scoped suite (`test_provenance` + `test_certification` + `test_prefetch_gap_closure`): **46 passed in 0.24s**.
- Full repository gate: **579 passed, 1 deselected in 5.77s** (Phase 13 baseline 573 plus six new regressions).
- Ruff, mypy and CRLF-aware whitespace checks clean.
- No live Notion call was required.
- Digest refreshed 2026-11-12 after the Phase 15 provider change; 23 cache/provenance tests and the 582-test full gate are green.

## Closure evidence

`notion_brain/brain_cache.py`:

- Schema v3 adds `source_agent`, `source_session` and `created_at` through additive ALTERs; a newer schema is left untouched.
- `upsert_active` redacts and stores provenance, preserving known values on conflict.
- `populate_from_read` backfills empty provenance only; accepted title/content/status/truth are never overwritten.
- `list_active` reconstructs known provenance keys and omits unknown/empty ones.

`notion_brain/provider.py`:

- `_provenance` prefers `Created At` for cached rows.
- `_mirror_memory_cache` carries the session into the cache.
- Prefetch keeps the existing `[fact:truth:agent]` tag and appends `[provenance: session=… created=… status=…]`.
- Timeline items include the full provenance block.

## Scope note

Three exact-line prefetch assertions were updated to include the intentional provenance suffix; no assertion was weakened. PROV-02/03 behavior is unchanged.

## Remaining scope

Phase 15 answerability closure remains. Phase 14 does not mark the milestone released or merged to `main`.
