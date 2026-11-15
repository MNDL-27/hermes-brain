You are implementing v1.2 Phase 8 residual work in repository /home/protik/projects/hermes-brain.

Context: Phase 8's hermetic test infrastructure is ALREADY COMMITTED (tests/conftest.py socket-deny fixture, pyproject.toml network marker). Do not recreate or refactor it. Current suite baseline: 387 passed, 1 failed, 1 deselected. The one failure blocks the Phase 8 green-suite gate.

Task A — fix the pre-existing regression test failure:
- tests/test_bootstrap_schema.py::test_database_schema_mismatch_detects_zombie_status_options fails.
- Root cause: notion_brain/bootstrap.py `_database_schema_matches` (around line 519) applies issubset() option comparison to ALL property types. Commit e4362f7 intended: 'status' fields keep STRICT option-name equality (zombie status options — which Notion PATCH cannot delete — must be detected and drive reset_databases); 'select'/'multi_select' fields accept a superset of user-added options.
- Implement exactly that type-aware comparison. Do not change any other bootstrap behavior. Keep the function's signature and fail-fast returns.
- Do NOT modify the test to fit a wrong implementation; the test encodes the intended contract.

Task B — suite-count audit in planning docs:
- Run the full offline suite and record the true count.
- Update .planning/PROJECT.md (the "361 tests" / baseline mentions in Context section) and .planning/STATE.md (Performance Metrics cumulative counts) with the audited figure and today's date. Do not touch other planning sections.

Scope limits:
- Files: notion_brain/bootstrap.py, tests/ if a regression test addition is warranted, .planning/PROJECT.md, .planning/STATE.md.
- Do not commit. Do not run git checkout/reset/clean.

Verification:
1. export PATH=/home/protik/.hermes/tools/uv-0.13.5-linux-x64:$PATH
2. cd /home/protik/projects/hermes-brain
3. uv run --no-sync pytest -q   (must be fully green except the 1 network-deselected test)
4. uv run --no-sync ruff check notion_brain tests
5. uv run --no-sync mypy notion_brain

Return files changed, final pytest summary line, ruff/mypy results, blockers.