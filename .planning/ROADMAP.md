# Roadmap: hermes-brain

## Milestones

- ✅ **v1.0 Release Polish** — Phases 1-3 (shipped 2026-09-21)
- ✅ **v1.1 Distribution & Updates** — Phases 4-6 (shipped 2026-10-07)
- ✅ **v1.2 Update UX & Tooling Polish** — Phases 7-8 (shipped 2026-11-07)
- ✅ **v1.3 Brain Architecture & Freemium Foundation** — Phases 9-11 (shipped 2026-11-13)
- ✅ **v1.4 Semantic Brain Layer** — Phases 12-15 (shipped 2026-11-13)
- 🚧 **v1.5 Obsidian Vault Backend** — Phases 16-20 (in progress)

**Current route:** `/gsd-discuss-phase 16` then `/gsd-plan-phase 16`. The vault becomes a real premium backend with vault-primary writes, bidirectional sync, section-aware references and offline signed entitlement.

## Phases

<details>
<summary>✅ v1.0 Release Polish (Phases 1-3) — SHIPPED 2026-09-21</summary>

- [x] Phase 1: Config Schema Test Infrastructure (1/1 plans) — completed 2026-09-20
- [x] Phase 2: Pre-Commit Quality Gates & Tooling Parity (1/1 plans) — completed 2026-09-20
- [x] Phase 3: Platform Portability & Installation Guard (1/1 plans) — completed 2026-09-20

Full phase details archived to: [.planning/milestones/v1.0-ROADMAP.md](.planning/milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Distribution & Updates (Phases 4-6) — SHIPPED 2026-10-07</summary>

- [x] Phase 4: Build Metadata Modernization & PyPI Publishing (2/2 plans) — completed 2026-09-26
- [x] Phase 5: CLI Update Drift Detection (1/1 plans) — completed 2026-09-29
- [x] Phase 6: Cached Non-Blocking Auto-Update Check (1/1 plans) — completed 2026-10-07

Full phase details archived to: [.planning/milestones/v1.1-ROADMAP.md](.planning/milestones/v1.1-ROADMAP.md)

</details>

<details>
<summary>✅ v1.2 Update UX & Tooling Polish (Phases 7-8) — SHIPPED 2026-11-07</summary>

- [x] Phase 7: Update UX — Commit-Level Drift + Release-Notes Link (2/2 plans) — completed 2026-11-07
- [x] Phase 8: Developer Tooling & Test Reliability (2/2 plans) — completed 2026-11-07

Full phase details archived to: [.planning/milestones/v1.2-ROADMAP.md](.planning/milestones/v1.2-ROADMAP.md)

</details>

<details>
<summary>✅ v1.3 Brain Architecture & Freemium Foundation (Phases 9-11) — SHIPPED 2026-11-13</summary>

- [x] Phase 9: Retrieval Correctness & Local Read-Through Cache (1/1 plans) — completed 2026-11-09
- [x] Phase 10: Event-Driven Supersession & Truth Integrity (1/1 plans) — completed 2026-11-09
- [x] Phase 11: Storage Adapter Abstraction & Freemium Gate (1/1 plans) — completed 2026-11-12

Full phase details archived to: [.planning/milestones/v1.3-ROADMAP.md](.planning/milestones/v1.3-ROADMAP.md)

</details>

<details>
<summary>✅ v1.4 Semantic Brain Layer (Phases 12-15) — SHIPPED 2026-11-13</summary>

- [x] Phase 12: Core Semantic Catalog (1/1 plans) — completed 2026-11-12
- [x] Phase 13: User-Gated Certification Flow (1/1 plans) — completed 2026-11-12
- [x] Phase 14: Graph Provenance & Relational Recall (1/1 plans) — completed 2026-11-12
- [x] Phase 15: Answerability Gate & Contradiction Detection (1/1 plans) — completed 2026-11-12

Full phase details archived to: [.planning/milestones/v1.4-ROADMAP.md](.planning/milestones/v1.4-ROADMAP.md)

Verification: [v1.4-MILESTONE-AUDIT.md](.planning/milestones/v1.4-MILESTONE-AUDIT.md) — all four phases passed, Nyquist compliant, 11/11 v1.4 requirements satisfied.

</details>

### v1.5 Obsidian Vault Backend (Phases 16-20)

**Milestone goal:** Make the Obsidian vault a real premium storage backend — vault-primary writes, bidirectional sync, section-aware references and offline signed entitlement — so premium users can keep memory in their own vault while Notion remains the free-tier default.

- [x] **Phase 16: Vault Note Schema & Write Operations** — full frontmatter + index v2, idempotent remember, history-preserving supersede, certification, redaction. (completed 2026-11-13)
- [ ] **Phase 17: Vault-Primary Provider Routing** — Memory writes, certification and supersession route to the vault when selected; free tier unchanged; vault config and health.
- [ ] **Phase 18: Bidirectional Sync & Migration** — Notion→vault bootstrap; vault→Notion ingest for `agents/memory.md` and `journal/*.md` with state/dedupe.
- [ ] **Phase 19: Section-Aware References** — `note.md#section` catalog locators with retrieval targeting and safe fallback.
- [ ] **Phase 20: Offline Signed Entitlement** — Ed25519 license verification with expiry/features, `cryptography` dependency, docs and packaging.

## Phase Details

### Phase 16: Vault Note Schema & Write Operations

**Goal:** Make `ObsidianVaultAdapter` a complete memory store rather than a read-side scaffold.
**Depends on:** v1.4 (Phase 15)
**Requirements:** OBS-01, OBS-02
**Success Criteria**:
  1. Notes and the SQLite index carry title, subject key, status, truth, source agent/session, created/updated timestamps, domain, kind, tags and supersession link; v1 notes read with defaults and migrate lazily.
  2. Identical active entries reuse the existing note; changed values create a new note; non-identical active peers are marked Superseded without deletion.
  3. Certification sets `truth: certified` only through an explicit adapter call; ordinary writes never demote certified notes.
  4. Every written field and body is secret-redacted; tests cover migration, idempotency, history and redaction.

**Plans**: 1/1 — completed 2026-11-13
**Verification**: Passed 16-01: OBS-01/OBS-02 closed; 46 adapter/catalog tests and the 588-test full gate pass; ruff and mypy clean. See [16-VERIFICATION.md](phases/16-vault-note-schema-write-operations/16-VERIFICATION.md).

### Phase 17: Vault-Primary Provider Routing

**Goal:** Route Memory-domain writes through the selected vault adapter when premium is active.
**Depends on:** Phase 16
**Requirements:** OBS-03, SYNC-03
**Success Criteria**:
  1. `_store_entry`, the Memory write path and `_tool_certify` route to the vault when `storage_adapter="obsidian"` is selected and entitled.
  2. Free-tier Notion behavior and non-Memory domains are unchanged.
  3. Graph edges are written after accepted vault transitions; certification protection and confirmation gating still hold.
  4. Vault path configuration, sync status and health expose note count, index path, last sync and entitlement state.
  5. Parity tests cover remember, certify and supersede on both backends.

### Phase 18: Bidirectional Sync & Migration

**Goal:** Move existing memory into the vault and ingest vault notes back into Notion safely.
**Depends on:** Phase 17
**Requirements:** SYNC-01, SYNC-02
**Success Criteria**:
  1. Bootstrap exports active Notion Memory rows to stable vault notes with truth, provenance, subject key and creation time; existing notes are skipped and counts reported.
  2. The ingest command processes `agents/memory.md` and `journal/*.md` through `_store_entry` with content-hash dedupe, a state file, redaction and idempotent re-runs.
  3. Sync runs on demand or from an external timer; no daemon is started.
  4. Tests cover new, updated and unchanged sources plus secret redaction.

### Phase 19: Section-Aware References

**Goal:** Let catalog definitions point at a specific section of a vault note.
**Depends on:** Phase 18
**Requirements:** REF-01
**Success Criteria**:
  1. `note.md#section` locators resolve only inside the vault; traversal and non-markdown targets are rejected.
  2. Retrieval uses the referenced section text; matching is case-insensitive and missing sections fall back to the whole note with a warning.
  3. Catalog output exposes the section locator and tests cover resolution, fallback and rejection.

### Phase 20: Offline Signed Entitlement

**Goal:** Replace the presence-only license stub with real offline verification.
**Depends on:** Phase 19
**Requirements:** ENT-01
**Success Criteria**:
  1. Ed25519 verification of a canonical JSON payload plus signature, with subject, issued/expiry dates and an `obsidian` feature.
  2. Invalid, expired or missing licenses raise a specific `EntitlementError` and fall back to Notion; a valid license enables vault selection.
  3. `cryptography` is added as a bounded runtime dependency and packaging/docs are updated.
  4. Tests generate a throwaway keypair and cover valid, tampered, expired and wrong-feature licenses.
  5. License format and vault setup are documented.
