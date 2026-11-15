---
phase: 12-semantic-catalog
plan: "01"
subsystem: semantic-catalog
status: complete
completed: 2026-11-12
requirements-completed: [CAT-01, CAT-02, CAT-03]
requires:
  - phase: 11-storage-adapters
    provides: Entitlement-gated adapters and provider read-path routing
affects: [15-answerability]
tech-stack:
  added: []
  patterns: [provider-neutral catalog models, atomic redacted JSON persistence, deterministic definition matching, adapter locator resolution]
key-files:
  created: []
  modified: [notion_brain/provider.py, notion_brain/adapters.py, tests/test_catalog_search.py, tests/test_adapters.py]
key-decisions:
  - Phase 12 was primarily a verification gap: the audit already marked CAT-01..03 WIRED. Gap review found one real residual — Obsidian storage refs were resolved for output but never selected rows — which this plan now closes.
  - The catalog remains stdlib-only and provider-neutral: `catalog.py` imports `schema` for redaction and nothing from `store`, `bootstrap` or `adapters`.
  - Storage references stay data (`StorageRef.adapter_name` + `locator`); each adapter decides whether a locator is valid. Notion accepts page/database ids; Obsidian accepts `.md` paths inside the vault and rejects traversal.
  - Reference-driven retrieval selects rows by resolved page/database ids on the Notion side and by resolved note path on the premium Obsidian side, before textual matching, while still enforcing an explicit `database` filter.
  - `ObsidianVaultAdapter.get_note(path)` performs the targeted lookup for a referenced note; text search alone could not surface a note whose body does not contain the query.
coverage:
  - id: S1
    description: Provider-neutral catalog types represent terms, synonyms, entities, relations and storage references.
    requirement: CAT-01
    verification:
      - kind: unit
        ref: tests/test_catalog.py
        status: pass
      - kind: probe
        ref: "standalone probe: model construction + save/load round-trip"
        status: pass
    human_judgment: false
  - id: S2
    description: Catalog queries are deterministic and require no LLM or network.
    requirement: CAT-02
    verification:
      - kind: unit
        ref: tests/test_catalog.py::test_resolve_term_synonym
        status: pass
      - kind: unit
        ref: tests/test_catalog.py::test_list_entities_filtered
        status: pass
      - kind: probe
        ref: "standalone probe: resolve_term/list_entities/get_relations + source import scan"
        status: pass
    human_judgment: false
  - id: S3
    description: Notion and Obsidian adapters map catalog references to concrete storage locations.
    requirement: CAT-03
    verification:
      - kind: unit
        ref: tests/test_catalog.py::test_notion_resolve_valid_ref
        status: pass
      - kind: unit
        ref: tests/test_catalog.py::test_obsidian_resolve_returns_absolute_note_path
        status: pass
      - kind: unit
        ref: tests/test_catalog_search.py::test_search_resolves_multiword_definition_to_page_without_text_match
        status: pass
      - kind: unit
        ref: tests/test_catalog_search.py::test_search_resolves_obsidian_note_ref_without_text_match
        status: pass
      - kind: unit
        ref: tests/test_adapters.py::test_obsidian_get_note_returns_indexed_note_and_rejects_outside_paths
        status: pass
      - kind: probe
        ref: "standalone probe: adapter resolution + end-to-end ref-driven row selection"
        status: pass
    human_judgment: false
---

# Phase 12 plan 01 summary

Phase 12 was primarily a closure pass: `da6b1d4` delivered the catalog and its provider consumption, and the 2026-11-09 milestone audit found all three CAT requirements wired with only the original GSD artifacts missing. The gap review added one repair: Obsidian storage refs resolved to output paths but never selected vault rows.

## What was verified and closed

- **CAT-01** — `notion_brain/catalog.py` defines `StorageRef`, `Term`, `Entity` and `Relation`, plus atomic redacted persistence. The module imports only `schema`; nothing from a storage backend. Adapters consume `StorageRef` rather than the catalog depending on them.
- **CAT-02** — `resolve_term` resolves exact names, case-insensitively and by synonym; `list_entities` filters by case-insensitive entity type; `get_relations` filters by subject. `match_definitions` feeds provider search deterministically. No LLM, HTTP or network client is imported.
- **CAT-03** — `NotionAdapter.resolve_storage_ref` validates and strips `page/`/`db/` locators; `ObsidianVaultAdapter.resolve_storage_ref` returns absolute in-vault `.md` paths and rejects traversal. Provider search selects rows by resolved page/database id even when the title does not match the query. After the closure fix, a resolved Obsidian note path also selects its note through `ObsidianVaultAdapter.get_note`, so a premium vault reference is recalled without a text match.

## Execution

- Catalog suite: **58 passed**.
- Adapter suite: **14 passed** (includes the new `get_note` safety test).
- Independent probe: all four checks passed (models/round-trip, deterministic queries/import scan, adapter resolution, end-to-end ref selection).
- Full gate: **570 passed, 1 deselected in 5.44s**; ruff clean; mypy clean.

## Remaining scope

Phase 13 (certification failure isolation) carries the next known code gap, followed by Phase 14 (provenance continuity) and Phase 15 (answerability closure evidence).
