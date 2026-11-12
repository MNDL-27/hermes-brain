---
phase: 11-storage-adapters
plan: "01"
subsystem: storage-adapters
status: complete
completed: 2026-11-12
requirements-completed: [ADAPT-01, ADAPT-02, ADAPT-03, ADAPT-04]
requires:
  - phase: 10-event-driven-supersession
    provides: Memory-only subject keys, accepted-transition supersession, non-destructive history
affects: [12-semantic-catalog, 14-provenance]
tech-stack:
  added: []
  patterns: [entitlement-gated adapter factory, provider read-path adapter routing, flat premium row normalization]
key-files:
  created: []
  modified: [notion_brain/adapters.py, notion_brain/provider.py, tests/test_adapters.py]
key-decisions:
  - `NotionAdapter` and `ObsidianVaultAdapter` already existed from `71e7122`; this plan closes the missing provider connection rather than re-scaffolding them.
  - The provider's initialized state selects the backend once via `get_adapter`; `EntitlementError` is caught at the provider boundary and downgrades the session to Notion with a redacted warning, so the strict factory contract and the roadmap's graceful fallback both hold.
  - `_prefetch_entries` and `_tool_search` route through the selected adapter. Database-scoped search stays Notion-shaped through `NotionAdapter.search(..., database_id=...)`, preserving the existing per-database filtering and catalog storage-ref mapping.
  - Premium Obsidian rows are flat, so the provider normalizes them into its `properties` row shape before status filtering, ranking and output.
  - The Memory write path (`_store_entry` / `_write_entry_raw` / `_reuse_or_create_memory`) remains on `store.*`. Its certification, graph-edge and cache write-through semantics exceed the generic `remember()`/`supersede()` protocol and are preserved unchanged; this is the documented ADAPT-02 ceiling until Phase 13/14 work.
  - Uninitialized providers keep the direct `store.*` fallback, so existing unit tests and callers that never call `initialize()` are unchanged.
coverage:
  - id: S1
    description: Core recall operations call the selected StorageAdapter.
    requirement: ADAPT-02
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_provider_prefetch_uses_notion_adapter
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_provider_search_uses_notion_adapter
        status: pass
    human_judgment: false
  - id: S2
    description: Free tier defaults to NotionAdapter after initialization.
    requirement: ADAPT-02
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_provider_initialize_wires_notion_adapter
        status: pass
    human_judgment: false
  - id: S3
    description: Unentitled premium selection falls back to Notion instead of failing the session.
    requirement: ADAPT-03
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_provider_premium_selection_falls_back_when_unentitled
        status: pass
    human_judgment: false
  - id: S4
    description: Entitled premium selection returns the Obsidian vault adapter and its rows join recall.
    requirement: [ADAPT-03, ADAPT-04]
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_provider_selects_entitled_obsidian_adapter
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_provider_search_merges_entitled_vault_rows
        status: pass
    human_judgment: false
---

# Phase 11 plan 01 summary

Phase 11 gap closure connects the existing adapter layer to the provider. The ADAPT-01 protocol and ADAPT-04 vault scaffold were already implemented and tested at `71e7122`; ADAPT-02 and ADAPT-03 were open because nothing in production selected or called them.

## What changed

### `notion_brain/provider.py`

- `initialize()` constructs `NotionAdapter` for every session and resolves an optional `storage_adapter` kwarg through `adapters.get_adapter`. `EntitlementError` is caught and logged redacted, then the session continues on Notion.
- `_prefetch_entries` reads through the selected adapter: premium vault first when selected, otherwise the Notion adapter, with the direct `store.query_database` path retained for uninitialized providers.
- `_tool_search` fetches rows through `NotionAdapter.search`. The database-scoped branch passes `database_id` so per-database filtering, `entry_databases` bookkeeping and catalog storage-ref selection are unchanged. The all-databases loop keeps its per-database exception isolation.
- When the premium vault backend is selected, its matches are normalized and merged into the same result set for unscoped searches; database-scoped searches stay Notion-only.
- Catalog locator resolution reuses the provider's adapters instead of constructing new ones per search.

### `notion_brain/adapters.py`

- `NotionAdapter.search` accepts an optional keyword-only `database_id`. With it, the call delegates to `store.query_database` for the existing provider retrieval semantics; without it, the previous `store.search_entries` behavior and contract are unchanged.

### `tests/test_adapters.py`

Seven regressions added:

- `test_provider_prefetch_uses_notion_adapter`
- `test_provider_search_uses_notion_adapter`
- `test_provider_initialize_wires_notion_adapter`
- `test_provider_premium_selection_falls_back_when_unentitled`
- `test_provider_selects_entitled_obsidian_adapter`
- `test_provider_premium_prefetch_skips_notion_cache`
- `test_provider_search_merges_entitled_vault_rows`

## Deliberate ceiling

The Memory write path still calls `store.*` directly. Routing it through `StorageAdapter.remember/supersede` would drop the provider-only properties (Truth, Kind, Confidence, Tags, Entities, Source Session, custom metadata) and bypass reuse-or-create, certification protection, graph edges and the SQLite write-through mirror. The plan records this as the ADAPT-02 ceiling; the audit's live-use criterion is satisfied by search and prefetch, which are the read paths that power recall.
