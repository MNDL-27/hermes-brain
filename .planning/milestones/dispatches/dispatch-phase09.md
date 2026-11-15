You are implementing v1.3 Phase 9 in /home/protik/projects/hermes-brain. Work alone; no concurrent agents. Read AGENTS.md, .planning/PROJECT.md, .planning/ROADMAP.md, .planning/REQUIREMENTS.md, .planning/phases/09-retrieval-correctness-local-cache/09-01-WORK-ORDER.md, notion_brain/provider.py, notion_brain/update_cache.py, tests/test_prefetch_hydration.py.

Scope: complete RET-01 verification (existing prefetch hydration), implement RET-02 local SQLite read-through cache at ~/.hermes/brain_cache.db, implement RET-03 deterministic two-lane 800-token prompt injection (Lane 1 pinned/critical 400, Lane 2 dynamic 400), with offline tests. Use stdlib sqlite3; no new dependency. Preserve Notion background writes and secret redaction. Do not touch Phase 10/11 or v1.4. Do not edit planning docs. Do not commit.

Acceptance:
- prefetch reads hydrated body and existing tests remain green.
- cache mirrors active memory rows and prefetch can read offline without Notion calls; schema migration/atomic behavior safe.
- injection hard cap 800 tokens, deterministic truncation, lane budgets explicit.
- add focused tests for cache hit/offline miss/write-through and lane budgets/overflow.

Verify using project venv (not uv):
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check notion_brain tests
.venv/bin/python -m mypy notion_brain

Return exact files, test summary, lint/type output, blockers. Leave uncommitted.