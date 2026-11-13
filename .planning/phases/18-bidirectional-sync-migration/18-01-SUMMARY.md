---
phase: 18-bidirectional-sync-migration
plan: "01"
subsystem: obsidian-vault
tags: [obsidian, sync, migration, cli, state]
requires:
  - phase: 17-vault-primary-provider-routing
    provides: Vault-primary writes, vault-only Notion, entitlement and vault status
provides:
  - Explicit Notion→vault bootstrap with stable ids and idempotent re-runs
  - Vault→Notion ingest for agents/memory.md and journal/*.md with hash dedupe
  - Unified sync state with legacy migration
  - `notion_brain vault bootstrap|sync|status` CLI
affects: [19-section-aware-references]
tech-stack:
  added: []
  patterns: [explicit bidirectional sync, atomic sync state, force-Notion ingest, per-entry error isolation]
key-files:
  created:
    - notion_brain/vault_sync.py
    - tests/test_vault_sync.py
  modified:
    - notion_brain/__main__.py
key-decisions:
  - Both directions are explicit commands; provider startup never migrates automatically.
  - Ingest forces `storage_adapter="notion"` so premium selection cannot redirect entries into the vault.
  - `agents/memory.md` ingests certified; journal entries ingest inferred.
  - Unified `$HERMES_HOME/vault_sync_state.json` with a one-time legacy migration and atomic 0600 writes.
  - Bootstrap skips ids already in the vault or state; ingest skips unchanged title hashes.
requirements-completed: [SYNC-01, SYNC-02]
coverage:
  - id: D1
    description: Bootstrap exports active Notion Memory into stable vault notes and is idempotent.
    requirement: SYNC-01
    verification:
      - kind: unit
        ref: tests/test_vault_sync.py::test_bootstrap_exports_and_skips
        status: pass
      - kind: unit
        ref: tests/test_vault_sync.py::test_bootstrap_dry_run_writes_nothing
        status: pass
      - kind: unit
        ref: tests/test_vault_sync.py::test_bootstrap_requires_entitlement
        status: pass
    human_judgment: false
  - id: D2
    description: Ingest is deduped, truth-aware, redacted and idempotent.
    requirement: SYNC-02
    verification:
      - kind: unit
        ref: tests/test_vault_sync.py::test_ingest_writes_pending_then_noop
        status: pass
      - kind: unit
        ref: tests/test_vault_sync.py::test_ingest_error_isolation_and_redaction
        status: pass
      - kind: unit
        ref: tests/test_vault_sync.py::test_legacy_state_migrates_to_unified_shape
        status: pass
    human_judgment: false
  - id: D3
    description: The vault CLI exposes both directions and status.
    requirement: SYNC-01, SYNC-02
    verification:
      - kind: unit
        ref: tests/test_vault_sync.py::test_cli_vault_status_json
        status: pass
      - kind: unit
        ref: tests/test_vault_sync.py::test_cli_vault_sync_dry_run
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-13
---

# Phase 18 plan 01 summary

**Notion and the vault can now be synced explicitly in both directions, idempotently and without a daemon**

## Performance

- **Tasks:** 3
- **Files modified:** 3
- **Commits:** pending review

## Accomplishments

- New `notion_brain/vault_sync.py`: state load/save/migration, vault path resolution, memory/journal parsers, hash dedupe, bootstrap, ingest and status.
- Bootstrap exports active Notion Memory rows with stable page ids, preserves truth/provenance/timestamps, skips existing notes and reports counts.
- Ingest forces the Notion backend, applies certified/inferred truth by source, dedupes by title hash, isolates per-entry failures and caps redacted errors.
- Unified `vault_sync_state.json` migrates the legacy mirror state once and writes atomically with `0o600`.
- CLI: `notion_brain vault bootstrap|sync|status` with `--vault`, `--json` and `--dry-run`; status runs without an API key.

## Evidence

- Sync suite: **11 passed in 0.21s**.
- Full repository gate: **607 passed, 1 deselected in 5.67s** (Phase 17 baseline 596 plus 11 tests).
- Ruff, mypy and whitespace clean.

## Decisions Made

- Explicit commands only; no startup migration.
- Force-Notion ingest to avoid premium redirection.
- Memory certified / journal inferred.
- Unified state with legacy migration.

## Deviations from Plan

None — the three planned tasks were implemented as specified.

## Issues Encountered

Ruff import ordering and a mypy protocol-narrowing issue were fixed before the final gate.

## User Setup Required

Configure a vault path (`--vault`, `HERMES_OBSIDIAN_VAULT`, or `AGENT_BRAIN_VAULT`) and run `notion_brain vault bootstrap|sync`.

## Next Phase Readiness

Phase 19 can extend catalog references to `note.md#section`; the sync module is independent.

## Self-Check

All checks passed: 11 sync regressions, the 607-test full gate and static checks are green.
