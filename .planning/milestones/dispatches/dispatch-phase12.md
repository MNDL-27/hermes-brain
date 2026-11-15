You are implementing v1.4 Phase 12 (CAT-01..03) in /home/protik/projects/hermes-brain. Read AGENTS.md, .planning/REQUIREMENTS.md (Semantic Catalog section), .planning/research/2026-11-06-auto-ontology-semantic-layer.md, notion_brain/schema.py, notion_brain/adapters.py, notion_brain/provider.py.

Requirements:
- CAT-01: New module `notion_brain/catalog.py` with provider-neutral types:
  - `Term` (name, description, synonyms tuple, entity_refs tuple)
  - `Entity` (name, entity_type, description, storage_refs tuple)
  - `Relation` (subject, predicate, object, relation_type)
  - `StorageRef` (adapter_name, locator, extra) - provider-neutral pointer to where the entity lives.
  Use dataclasses with frozen=True. No Notion/Obsidian specifics in these types.
- CAT-02: Deterministic catalog query API in `notion_brain/catalog.py`: `resolve_term(name) -> Term | None`, `list_entities(entity_type=None) -> list[Entity]`, `get_relations(subject=None) -> list[Relation]`, `add_term`, `add_entity`, `add_relation`. Resolution must be exact-match, then case-insensitive, then synonym match. NO LLM, NO network. Catalog stores in memory and can load/save JSON to `$HERMES_HOME/brain_catalog.json` (atomic write, 0o600).
- CAT-03: Storage mapping: `Term`/`Entity` carry `StorageRef` values that adapters can resolve. Add a method on the adapter protocol implementations: `resolve_storage_ref(ref) -> str | None` returning a concrete locator (Notion page id, Obsidian note path) for a ref, or None when unmapped. Implement for both NotionAdapter and ObsidianVaultAdapter in notion_brain/adapters.py.

Hard rules:
- Zero new dependencies; stdlib only.
- Secret redaction (S.redact_secrets) on any string persisted into the catalog JSON.
- Do not change existing Notion behavior or public provider API; existing tests stay green untouched.
- CAT-03 includes the required narrow adapter changes: add `resolve_storage_ref(ref) -> str | None` to both adapter implementations. No other adapter behavior changes.
- Do not implement certification, provenance edges, or the answerability gate (Phases 13-15). Do not commit.

Tests (tests/test_catalog.py):
- Term/Entity/Relation dataclass construction + immutability
- resolve_term exact, case-insensitive, synonym
- list_entities filtered by type
- get_relations filtered by subject
- JSON round-trip through save/load, atomic + 0o600
- secret redaction on persisted strings
- resolve_storage_ref works for Notion and Obsidian adapters

Verify with project venv (never uv):
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check notion_brain tests
.venv/bin/python -m mypy notion_brain

Return files created/changed, test summary, lint/type output, blockers. Leave uncommitted for review.