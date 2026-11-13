# Phase 17: Vault-Primary Provider Routing - Context

**Gathered:** 2026-11-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Route Memory-domain `remember`, `certify` and `supersede` operations through the selected `ObsidianVaultAdapter` when `storage_adapter="obsidian"` is entitled and selected. Deliver the vault path configuration and health/sync reporting surface (OBS-03, SYNC-03). Non-Memory domains stay on Notion. Notion↔vault migration and ingest, section refs and the signed license remain Phases 18–20.

</domain>

<decisions>
## Implementation Decisions

### Write failure behavior
- **D-01:** A failed vault write is fatal for that call. Return a clear error and do not write to Notion. — **Reversibility:** costly — switching to a fallback or queue later changes the provider contract and user expectations about where data lives.

### Notion's role
- **D-02:** When Obsidian is selected, Memory reads and writes are vault-only; the provider does not mutate Notion. Migration and mirroring are Phase 18. — **Reversibility:** costly — enabling a live mirror later requires reconciliation and duplicate handling.

### Search scope
- **D-03:** Provider search is vault-first: return vault matches when present; consult Notion only when the vault has no match. This protects existing memories until the Phase 18 bootstrap runs. — **Reversibility:** reversible — the fallback can be removed once migration is complete.

### Vault configuration
- **D-04:** Resolve the vault path from the `obsidian_vault` provider kwarg, falling back to `HERMES_OBSIDIAN_VAULT`. Expose configuration and sync/health status through the provider boundary; richer CLI/config comes with SYNC-03. — **Reversibility:** reversible — env/kwarg resolution is a small, local contract.

### Claude's Discretion
- Whether the routing branch lives in `_store_entry`/`_write_entry_raw` or a dedicated `_vault_write` helper.
- How to preserve certification confirmation semantics while calling `adapter.certify`.
- Graph-edge ordering relative to accepted vault transitions (must remain after acceptance).
- Health payload shape beyond the required note count, index path, last sync/result and entitlement state.
- Whether to reuse the existing vault row merge helper for the Notion fallback.

### Folded Todos
None.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` § Phase 17 — goal and success criteria.
- `.planning/REQUIREMENTS.md` — OBS-03 and SYNC-03; v1.5 scope fences.
- `.planning/research/2026-11-13-obsidian-vault-backend.md` — vault-primary, write semantics, sync, entitlement decisions.
- `.planning/phases/16-vault-note-schema-write-operations/16-CONTEXT.md` — Phase 16 schema and write semantics (if present).
- `.planning/phases/16-vault-note-schema-write-operations/16-VERIFICATION.md` — verified adapter capabilities.

### Code
- `notion_brain/provider.py` — `_store_entry`, `_write_entry_raw`, `_reuse_or_create_memory`, `_supersede_matching_active`, `_tool_certify`, `_prefetch_entries`, `_tool_search`, adapter selection in `initialize`.
- `notion_brain/adapters.py` — `ObsidianVaultAdapter` remember/supersede/certify/get_note/health, `get_adapter`.
- `notion_brain/catalog.py` — supersedes relation edges and graph traversal.
- `notion_brain/brain_cache.py` — Notion read-through cache (not the premium path).
- `tests/test_adapters.py`, `tests/test_certification.py`, `tests/test_supersession.py`, `tests/test_provenance.py` — existing contracts to preserve.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ObsidianVaultAdapter.remember/supersede/certify` from Phase 16 — complete write semantics.
- `_adapter_entry` / `_merge_adapter_entries` — normalize and merge premium rows.
- `_provenance` and the certification gate — reuse for vault writes and certification.
- `semantic_catalog.Relation` — supersedes edges are backend-independent.

### Established Patterns
- Provider adapter selection happens in `initialize`; `_adapter_name` and `_obsidian_adapter` are already wired for reads.
- Accepted-state success boundary: auxiliary graph/cache work is isolated.
- Free-tier behavior must remain unchanged; tests patch `store.*` extensively.

### Integration Points
- `_store_entry` / `_write_entry_raw` for Memory-domain writes and reuse-or-create.
- `_tool_certify` for truth flips and predecessor supersession.
- `_prefetch_entries` / `_tool_search` for vault reads and the Notion fallback.
- `health` / provider reporting for SYNC-03.

</code_context>

<specifics>
## Specific Ideas

- Fail-closed error should name the vault path issue and the Notion fallback option, without printing secrets.
- Vault-first search should only fall back when the vault returns zero matches, not when it returns few.
- Health should report: note count, index path, schema version, entitlement state, and last sync outcome (even if "not run" in this phase).

</specifics>

<deferred>
## Deferred Ideas

- Durable write queue/retry for vault failures — future phase if fail-closed proves too strict.
- Notion mirror writes and bidirectional reconciliation — Phase 18.
- Persistent config file and full CLI for the vault path — SYNC-03/Phase 18.
- Migrating non-Memory domains to the vault — beyond v1.5.

</deferred>

---

*Phase: 17-Vault-Primary Provider Routing*
*Context gathered: 2026-11-13*
