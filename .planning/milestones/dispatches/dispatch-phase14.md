You are implementing v1.4 Phase 14 (PROV-01..03) in /home/protik/projects/hermes-brain. Read AGENTS.md, .planning/REQUIREMENTS.md (Provenance & Graph section), .planning/research/2026-11-06-auto-ontology-semantic-layer.md, notion_brain/schema.py, notion_brain/catalog.py, notion_brain/provider.py, notion_brain/adapters.py.

Requirements:
- PROV-01: Every recalled fact returns provenance. Add a `provenance` block to each search result and prefetch line: `{"source_agent": ..., "session_id": ..., "created_at": ..., "truth": "certified"|"inferred", "status": "active"|"superseded"}`. Prefetch output format includes a compact tag (e.g. `[fact:certified:agent]` or suffix `[provenance: source=agent status=active]`).
- PROV-02: Explicit supersession relation edge: when Fact B supersedes Fact A, write a `Relation(subject=Fact_B_id, predicate="supersedes", object=Fact_A_id, relation_type="edge")` into the catalog sidecar `$HERMES_HOME/brain_catalog.json` (CAT-01/02), so the chain is traversable forwards and backwards (Fact B supersedes Fact A; Fact A superseded_by Fact B). In the Memory DB, record the predecessor page ID in a rich-text property `Superseded Page ID`. Catalog relation writes use existing atomic save and redaction rules; no graph database.
- PROV-03: Relational recall: expose a `graph_traverse(start_id, predicate=None, max_depth=3)` API on `notion_brain/catalog.py` and register an action `related` on the `notion_brain_search` tool: given an entity/memory id or name, returns all reachable memories linked via explicit relation edges (e.g., project -> decisions -> tasks), with loop detection (visited set) and depth capping.

Hard rules:
- Zero new dependencies; stdlib only.
- Redaction on all strings in the provenance payload and traversal output.
- Schema evolution must be idempotent: bootstrap._PROPS memory gains Superseded Page ID as rich_text without forcing DB reset.
- Do not implement the answerability gate (Phase 15). Do not edit planning docs. Do not commit.

Tests (tests/test_provenance.py):
- search returns provenance block on each entry
- prefetch surfaces provenance tag
- supersession creates explicit catalog edge
- graph_traverse handles chain A -> B -> C
- graph_traverse terminates on cycles (A -> B -> A)
- graph_traverse respects max_depth
- 'related' action on notion_brain_search returns connected facts

Verify with project venv (never uv):
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check notion_brain tests
.venv/bin/python -m mypy notion_brain

Return files created/changed, test summary, lint/type output, blockers. Leave uncommitted for review.