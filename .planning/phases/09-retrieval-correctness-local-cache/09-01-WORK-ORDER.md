# Phase 9 Work Order — RET-01: Prefetch Text Hydration Fix

## Task
Fix `notion_brain/provider.py` `prefetch()` so each injected line shows real content, not blank.

## Current bug (verified)
File: `notion_brain/provider.py`, method `prefetch()` (~line 160).

```python
content = entry.get("properties", {}).get("Content", "")
safe_content = S.redact_secrets(content[:200])
lines.append(f"- [{kind}] {safe_title}: {safe_content}")
```

The Memory database schema (see `notion_brain/schema.py` / bootstrap) has NO `Content` property — pages carry their text in child blocks and/or a title. `store.query_database()` returns rows under `entry["title"]` and properties `Confidence/Last Seen/Kind/Source Session/Domain/Tags/Status/title`. So every prefetch line renders `- [kind] Title: ` (empty).

## Required change
1. In `prefetch()`, when `properties.Content` is empty, hydrate the page body via `store._page_body_text(entry["id"])` (already exists in `store.py`, used by search hydration — reuse it; make it importable/public if private) and fall back to that text.
2. Cache hydrated text per page id inside the existing prefetch lock path so a prefetch run makes at most one body fetch per page.
3. Keep `S.redact_secrets()` on the hydrated text. Truncate to 200 chars as today.
4. Preserve existing behavior otherwise (sort by `Last Seen` descending, page_size 10, `self._prefetch_cache`  semantics, empty-DB `return ""`).

## Constraints (hard rules)
- Zero new dependencies.
- No changes to Notion database schema; no new properties written.
- Fail-soft: if body hydration throws for a page, leave text empty for that page and continue (match store.py's documented behavior). Log via the module logger at warning level with `S.redact_secrets()` on any exception text.
- Do not touch `sync_turn`, `_sync_disk_memories`, or tool handlers in this change.

## Tests (must add)
Add `tests/test_prefetch_hydration.py`:
- Prefetch renders non-empty content when the store hydrates a body (mock `store` layer: one entry with `properties` lacking `Content`, body text present).
- Prefetch stays blank-tolerant when body hydration returns empty.
- Prefetch output is redacted: include a fake `sk-...` key inside body text and assert it does not appear in output.
- Cache behavior: second prefetch call returns the cached string without calling the store again (assert call count).

Run: `uv run pytest tests/test_prefetch_hydration.py -q` then full offline suite `uv run pytest -q` (exclude known-hang files per repo convention: `--deselect tests/test_coverage_gaps.py --deselect tests/test_migration_privacy_blockers.py --deselect tests/test_provider.py` if they hang offline).

## Definition of done
- New tests pass, full offline suite passes (minus pre-existing hangs), `uv run ruff check notion_brain tests`, `uv run mypy notion_brain` clean or no new errors.
- Do NOT commit; leave changes uncommitted for review.
- Print a summary of files changed and test results.
