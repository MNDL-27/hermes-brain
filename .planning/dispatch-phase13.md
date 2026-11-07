You are implementing v1.4 Phase 13 (CERT-01..03) in /home/protik/projects/hermes-brain. Read AGENTS.md, .planning/REQUIREMENTS.md (Certification section), .planning/research/2026-11-06-auto-ontology-semantic-layer.md, notion_brain/schema.py, notion_brain/provider.py, notion_brain/store.py, notion_brain/bootstrap.py, notion_brain/catalog.py (Phase 12), notion_brain/adapters.py (Phase 11).

Requirements:
- CERT-01: Memories carry a truth status. Add a Notion select property `Truth` on the Memory DB with options `inferred` and `certified` (default `inferred` for agent-written rows). Retrieval prefers certified facts over inferred facts at equal recency: implement the ordering in the search/prefetch path so certified rows rank first when recency ties.
- CERT-02: ONLY explicit user confirmation promotes inferred -> certified. Add dedicated `notion_brain_certify` action registered in `notion_brain/schemas.py`, accepting memory id/title plus `user_confirmed: true`. Provider rejects certification unless this exact flag is present and true; normal agent-facing remember cannot set Truth. UI/orchestrator is responsible for supplying the flag after a real user confirmation; the provider must not infer confirmation from free-text or agent intent.
- CERT-03: A certified correction supersedes conflicting inferred rows immediately: when a row is certified and an existing ACTIVE row shares the same Subject Key, flip the older row to Status: Superseded (reuse Phase 10 supersession machinery). Historical rows are preserved.

Hard rules:
- Zero new dependencies; stdlib only.
- Idempotent schema evolution: bootstrap._PROPS memory gains the Truth property; existing databases must not trigger a destructive reset for the new property (use the same select-superset semantics as Phase 8). Keep zombie status strict.
- Secret redaction on all outbound strings.
- Do not implement provenance edges or the answerability gate (Phases 14-15). Do not edit planning docs. Do not commit.

Tests (tests/test_certification.py):
- agent remember defaults Truth=inferred
- certify action flips to certified
- normal remember path cannot set certified
- retrieval orders certified before inferred at equal recency
- certified row supersedes conflicting inferred row with same subject key
- bootstrap schema match stays true with the new property

Verify with project venv (never uv):
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check notion_brain tests
.venv/bin/python -m mypy notion_brain

Return files created/changed, test summary, lint/type output, blockers. Leave uncommitted for review.