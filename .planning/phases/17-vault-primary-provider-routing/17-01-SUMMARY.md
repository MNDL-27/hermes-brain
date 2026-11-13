---
phase: 17-vault-primary-provider-routing
plan: "01"
subsystem: obsidian-vault
tags: [obsidian, provider, routing, certification, search, status]
requires:
  - phase: 16-vault-note-schema-write-operations
    provides: Vault note/index v2, idempotent writes, supersede and certify
provides:
  - Vault-primary Memory write and certification routing
  - Fail-closed vault errors with no Notion fallback
  - Vault-first search with Notion fallback
  - Vault path resolution and provider status surface
affects: [18-bidirectional-sync-migration]
tech-stack:
  added: []
  patterns: [capability-gated provider routing, fail-closed premium writes, vault-first retrieval]
key-files:
  created: []
  modified:
    - notion_brain/adapters.py
    - notion_brain/provider.py
    - tests/test_adapters.py
key-decisions:
  - Premium Memory writes branch inside `_write_entry_raw`, covering explicit remember, background ingestion and direct callers.
  - A vault failure raises a generic redacted RuntimeError and never falls back to Notion.
  - Ordinary supersession skips certified peers; certification supersedes only inferred peers.
  - Search uses the vault when the filter is absent or `memory`; Notion is consulted only when the vault returns no rows.
  - The vault path resolves from `obsidian_vault`, then `HERMES_OBSIDIAN_VAULT`; `vault_status` reports backend, entitlement, path, health and `last_sync=not_run`.
requirements-completed: [OBS-03, SYNC-03]
coverage:
  - id: D1
    description: Memory writes route to the vault and fail closed.
    requirement: OBS-03
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_provider_vault_primary_remember_writes_note_not_notion
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_provider_vault_write_failure_fails_closed
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_provider_vault_supersede_retains_history_and_edge
        status: pass
    human_judgment: false
  - id: D2
    description: Vault certification respects confirmation and protects certified facts.
    requirement: OBS-03
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_provider_vault_certify_flips_truth_and_supersedes_inferred_peer
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_obsidian_supersede_skips_certified_peer
        status: pass
    human_judgment: false
  - id: D3
    description: Search is vault-first and the status surface exposes configuration/health.
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_provider_vault_search_prefers_vault_and_falls_back
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_provider_vault_status_and_env_path
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-13
---

# Phase 17 plan 01 summary

**Premium Memory writes, certification and supersession now live in the vault, with fail-closed errors and vault-first retrieval**

## Performance

- **Tasks:** 4
- **Files modified:** 3
- **Commits:** pending review

## Accomplishments

- `_write_entry_raw` branches Memory-domain writes to `_store_vault_entry` when the vault is enabled; Notion is never mutated.
- Exact active matches are reused; changed subjects call the adapter's certified-safe `supersede`, and graph `supersedes`/entity edges are written after acceptance.
- Vault failures raise `RuntimeError("Failed to save entry to the Obsidian vault")` with redacted diagnostics and no Notion fallback.
- `_tool_certify` routes to `_certify_vault` after the exact per-call confirmation gate; the target becomes certified and inferred peers are superseded.
- Search is vault-first for no filter or `memory`; a non-empty vault result skips Notion, and an empty result falls back to the Notion memory query.
- `initialize` resolves the vault path from the kwarg or `HERMES_OBSIDIAN_VAULT`; `vault_status()` reports backend, entitlement, path, counts, schema version and `last_sync`.
- Adapter helpers `find`, `list_active`, `supersede_inferred` and certified-safe supersession support the routing.

## Evidence

- Adapter suite: **28 passed in 0.42s** (eight new regressions).
- Full repository gate: **596 passed, 1 deselected in 5.73s** (Phase 16 baseline 588 plus eight tests).
- Ruff, mypy and whitespace clean.

## Decisions Made

- Fail closed rather than split data across backends.
- Vault-only Notion in premium mode; migration remains Phase 18.
- Vault-first search with a fallback until bootstrap exists.
- Provider-boundary status now; operational CLI/UX in Phase 18.

## Deviations from Plan

None — all four planned tasks were implemented as specified.

## Issues Encountered

None.

## User Setup Required

Set `HERMES_OBSIDIAN_VAULT` or pass `obsidian_vault` when selecting the premium adapter.

## Next Phase Readiness

Phase 18 can bootstrap Notion memories into the vault and ingest vault notes back to Notion using the now-vault-primary write path and status surface.

## Self-Check

All checks passed: eight new regressions, the 596-test full gate, and static checks are green.
