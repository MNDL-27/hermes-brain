# Requirements: hermes-brain

**Defined:** 2026-11-13 (v1.5 intake — Obsidian Vault Backend)
**Core Value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.

**Current work:** v1.5 — Obsidian Vault Backend. v1.4 requirements were archived to `.planning/milestones/v1.4-REQUIREMENTS.md`.

## v1.5 Requirements

Derived from the confirmed v1.5 design decisions in [2026-11-13-obsidian-vault-backend.md](research/2026-11-13-obsidian-vault-backend.md). The vault becomes a real premium backend, not only a read-side scaffold.

### Vault Storage (OBS)

- [x] **OBS-01**: Adapter-managed notes carry the full memory schema in frontmatter and the SQLite index: title, subject key, status, truth, source agent/session, created/updated timestamps, domain, kind, tags and supersession link. Existing v1 notes are read with defaults; migration is additive and non-destructive.
- [x] **OBS-02**: `ObsidianVaultAdapter` implements idempotent remember, history-preserving supersede, certification and lookup with secret redaction on every written field. Identical active entries reuse the existing note; changed entries create a new note; non-identical active peers are superseded without deletion.
- [x] **OBS-03**: When `storage_adapter="obsidian"` is selected and entitled, the provider routes Memory-domain remember, certify and supersede operations to the vault, including certification protection and graph edges. Free-tier Notion behavior is unchanged; non-Memory domains remain on Notion in v1.5.

### Sync & Migration (SYNC)

- [x] **SYNC-01**: A first-run or explicit Notion→vault bootstrap exports active Memory rows to stable vault notes, preserving truth, provenance, subject key and creation time. Re-runs skip existing notes and report what was skipped.
- [x] **SYNC-02**: A supported vault→Notion ingest command promotes `agents/memory.md` and `journal/*.md` entries through `NotionBrainProvider._store_entry`, with content-hash dedupe, a state file, redaction and idempotent re-runs. The package does not start a background daemon.
- [x] **SYNC-03**: Vault path configuration, sync status and health reporting are available through the provider boundary and CLI/config, including note count, index path, last sync result and entitlement state.

### References & Entitlement (REF/ENT)

- [ ] **REF-01**: Catalog storage references support section locators (`note.md#section`); resolution is confined to the vault, heading matching is case-insensitive, and a missing section falls back to the whole note with a warning.
- [ ] **ENT-01**: Premium selection verifies an offline Ed25519-signed license (canonical JSON payload + base64 signature) with subject, issued/expiry dates and an `obsidian` feature. Invalid, expired or missing licenses raise a clear `EntitlementError` and fall back to Notion. The signing dependency is `cryptography`; tests use a throwaway keypair.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| OBS-01 | Phase 16 | Verified — 16-01 schema and migration evidence |
| OBS-02 | Phase 16 | Verified — 16-01 idempotency, history, certification and redaction |
| OBS-03 | Phase 17 | Verified — vault-primary write/certify/supersede routing |
| SYNC-01 | Phase 18 | Verified — bootstrap export and idempotent re-runs |
| SYNC-02 | Phase 18 | Verified — ingest with hash dedupe, truth levels and redaction |
| SYNC-03 | Phase 17 | Verified — path resolution and vault status |
| REF-01 | Phase 19 | Pending |
| ENT-01 | Phase 20 | Pending |

**Coverage:**
- v1.5 requirements: 8 total
- Mapped to phases: 8 ✓
- Dropped: 0 / Adjusted: 0
- Deferred: 0

## Out of Scope (v1.5)

| Feature | Reason |
|---------|--------|
| Online license server / account system | Offline-first constraint; signed local license is sufficient. |
| Whole-vault editing | Only `<vault>/hermes-brain/` is adapter-managed; external folders are ingest-only. |
| Non-Memory domain migration to the vault | Tasks/projects/content/research/career/entities stay on Notion in v1.5. |
| Background sync daemon | Sync is command- or timer-driven; the package starts no daemon. |
| Silent auto-mutation of user notes | Bootstrap skips existing notes; supersede marks history but never deletes. |

---
*Requirements defined: 2026-11-13.*
