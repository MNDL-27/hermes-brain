You are implementing v1.3 Phase 10 (SUP-01..03) in /home/protik/projects/hermes-brain. Read AGENTS.md, .planning/REQUIREMENTS.md (Supersession section), notion_brain/schema.py, notion_brain/provider.py, notion_brain/store.py, notion_brain/bootstrap.py, plus tests/test_provider.py and tests/test_store.py for conventions.

Requirements:
- SUP-01: Memory rows carry a Subject Key logical slot (e.g. `device.daily_phone`). Detection infers it from content (deterministic heuristics, no LLM in the write path) with an explicit override argument on remember. Subject keys are stored as a Notion rich-text property `Subject Key` on the Memory DB, and mirrored in any local cache.
- SUP-02: Writing a fact whose Subject Key matches an existing ACTIVE row flips the older row to Status: Superseded (non-destructive; history preserved). Superseded is a NEW status value - bootstrap must include it in the Memory DB status options and health/reset checks. Do not delete rows. Sync time flips must be fail-soft (log via module logger with S.redact_secrets on exceptions) and never block the write.
- SUP-03: Superseded rows remain queryable: a `timeline` listing (per subject key, newest first, with status + timestamps) exposed as an action on the existing `notion_brain_search` tool (e.g. {"action": "timeline", "subject_key": "..."}).

Hard rules:
- Zero new dependencies; stdlib only.
- All outbound strings redacted through S.redact_secrets at store boundaries.
- Schema change must be idempotent (bootstrap._PROPS memory gains Subject Key + Superseded status option without breaking _database_schema_matches for existing DBs: keep select/user-option superset semantics; status strict equality now includes the new option - update _STATUS_OPTIONS accordingly).
- Do not touch PrefetchTokenBudget or adapter work (Phases 9/11). Do not edit planning docs. Do not commit.

Tests (tests/test_supersession.py):
- subject key inference + override
- same subject write marks prior active row Superseded (mock store.update_page/store.create_page)
- different subject does not flip
- timeline returns chronological history for a subject with statuses
- redaction holds on failure paths
- bootstrap schema match still true after adding Subject Key property

Verify with project venv (never uv):
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check notion_brain tests
.venv/bin/python -m mypy notion_brain

Return files changed, test summary, lint/type output, blockers. Leave uncommitted for review.