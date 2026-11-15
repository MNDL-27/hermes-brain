---
phase: 16-vault-note-schema-write-operations
verified: 2026-11-13
status: passed
source_snapshot: 592ab84
score: "2/2 requirements verified; OBS-01 and OBS-02 closed"
fingerprint: "Phase 16 closure: vault notes and the SQLite index carry the full memory schema with additive v1 migration; remember is idempotent, supersede preserves history and links the predecessor, certification is protected from demotion, and all fields/bodies are redacted. 46 adapter/catalog tests pass; full suite 588 passed, 1 deselected; ruff and mypy clean."
gaps: []
covered_files:
  - notion_brain/adapters.py
  - tests/test_adapters.py
  - .planning/phases/16-vault-note-schema-write-operations/16-01-PLAN.md
  - .planning/phases/16-vault-note-schema-write-operations/16-01-SUMMARY.md
covered_digest: "v4:sha256:bf7781efa5346c95a40abddbfd7a59e6b544ca5b17ee41602a9ae2272521ffc3"
closed:
  - truth: Vault notes and the index carry the full memory schema with lazy, non-destructive migration.
    requirements: [OBS-01]
    resolution: Frontmatter v2 stores id/title/subject/status/truth/source/timestamps/supersession/domain/kind/tags as JSON lines; the index gains the same columns through additive ALTERs; v1 rows read with defaults and upgrade on write.
    evidence: tests/test_adapters.py::test_obsidian_frontmatter_v2_round_trip, test_obsidian_v1_note_reads_with_defaults_and_upgrades_on_write
  - truth: Write operations are idempotent, history-preserving, certification-safe and redacted.
    requirements: [OBS-02]
    resolution: remember reuses exact active matches or updates by id; supersede flips all active peers and links the first predecessor; certify sets truth; ordinary writes cannot demote certified notes; every value passes redaction.
    evidence: tests/test_adapters.py::test_obsidian_remember_is_idempotent_for_identical_active_entry, test_obsidian_supersede_keeps_history_and_links_predecessor, test_obsidian_certify_sets_truth_without_demotion, test_obsidian_v2_redacts_provenance_fields
---

# Phase 16 verification record

Phase 16 is verified. OBS-01 and OBS-02 are closed; provider routing, sync, sections and licensing remain in Phases 17–20.

## Verification scope

- Adapter/catalog suite: **46 passed in 0.40s** (six new regressions).
- Full repository gate: **588 passed, 1 deselected in 5.98s**.
- Ruff, mypy and CRLF-aware whitespace checks clean.
- No live Notion call or external service required.

## Closure evidence

`notion_brain/adapters.py`:

- `_render_obsidian_note` / `_parse_obsidian_note` provide dependency-free JSON frontmatter.
- `_obsidian_note_meta` normalizes defaults, protects certified truth and redacts fields.
- `_connect` creates/migrates index v2 additively and records the schema version.
- `remember` handles exact-match reuse and id-preserving updates.
- `supersede` flips active peers and stores `superseded_page_id`.
- `certify` flips truth; `health` reports counts and schema version.

`tests/test_adapters.py`: six new regressions cover the full contract.

## Scope note

The provider still routes Memory writes through Notion. Phase 17 wires vault-primary routing and the confirmation gate. Sync, section refs and the signed license are untouched.

## Remaining scope

Phases 17–20. Phase 16 does not mark the milestone released or merged.
