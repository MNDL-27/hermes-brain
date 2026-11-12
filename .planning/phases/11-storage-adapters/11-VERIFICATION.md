---
phase: 11-storage-adapters
verified: 2026-11-12
status: passed
source_snapshot: working tree on top of f9c589b
score: "3/3 success criteria verified for read and selection paths; ADAPT-02 Memory write path recorded as an explicit ceiling"
fingerprint: "Phase 11 gap closure: provider initializes and selects storage adapters through the entitlement factory, routes prefetch and search through NotionAdapter, normalizes and merges entitled Obsidian vault rows, and falls back to Notion on EntitlementError. Full suite 568 passed, 1 deselected; ruff clean; mypy clean. No live Notion or vault mutation performed."
gaps: []
ceiling:
  - requirement: ADAPT-02
    scope: "Memory write path (_store_entry, _write_entry_raw, _reuse_or_create_memory, _supersede_matching_active)"
    reason: StorageAdapter.remember/supersede cannot express provider-only properties (Truth, Kind, Confidence, Tags, Entities, Source Session, custom metadata), reuse-or-create idempotency, certification protection, graph edges or the SQLite write-through mirror.
    decision: Keep the store.* write path unchanged; read operations are the live adapter consumer. Revisit when Phase 13/14 certification and provenance work can lift the protocol.
closed:
  - truth: Core recall operations run through a generic StorageAdapter.
    requirements: [ADAPT-02]
    resolution: _prefetch_entries reads through the selected adapter; _tool_search fetches rows through NotionAdapter.search, including a database-scoped delegation that preserves existing filtering and catalog mapping.
    evidence: tests/test_adapters.py::test_provider_prefetch_uses_notion_adapter, test_provider_search_uses_notion_adapter
  - truth: The free tier defaults to NotionAdapter.
    requirements: [ADAPT-02]
    resolution: initialize() always constructs NotionAdapter; the adapter name remains "notion" unless an entitled premium backend is selected.
    evidence: tests/test_adapters.py::test_provider_initialize_wires_notion_adapter
  - truth: Premium backend selection is entitlement-gated and falls back gracefully.
    requirements: [ADAPT-03]
    resolution: initialize() resolves storage_adapter through adapters.get_adapter, catches EntitlementError, logs a redacted upgrade/fallback warning, and continues on Notion. The strict factory contract is unchanged.
    evidence: tests/test_adapters.py::test_provider_premium_selection_falls_back_when_unentitled, test_get_adapter_entitlement_and_defaults
  - truth: The entitled Obsidian vault backend participates in recall.
    requirements: [ADAPT-03, ADAPT-04]
    resolution: An entitled selection stores the ObsidianVaultAdapter; its flat rows are normalized into the provider row shape and merged into unscoped search results without changing database-scoped search.
    evidence: tests/test_adapters.py::test_provider_selects_entitled_obsidian_adapter, test_provider_search_merges_entitled_vault_rows, test_obsidian_round_trip_and_sqlite_index
---

# Phase 11 verification record

Phase 11 is verified for its scoped contract. ADAPT-01 and ADAPT-04 were already implemented and covered at `71e7122`; this pass closed the missing provider connection (ADAPT-02) and the runtime selection/fallback flow (ADAPT-03).

## Verification scope

- Targeted suite: `tests/test_adapters.py` — **13 passed**, including seven new provider-wiring regressions.
- Full repository gate: **568 passed, 1 deselected in 5.59s**. The pre-change baseline was 561 passed; the seven new regressions account for the delta.
- Ruff: clean (`notion_brain`, `tests`). Mypy: no issues (`notion_brain`).
- No live Notion workspace call, live vault write, network access or external confirmation UI was used.

## Key implementation evidence

`notion_brain/provider.py`:

- `initialize()` wires `NotionAdapter` on every session and resolves `storage_adapter` through `adapters.get_adapter` with `obsidian_vault` passthrough.
- `EntitlementError` downgrades the session to Notion with a redacted warning; the session still initializes.
- `_prefetch_entries` selects the premium vault adapter when entitled, otherwise the Notion adapter, and retains the direct `store` fallback for uninitialized providers.
- `_tool_search` fetches through `NotionAdapter.search`; `database_id` preserves the per-database path, and the all-database loop keeps its existing exception isolation and `entry_databases` mapping.
- Entitled vault rows are normalized by `_adapter_entry` and merged by `_merge_adapter_entries` for unscoped search.
- Catalog locator resolution reuses the provider's adapters instead of constructing per-search instances.

`notion_brain/adapters.py`:

- `NotionAdapter.search(query, limit, *, database_id=None)` delegates to `store.query_database` when scoped and keeps the previous `store.search_entries` behavior otherwise. The existing adapter contract test remains unchanged.

`tests/test_adapters.py`:

- Seven regressions cover adapter routing, free-tier default, entitlement fallback, entitled selection, premium result merging, and cache/graph isolation.

## Known ceiling

The Memory write path still calls `store.*` directly. `StorageAdapter.remember`/`supersede` are implemented and tested, but the provider write path carries certification, provenance, reuse-or-create, graph and cache-mirror semantics that the generic protocol does not model. Wiring it through `remember()` today would silently drop Truth, Kind, Confidence, Tags, Entities, Source Session and custom metadata. The plan records this as the ADAPT-02 ceiling rather than claiming full write-path abstraction.

## Remaining scope

Phase 12 (semantic catalog closure evidence), Phase 13 (certification-failure isolation), Phase 14 (provenance/audit continuity) and Phase 15 (answerability closure) remain open in the milestone audit. Phase 11 verification does not mark the milestone released or merged to `main`.
