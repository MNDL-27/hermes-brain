# Phase 18: Bidirectional Sync & Migration - Context

**Gathered:** 2026-11-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver SYNC-01 and SYNC-02: an explicit Notion→vault bootstrap that exports active Memory rows to stable vault notes, and a vault→Notion ingest that promotes `agents/memory.md` and `journal/*.md` entries through the Notion write path with content-hash dedupe, a unified state file, redaction and idempotent re-runs. Expose both as `notion_brain vault` subcommands. No daemon; no section refs or licensing (Phases 19–20).

</domain>

<decisions>
## Implementation Decisions

### Bootstrap trigger
- **D-01:** Bootstrap runs only through an explicit command; provider startup never performs a Notion→vault migration automatically. — **Reversibility:** reversible — an automatic trigger can be layered on later without changing the export format.

### Command surface
- **D-02:** Add `notion_brain vault bootstrap|sync|status` subcommands to the existing argparse CLI. Bootstrap and ingest remain importable functions for host timers. — **Reversibility:** reversible — subcommands can be extended or aliased.

### Ingest truth
- **D-03:** `agents/memory.md` entries ingest as `certified` (curated durable knowledge); `journal/*.md` entries ingest as `inferred` (logs). — **Reversibility:** costly — changing truth later alters ranking and certification semantics for already-written rows.

### Sync state
- **D-04:** Use a unified `$HERMES_HOME/vault_sync_state.json` with bootstrap ids and ingest title→hash entries plus `last_run`/`last_bootstrap`. Migrate the existing `vault_notion_mirror_state.json` once, preserving its entries. — **Reversibility:** costly — a state-format change after users run sync risks duplicate re-ingestion.

### Claude's Discretion
- Reuse the existing `agents/memory.md` and `journal/*.md` parsers from the script; factor them into a module.
- Dry-run flag and machine-readable JSON output.
- Error collection per entry with a bounded error list.
- How bootstrap reports skipped-existing and failed notes.
- Whether status merges the existing `vault_status()` or adds sync-specific fields.

### Folded Todos
None.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` § Phase 18 — goal and success criteria (SYNC-01, SYNC-02).
- `.planning/REQUIREMENTS.md` — SYNC-01 and SYNC-02, plus v1.5 scope fences.
- `.planning/research/2026-11-13-obsidian-vault-backend.md` — sync, ingest and state decisions.
- `.planning/phases/17-vault-primary-provider-routing/17-CONTEXT.md` — vault-only Notion and fail-closed routing.

### Code
- `scripts/mirror_vault_to_notion.py` — existing parsers, state format, dedupe and `_store_entry` ingest.
- `notion_brain/__main__.py` — argparse command surface and existing `import` command patterns.
- `notion_brain/provider.py` — `_store_entry`, Notion SQLite mirror, vault-primary branching; ingest must force the Notion backend.
- `notion_brain/adapters.py` — vault `remember` for bootstrap exports.
- `notion_brain/bootstrap.py` — cache/database ids and health.
- `tests/test_adapters.py`, `tests/test_provider.py` — provider contracts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `parse_memory_entries`, `parse_journal_entries`, `entry_hash` and the state shape from the mirror script.
- `provider._store_entry` for Redaction + subject inference + title dedupe.
- `ObsidianVaultAdapter.remember` for bootstrap exports with stable ids (`page_id` as note id).
- `vault_status()` for the status command.

### Established Patterns
- Provider `initialize(storage_adapter="notion")` forces the free-tier write path even when a license/vault is configured.
- State files are atomic with `0o600` in existing cache writers.
- Commands return exit codes and JSON for automation.

### Integration Points
- `notion_brain/__main__.py` subparsers.
- New module (e.g. `notion_brain/vault_sync.py`) for bootstrap/ingest/state.
- Vault adapter for export; Notion provider for ingest.

</code_context>

<specifics>
## Specific Ideas

- Bootstrap should be idempotent: skip an existing note id and report `skipped`.
- Ingest must not re-ingest vault-managed notes (`<vault>/hermes-brain/`), only the configured source folders.
- A `--dry-run` must report counts without writing either store.
- Errors must be redacted and capped (the script already caps at 10).

</specifics>

<deferred>
## Deferred Ideas

- Automatic first-run bootstrap — explicit command chosen for v1.5.
- Background sync daemon — timers call the command.
- Whole-vault ingestion or knowledge-note classification — only `agents/memory.md` and `journal/*.md`.
- Migrating non-Memory domains.

</deferred>

---

*Phase: 18-Bidirectional Sync & Migration*
*Context gathered: 2026-11-13*
