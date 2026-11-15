# Phase 18: Bidirectional Sync & Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-13
**Phase:** 18-bidirectional-sync-migration
**Areas discussed:** Bootstrap trigger, CLI surface, Ingest truth, Sync state

---

## Bootstrap trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit command | User runs `notion_brain vault bootstrap`; no startup network or surprise writes. | ✓ |
| Automatic on first selection | Run when premium is selected and the vault index is empty. | |
| Both | Explicit plus automatic empty-vault run. | |

**User's choice:** Explicit command
**Notes:** Provider startup stays network-free.

---

## CLI surface

| Option | Description | Selected |
|--------|-------------|----------|
| Vault subcommands | `notion_brain vault bootstrap|sync|status`. | ✓ |
| Importable module only | Python API for hosts/timers. | |
| Keep the script | Promote the existing script with env configuration. | |

**User's choice:** Vault subcommands
**Notes:** Functions remain importable for timers.

---

## Ingest truth

| Option | Description | Selected |
|--------|-------------|----------|
| Memory certified, journal inferred | Curated memory is certified; logs stay inferred. | ✓ |
| All certified | Preserve the script's behavior. | |
| All inferred | Treat ingestion as agent-derived. | |

**User's choice:** Memory certified, journal inferred
**Notes:** Distinguishes durable knowledge from logs.

---

## Sync state

| Option | Description | Selected |
|--------|-------------|----------|
| Unified state file | `$HERMES_HOME/vault_sync_state.json` with bootstrap ids and ingest hashes; migrate the old mirror state. | ✓ |
| Keep the old file | Extend `vault_notion_mirror_state.json`. | |
| Separate files | One per direction. | |

**User's choice:** Unified state file
**Notes:** One-time migration preserves existing dedupe history.

---

## Claude's Discretion

- Parser/module factoring.
- Dry-run and JSON output.
- Error cap and reporting.
- Status field composition.

## Deferred Ideas

- Automatic bootstrap.
- Background daemon.
- Whole-vault ingestion.
- Non-Memory domain migration.
