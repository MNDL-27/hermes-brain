---
phase: 16-vault-note-schema-write-operations
plan: "01"
subsystem: obsidian-vault
tags: [obsidian, frontmatter, sqlite, idempotency, supersession, certification]
requires:
  - phase: 11-storage-adapters
    provides: ObsidianVaultAdapter scaffold with search/prefetch/get_note/resolve_storage_ref
provides:
  - Vault frontmatter v2 with truth, provenance, timestamps, domain/kind/tags and supersession link
  - SQLite index v2 with additive migration from v1
  - Idempotent remember, history-preserving supersede and certification
affects: [17-vault-primary-provider-routing, 18-bidirectional-sync-migration]
tech-stack:
  added: []
  patterns: [JSON-encoded frontmatter without a YAML dependency, additive index migration, exact-match write idempotency]
key-files:
  created: []
  modified:
    - notion_brain/adapters.py
    - tests/test_adapters.py
key-decisions:
  - Frontmatter values are JSON-encoded line-by-line so titles, tags and timestamps with punctuation round-trip without a YAML dependency.
  - The index migration is additive via `PRAGMA table_info`; a newer schema version is left untouched and v1 rows read with defaults.
  - Remember reuses an active note only on exact title + subject key + body equality; changed values still create a new version.
  - Certified truth is protected on update unless the caller explicitly passes `truth="certified"` through `certify`.
  - Supersede links the replacement to the first predecessor and flips every active peer without deleting history.
requirements-completed: [OBS-01, OBS-02]
coverage:
  - id: D1
    description: Notes and the index carry the full memory schema, with v1 stores migrating lazily.
    requirement: OBS-01
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_obsidian_frontmatter_v2_round_trip
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_obsidian_v1_note_reads_with_defaults_and_upgrades_on_write
        status: pass
    human_judgment: false
  - id: D2
    description: Writes are idempotent, history-preserving and certification-safe.
    requirement: OBS-02
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_obsidian_remember_is_idempotent_for_identical_active_entry
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_obsidian_supersede_keeps_history_and_links_predecessor
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_obsidian_certify_sets_truth_without_demotion
        status: pass
    human_judgment: false
  - id: D3
    description: Provenance fields and bodies are redacted before disk writes.
    requirement: OBS-02
    verification:
      - kind: unit
        ref: tests/test_adapters.py::test_obsidian_v2_redacts_provenance_fields
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-13
---

# Phase 16 plan 01 summary

**Vault notes and the SQLite index now carry the full memory schema, with idempotent writes, history-preserving supersession and protected certification**

## Performance

- **Tasks:** 3
- **Files modified:** 2
- **Commits:** `592ab84`

## Accomplishments

- Frontmatter v2 stores `id`, title, subject key, status, truth, source agent/session, created/updated timestamps, supersession link, domain, kind and tags as JSON-encoded lines.
- The index gains the same columns through additive ALTERs; v1 indexes and notes read with defaults and upgrade on the next write.
- `remember` reuses an exact active match, updates an existing id in place, preserves `created_at`, and never demotes certified truth.
- `supersede` flips every active peer to `Superseded`, records the first predecessor in `superseded_page_id`, and writes the replacement without deleting history.
- `certify` flips truth on the note and index; `health` reports total/active/certified counts and the schema version.
- All frontmatter values, bodies and index values pass through `redact_secrets`.

## Evidence

- Adapter/catalog suite: **46 passed in 0.40s** (six new regressions).
- Full repository gate: **588 passed, 1 deselected in 5.98s** (v1.5 baseline 582 plus six tests).
- Ruff, mypy and whitespace clean.

## Decisions Made

- No YAML dependency: JSON-encoded scalar/list values inside `---` frontmatter.
- Exact-match idempotency keeps changed facts as new versions rather than silently overwriting.
- Certification protection lives in the adapter as well as the provider boundary.

## Deviations from Plan

None — the three planned tasks were implemented as specified.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Phase 17 can route Memory writes through this adapter; the flat row shape and `certify` method are ready.

## Self-Check

All checks passed: six new regressions, existing adapter/catalog tests, the 588-test full gate, and static checks are green.
