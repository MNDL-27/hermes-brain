You are implementing v1.4 Phase 15 (ANS-01..02) in /home/protik/projects/hermes-brain. Read AGENTS.md, .planning/REQUIREMENTS.md (Answerability Gate section), .planning/research/2026-11-06-auto-ontology-semantic-layer.md, notion_brain/catalog.py, notion_brain/provider.py, notion_brain/schemas.py.

Requirements:
- ANS-01: Answerability check before fuzzy retrieval. Implement `check_answerable(query, catalog=None)` in `notion_brain/catalog.py`: extracts candidate terms/entities from the query, compares them against the semantic catalog, and returns `{"answerable": bool, "coverage": float, "matched_terms": list[str], "missing_terms": list[str]}`. Expose this as an MCP tool `notion_brain_check_answerable` in `notion_brain/schemas.py` and `notion_brain/provider.py` (mirrors NVIDIA Auto Ontology's check_answerable pre-flight). When coverage is 0.0, say: "No known semantic terms for [X] were found in the catalog; unable to verify answerability." Name missing terms. Do not claim that no certified memory exists unless catalog coverage and certification data prove it.
- ANS-02: Contradiction detection: in `notion_brain/provider.py` search and prefetch, if multiple ACTIVE memories share the exact same Subject Key but have different values (un-superseded collision), surface them as an explicit `contradiction` payload with both entries rather than silently picking one. Include both values, their timestamps, and their certification levels so the caller knows the memory is in dispute.
- Register tools in `notion_brain/schemas.py`: `notion_brain_check_answerable`, and mirror Auto Ontology's read-only inspection pattern: `notion_brain_search_terms` (queries the catalog glossary, not raw notes).

Hard rules:
- Zero new dependencies; stdlib only.
- Redaction on all strings in check_answerable and contradiction payloads.
- Existing tools (`notion_brain_search`, `notion_brain_remember`, etc.) preserve backward compatibility.
- Do not edit planning docs. Do not commit.

Tests (tests/test_answerability.py):
- check_answerable returns coverage=1.0 when all query terms match catalog
- check_answerable returns coverage=0.0 and missing_terms when no term matches
- check_answerable tool callable via provider.handle_tool_call
- notion_brain_search_terms returns matching glossary terms
- contradiction detection surfaces both conflicting active rows
- single active row does not flag contradiction
- redaction holds on all output paths

Verify with project venv (never uv):
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check notion_brain tests
.venv/bin/python -m mypy notion_brain

Return files created/changed, test summary, lint/type output, blockers. Leave uncommitted for review.