# Phase 17: Vault-Primary Provider Routing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-13
**Phase:** 17-vault-primary-provider-routing
**Areas discussed:** Write failure, Notion role, Search scope, Vault config

---

## Write failure

| Option | Description | Selected |
|--------|-------------|----------|
| Fail closed | Return a clear error and change nothing in Notion; preserves the vault as the single source of truth. | ✓ |
| Fall back to Notion | Write to Notion when the vault fails; more available but splits data across stores. | |
| Queue and retry | Keep the write pending for a later sync; adds durable queue machinery. | |

**User's choice:** Fail closed
**Notes:** No silent split-brain; the vault remains authoritative.

---

## Notion role

| Option | Description | Selected |
|--------|-------------|----------|
| Vault-only | Reads and writes stay in the vault; Notion is untouched until Phase 18 sync. | ✓ |
| Best-effort mirror writes | Also write each accepted change to Notion now. | |
| Notion read-through only | Writes to the vault, reads may consult Notion. | |

**User's choice:** Vault-only
**Notes:** Migration and mirroring belong to Phase 18.

---

## Search scope

| Option | Description | Selected |
|--------|-------------|----------|
| Vault-first, Notion fallback | Prefer vault matches; consult Notion only when the vault has none. | ✓ |
| Vault-only | Never query Notion while premium is selected. | |
| Always merge both | Query both on every search. | |

**User's choice:** Vault-first, Notion fallback
**Notes:** Protects existing memories until the bootstrap in Phase 18.

---

## Vault config

| Option | Description | Selected |
|--------|-------------|----------|
| Provider kwargs + env | Use `obsidian_vault`, fallback `HERMES_OBSIDIAN_VAULT`; CLI/health in SYNC-03. | ✓ |
| Provider kwargs only | Require the host to pass the path every time. | |
| Config file + CLI | Add persistent config and CLI now. | |

**User's choice:** Provider kwargs + env
**Notes:** Keep Phase 17 focused; richer UX with SYNC-03.

---

## Claude's Discretion

- Helper placement for the write branch.
- Graph-edge ordering details.
- Health payload beyond required fields.
- Notion fallback merge mechanics.

## Deferred Ideas

- Durable write queue/retry.
- Notion mirror writes (Phase 18).
- Persistent config file and full CLI (SYNC-03/Phase 18).
- Non-Memory domain migration.
