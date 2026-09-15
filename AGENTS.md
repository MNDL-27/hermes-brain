# AGENTS.md — Autonomous Agent Directives

Welcome to `hermes-brain`. Read this file before planning or executing any task.

---

## 1. Environment & Verification Commands

- **Python runtime:** Python 3.11+ via `uv` or active virtualenv.
- **Run test suite:** `uv run pytest` (all 293 tests must pass).
- **Run single test:** `uv run pytest tests/test_extract.py`
- **Lint:** `ruff check .`
- **Typecheck:** `mypy .`

Always run `uv run pytest` and ensure zero failures before proposing a plan or creating a Pull Request.

---

## 2. Security & Redaction Boundaries (For "Sentinel" 🛡️)

1. **Review Historical Fixes First:**
   - Read `.jules/sentinel.md` before scanning.
   - The following vulnerability classes are ALREADY resolved in `main`:
     - Status property secret redaction (`store.py:status_property`).
     - Exception context chaining (`from None` in `provider.py`).
     - Secret redaction regexes for Anthropic (`sk-ant-`), OpenAI (`sk-proj-`), Google (`AIza`), Bearer tokens, Stripe, GitHub, Slack tokens (`schema.py`).
     - Quoted secret redaction (`api_key="..."`).
   - **DO NOT** re-propose fixes for any of the above. They are verified and passing in `main`.

2. **Deduplication Rule:**
   - Never create a PR for an issue already addressed in `.jules/sentinel.md` or git history.
   - Never create duplicate PRs if a fix is already in `main` or in an open PR.

3. **No Security Theater:**
   - If no actionable, high-impact security vulnerability is found in the current codebase, **DO NOT create a PR**. Exit cleanly.
   - Do not reformat code, rewrite working exceptions, or introduce unnecessary wrappers under the guise of security.

---

## 3. High-Value Maintenance Tasks (If Scheduled)

When running scheduled maintenance or proactive tasks, prioritize:
1. **Real Test Coverage Gaps:** Add missing tests for uncovered branches in `tests/`.
2. **Dependency Hygiene:** Flag or bump dependencies with published CVEs.
3. **Schema Durability:** Ensure new Notion API property helpers strictly enforce input validation and sanitization.
