# Obsidian Vault Backend — v1.5 design research

**Date:** 2026-11-13
**Milestone:** v1.5 — Obsidian Vault Backend
**Status:** decisions confirmed; no external research required

## Confirmed decisions

| Decision | Choice |
| --- | --- |
| Source of truth when `storage_adapter="obsidian"` | **Vault-primary.** New memories, certifications and supersessions write to the vault. Notion becomes an optional mirror/read-through. |
| Sync | **Both directions.** First-run Notion→vault bootstrap plus periodic vault→Notion ingest. |
| Entitlement | **Offline signed license.** JSON payload + Ed25519 signature, embedded public key, expiry/feature validation. |
| Vault scope | Adapter-managed `<vault>/hermes-brain/` plus configured ingestion of `agents/memory.md` and `journal/*.md`. |

## Existing code facts

- `ObsidianVaultAdapter` already writes one markdown note per memory with `title`, `subject_key`, `status`, `created_at` frontmatter and a SQLite index (`memories` table) at `<vault>/hermes-brain/index.db`.
- `get_adapter("obsidian", ...)` is entitlement-gated but the license check is only "file present and non-empty".
- The provider selects the adapter for reads (search merge, prefetch) but the Memory write path still calls `store.*`, so a premium selection never stores new memories in the vault. This is the ADAPT-02 ceiling inherited from v1.3.
- `scripts/mirror_vault_to_notion.py` already implements a narrow vault→Notion mirror (`agents/memory.md`, `journal/*.md`) with a state file and dedupe. It is not packaged or timed.
- Catalog references support `.md` paths only; `note.md#section` is rejected by `_SAFE_NOTE_RE`.

## Vault note schema v2

Frontmatter (JSON-encoded strings to survive colons/quotes):

```yaml
---
id: "<stable memory id>"
title: "..."
subject_key: "..."
status: active | Superseded
truth: inferred | certified
source_agent: unknown | hermes | ...
source_session: "..."
created_at: "<ISO-8601>"
updated_at: "<ISO-8601>"
superseded_page_id: "<older id>"   # optional
domain: memory
kind: note | decision | preference | lesson | reminder
tags: []
---
<body markdown>
```

Rules:

- One note per memory; filename remains `<id>.md` for stable index lookup.
- Missing v1 fields are defaulted on read; migration is lazy and non-destructive.
- Every written string passes `schema.redact_secrets`; secrets never reach the vault.
- Sections are markdown headings inside the body. A `#section` reference maps to the heading text (case-insensitive, punctuation-normalized).

## Index schema v2

`memories` gains `truth`, `source_agent`, `source_session`, `updated_at`, and `superseded_page_id`. Additive `ALTER TABLE` migration, same pattern as `brain_cache`. `search`/`prefetch` reconstruct the adapter row shape expected by `_adapter_entry`.

## Write semantics

- `remember(entry)`: reuse an identical active note (same title, subject key and content) or create a new note. Non-identical active peers are superseded by the provider's explicit `supersede` call, mirroring the Notion path.
- `supersede(subject_key, entry)`: mark every active note for the subject `Superseded`, record `superseded_page_id` on the replacement, then write the replacement. No deletion.
- `certify(memory_id)`: set `truth: certified`; the provider still requires the exact per-call confirmation gate. Certified predecessors are never demoted by ordinary writes.
- Provider routing: vault-primary applies to the **Memory** domain only. Non-Memory databases (tasks/projects/etc.) remain Notion in v1.5; this is documented as a scope fence.
- Graph edges stay in `brain_catalog.json` (provider-independent) and are written after accepted vault transitions.
- The local `brain_cache` is not populated from vault writes; the vault index is the offline read path when premium is selected.

## Bidirectional sync

**Notion→vault bootstrap**

- Runs once when the vault backend is first selected (or via an explicit command).
- Exports active Notion Memory rows to `<vault>/hermes-brain/<page_id>.md` using the page id as the note id.
- Idempotent: existing notes are not overwritten; skipped ids are reported.
- Preserves truth, provenance, subject key and created time from Notion.

**Vault→Notion ingest**

- Promotes `scripts/mirror_vault_to_notion.py` into a supported command module.
- Reads `agents/memory.md` sections and `journal/*.md` entries, extracts memory-shaped facts, dedupes against the existing state file and Notion titles/subject keys, and writes through `NotionBrainProvider._store_entry` so redaction, subject inference and dedupe stay identical.
- Records a content hash + last-seen timestamp per source; re-runs are no-ops unless content changes.
- Runs on demand or from an external timer; the package does not start a daemon.

## Offline signed license

- License file: `$HERMES_HOME/hermes_brain.license` containing JSON:
  `{"payload": {"v": 1, "subject": "...", "issued": "...", "expires": "...", "features": ["obsidian"]}, "signature": "<base64>"}`
- Signature is Ed25519 over the canonical JSON payload.
- The public verification key is embedded in the package; the private key never ships.
- Validation: signature, expiry (UTC), and `features` contains `obsidian`. Failures raise `EntitlementError` with a specific reason and fall back to Notion.
- Dependency: `cryptography` for Ed25519 verification. This is the first new runtime dependency and is explicitly accepted for this milestone.
- Tests generate a throwaway keypair and monkeypatch the embedded public key; no live license is required.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Vault-primary writes bypass certification/provenance rules | Route through provider helpers, reuse the exact confirmation gate, mirror truth/provenance into frontmatter, and test parity with Notion. |
| Sync duplicates or overwrites user edits | Stable ids, content hashes, skip-existing bootstrap, state file, no destructive updates. |
| Secrets leak into the user's vault | `redact_secrets` on every written field and body before disk writes; regression tests. |
| License bypass via a copied stub | Signed payload with expiry/feature checks; presence-only stub is removed for premium selection. |
| New dependency footprint | `cryptography` is widely deployed; pin a lower bound and document it in packaging docs. |
| Section anchors drift when headings change | Resolve sections at read time; fall back to the whole note with a logged warning. |

## Out of scope for v1.5

- Online license server or account system.
- Whole-vault editing outside `<vault>/hermes-brain/` and the configured ingest folders.
- Non-Memory domain migration to the vault.
- Background daemon; sync is command- or timer-driven.
