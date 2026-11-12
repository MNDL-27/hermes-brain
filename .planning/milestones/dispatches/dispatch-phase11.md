You are implementing v1.3 Phase 11 (ADAPT-01..04) in /home/protik/projects/hermes-brain. Read AGENTS.md, .planning/REQUIREMENTS.md (Storage Adapter & Freemium section), notion_brain/provider.py, notion_brain/store.py, notion_brain/bootstrap.py, notion_brain/schema.py.

Requirements:
- ADAPT-01: Introduce a `StorageAdapter` Protocol (typing.Protocol, stdlib only) in a new module `notion_brain/adapters.py` exposing: `search(query, limit)`, `remember(entry)`, `supersede(subject_key, entry)`, `prefetch(limit)`, `health()`. All return plain dicts/lists (no provider-specific objects).
- ADAPT-02: Move the Notion REST implementation behind `NotionAdapter` in `notion_brain/adapters.py`, delegating to the existing store/bootstrap functions. Behavior must be unchanged for existing users. `NotionBrainProvider` keeps working exactly as before (its existing public API is the contract).
- ADAPT-03: Premium entitlement check: `notion_brain/entitlement.py` with `is_premium_entitled(hermes_home) -> bool` reading an optional license token file (`$HERMES_HOME/hermes_brain.license`) and validating presence + non-empty. Keep it a STUB (no crypto, no network): an unentitled selection must raise a clear `EntitlementError` with an upgrade message naming the free tier fallback.
- ADAPT-04: `ObsidianVaultAdapter` premium adapter scaffold in `notion_brain/adapters.py`: constructor takes a vault path; implements the protocol by writing/reading markdown notes under `<vault>/hermes-brain/` (one note per memory, YAML frontmatter with title, subject_key, status, created_at) and uses sqlite3 (stdlib) as the local index at `<vault>/hermes-brain/index.db`. Implement `remember`, `search` (substring + case-insensitive over frontmatter/body), `prefetch`, `health`, and `supersede` (writes status: superseded on the older note, no deletion). It must be constructible only via an entitlement-checked factory function `get_adapter(name, *, hermes_home, obsidian_vault=None)` that raises EntitlementError for "obsidian" when unentitled and falls back to NotionAdapter when no vault path is given.

Hard rules:
- Zero new dependencies; stdlib only (sqlite3, pathlib, typing).
- Secret redaction (S.redact_secrets) on every outbound string in both adapters.
- Do not change existing Notion behavior or public provider API. Existing tests must stay green untouched.
- Do not touch Phase 10 subject_key work or Phase 9 budget work. Do not edit planning docs. Do not commit.

Tests (tests/test_adapters.py):
- NotionAdapter delegates to store functions correctly (mocked)
- ObsidianVaultAdapter round-trips remember -> search -> prefetch -> supersede on a tmp vault
- Obsidian index db file created and queryable
- get_adapter("obsidian") raises EntitlementError when unentitled
- get_adapter("obsidian") with entitlement + vault returns ObsidianVaultAdapter
- get_adapter default returns NotionAdapter; unknown name raises ValueError
- redaction holds for secrets written through adapters

Verify with project venv (never uv):
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check notion_brain tests
.venv/bin/python -m mypy notion_brain

Return files created/changed, test summary, lint/type output, blockers. Leave uncommitted for review.