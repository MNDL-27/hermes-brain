---
last_mapped_commit: 7e1e184f80b4352228eef67fc0fa0a4432cdabbd
last_mapped_at: 2026-09-20
---
# Codebase Concerns

**Analysis Date:** 2026-09-20

## Tech Debt

**Core Database Schema Missing Content Property (`_PROPS`):**

- Issue: Standard database definitions in `_PROPS` omit a `"Content"` rich-text property across all 7 databases (`tasks`, `projects`, `content`, `research`, `career`, `entities`, `memory`). However, `_database_properties` only populates `Content` if `"Content" in schema_props`, and `_write_entry_raw` does not supply page body `children`. As a result, entry content payloads are silently dropped on initial writes to standard databases. Meanwhile, `bootstrap.write_memory_to_disk`, `helpers.parse_disk_memory_text`, `store.search_entries`, and `provider.py` all expect a `Content` property.
- Files: `notion_brain/bootstrap.py:70-152`, `notion_brain/provider.py:515-516`, `notion_brain/store.py:173-178`
- Impact: Permanent silent content loss on newly bootstrapped databases. Only titles, tags, and category metadata are saved in Notion; the substantive memory text is discarded unless a custom property exists.
- Fix approach: Add `"Content": {"rich_text": {}}` to `_PROPS` for all 7 standard databases in `notion_brain/bootstrap.py` and ensure `build_custom_database_props` includes it by default. Update `_repair_database_schema` to add `Content` to legacy workspaces.

**Orphaned Dead Code `_paragraph_blocks`:**

- Issue: Helper function `_paragraph_blocks` was implemented to split arbitrary content into Notion paragraph block chunks under the 2000-character limit, but is never imported or called by `provider.py`, `bootstrap.py`, or `store.py`.
- Files: `notion_brain/helpers.py:257-279`
- Impact: Dead code maintenance overhead. Content exceeding 2000 characters is truncated via `_rich_text` instead of appending child blocks.
- Fix approach: Integrate `_paragraph_blocks` into `_write_entry_raw` via `store.append_block_children` or `store.create_database_page(..., children=...)` when content exceeds property character limits.

**Database Schema Reset Lacks Page Migration:**

- Issue: Marked as `FIXED` under AUD-RELIABLE-03 in remediation documentation, but `reset_databases` in `bootstrap.py` archives old databases with `store.archive_database(old_db_id)` and creates empty replacements without transferring existing pages.
- Files: `notion_brain/bootstrap.py:399-452`
- Impact: Running `hermes-brain reset` (or `python -m notion_brain reset`) abandons user memories and task records inside archived Notion databases without migrating them to the new schema.
- Fix approach: Query all entries from `old_db_id` via `store.query_database` before archival and recreate or reparent them into the newly created database.

**Uncached Schema Lookups on Every Write:**

- Issue: `_database_properties` invokes `store.get_database(database_id)` over the network on every entry write to inspect property types.
- Files: `notion_brain/provider.py:485-498`
- Impact: Every single entry write causes 3 sequential Notion API round-trips: schema GET, title search POST, and create/update POST/PATCH. Batch importing 20 items makes 60+ HTTP calls and quickly exhausts rate limits.
- Fix approach: Cache database schema definitions in memory on `NotionBrainProvider` or write them to `notion_brain.json`, invalidating only on reset or schema repair.

**Implicit Dependency on Hermes Runtime via Lazy Imports:**

- Issue: Framework runtime packages (`agent.*`, `tools.*`, `plugins.*`) are imported lazily without declared package dependencies or distribution pins in package metadata.
- Files: `pyproject.toml:25-28`, `notion_brain/__init__.py:18-20`
- Impact: Tools and packaging cannot declare or verify compatibility with upstream Hermes versions at build time.
- Fix approach: Declare standard optional dependencies or abstract provider interfaces once upstream packages are published to PyPI.

## Known Bugs

**Default `search_entries` API Call Fails with "No database found for: all":**

- Symptoms: Calling `notion_brain.search_entries("query")` from Python code returns an empty list or fails with error message `No database found for: all`.
- Files: `notion_brain/__init__.py:97-104`, `notion_brain/provider.py:597-603`
- Trigger: `search_entries` has default argument `database: str = "all"`, which passes `{"database": "all"}` to `handle_tool_call`. In `_tool_search`, `args.get("database")` checks `self._db_ids.get("all")`, which is `None`.
- Workaround: Callers must explicitly pass `database=""` or `database=None` to trigger the multi-database search branch.

**`notion_brain.config_schema` Crashes on Import:**

- Symptoms: Importing `notion_brain.config_schema` throws `ModuleNotFoundError: No module named 'plugins'`.
- Files: `notion_brain/config_schema.py:3-9`
- Trigger: Any script, test, or introspection tool importing `notion_brain.config_schema` outside the Hermes desktop host environment.
- Workaround: Wrap import in `try...except ImportError` with fallback dummy classes.

**`remember()` Reports Success When Persistence Fails:**

- Symptoms: Invoking top-level helper `remember(title="...", content="...")` returns `{"status": "saved", ...}` even when saving fails with an error.
- Files: `notion_brain/__init__.py:76-95`, `notion_brain/provider.py:673-677`
- Trigger: Any exception caught by `_tool_remember` returns string `"Error: <msg>"`. `handle_tool_call` packages this as `{"result": "Error: ...", "error": False}`, so `remember()` does not raise `RuntimeError`.
- Workaround: Callers must manually inspect `result["message"]` for the `"Error:"` substring.

**`notion_brain_task` Drops Priority, Due Date, and Project Fields:**

- Symptoms: Passing `priority`, `due`, or `project` to `notion_brain_task` during task creation silently discards the fields.
- Files: `notion_brain/provider.py:683-703`, `notion_brain/schemas.py:109-120`
- Trigger: Invoking `notion_brain_task` tool with `action="create"` and valid `priority`, `due`, or `project` parameters.
- Workaround: None via tool call; fields must be manually updated in Notion UI.

**`notion_brain_content` Drops Platform Field:**

- Symptoms: Passing `platform` to `notion_brain_content` during creation drops the target platform even though `Platform` exists in `_PROPS["content"]`.
- Files: `notion_brain/provider.py:817-837`, `notion_brain/schemas.py:162-165`
- Trigger: Invoking `notion_brain_content` with `action="create"` and `platform="twitter"`.
- Workaround: Include platform in `tags` list or `body` text.

**Database-Filtered Search Fails on Case Mismatch and Ignores Content:**

- Symptoms: Querying Notion databases via `notion_brain_search` fails to find pages when query casing differs from title casing, and never searches page content.
- Files: `notion_brain/provider.py:591-623`
- Trigger: Notion API database query `title.contains` filter is case-sensitive and only matches the `title` property. Searching for body text returns 0 rows.
- Workaround: Use global search (`database=None`) which uses Notion's `/search` endpoint instead of `databases/{id}/query`.

**`_sync_disk_memories` Permanently Skips Failed Entries After Network Glitch:**

- Symptoms: If network timeout or 429 occurs while syncing disk memories, `cached["disk_sync_hash"]` is still updated to the current content hash. Subsequent runs see the matching hash and skip syncing.
- Files: `notion_brain/provider.py:270-280`
- Trigger: Network interruption during turn sync.
- Workaround: User must edit or touch `MEMORY.md` to alter the file hash.

## Security Considerations

**Hardcoded Secret Patterns Omit Common Provider Keys:**

- Risk: `_SECRET_PATTERNS` targets OpenAI, Anthropic, AWS, GitHub, and Slack, but misses HuggingFace (`hf_...`), Cohere, Google AI Studio (`AIza...` variation), Discord bot tokens, Stripe keys (`rk_live_...`), and generic JWTs with non-standard prefixes. Unmatched tokens can leak into Notion workspace properties or error logs.
- Files: `notion_brain/schema.py:94-108`
- Current mitigation: Regex list checks known prefixes and generic `api_key=...` patterns.
- Recommendations: Expand pattern list with high-entropy token detectors and standard prefixes from common AI providers.

**Prompt Injection Vulnerability in Memory Turn Extractor:**

- Risk: `extract_with_llm` concatenates user content and assistant content directly into the extraction prompt template (`User: {user_content}\nAssistant: {assistant_content}`). Adversarial conversational inputs can inject instructions that override memory categories or exfiltrate private instructions into the database.
- Files: `notion_brain/extract.py:128-150`
- Current mitigation: Basic secret redaction and 4000-character compaction before dispatching to LLM.
- Recommendations: Separate user input into structured chat message roles or validate extracted memory entities against strict schema boundaries before writing.

**Multi-Select Property Commas Cause API Rejection:**

- Risk: Notion API rejects multi-select tag names containing commas (`,`). While `dedupe_strings` strips whitespace and redacts secrets, it does not strip commas from tag or entity values. Passing a comma-separated string results in 400 Bad Request.
- Files: `notion_brain/schema.py:183-196`, `notion_brain/store.py:348-350`
- Current mitigation: None for comma characters.
- Recommendations: Sanitize tag and entity strings by replacing commas with dashes or splitting them into separate tag items in `dedupe_strings`.

## Performance Bottlenecks

**N+1 HTTP Requests During Search Body Hydration:**

- Problem: `store.search_entries` fetches body text for every result by querying `/blocks/{page_id}/children` sequentially. For 8 search results, this issues 8 to 24 sequential HTTP calls.
- Files: `notion_brain/store.py:156-178, 441-471`
- Cause: Synchronous iterative block retrieval on every search operation.
- Improvement path: Fetch body text concurrently using `concurrent.futures.ThreadPoolExecutor` or hydrate bodies lazily on demand.

**Missing Connection Pooling Across HTTP Requests:**

- Problem: `_request` calls `requests.request(...)` directly without maintaining a shared `requests.Session`. Every API call creates a new TCP/TLS connection.
- Files: `notion_brain/store.py:69-76`
- Cause: Stateless function calls instead of session lifecycle management.
- Improvement path: Initialize a persistent `requests.Session` in `store.py` with standard connection pooling and retry adapters.

**Synchronous Local LLM Fallback Blocks Worker Thread:**

- Problem: `classify_turn` unconditionally calls `extract_with_llm`, which defaults to `http://localhost:11434/v1`. If Ollama is not running, requests wait up to 5 seconds before falling back to heuristics.
- Files: `notion_brain/extract.py:83-86, 112-153`
- Cause: Hardcoded local endpoint without reachability caching or circuit breaker.
- Improvement path: Implement a circuit breaker that disables LLM extraction for 5 minutes after a connection failure.

**Unbounded Pagination Loop in `query_database`:**

- Problem: `store.query_database` continues fetching next cursors until `has_more` is False. If a database has 1000 items, `query_database(page_size=20)` executes 50 sequential HTTP requests rather than stopping after 20 results.
- Files: `notion_brain/store.py:181-218`, `notion_brain/provider.py:709, 908, 953`
- Cause: `page_size` only controls Notion per-page limit, not total returned count.
- Improvement path: Add a `limit: int | None` parameter that halts pagination once enough items are retrieved.

## Fragile Areas

**Heuristic Classifier and Regular Expression Routing:**

- Files: `notion_brain/extract.py:26-77, 263-335`
- Why fragile: Keyword regexes (`_TRIGGERS_TASK`, `_TRIGGERS_PROJECT`, `_TRIGGERS_DECISION`) frequently misclassify technical programming conversation (e.g. discussing code commits, build artifacts, or debugging). Negation checks (`"not a" in user_lower`) are brittle.
- Safe modification: Add comprehensive characterization test suites before editing regex patterns.
- Test coverage: Covered in `tests/test_extract.py`, but real-world multi-turn conversational coverage is minimal.

**Markdown Parsing via Line-by-Line Prefix Matching:**

- Files: `notion_brain/helpers.py:48-164`
- Why fragile: Disk memory parser splits text using line prefixes (`#`, `- `, `* `). Python comments (`# comment`) inside code snippets or sub-bullets trigger accidental section flushes and break entries into fragmented strings.
- Safe modification: Implement code block fence tracking (```` ... ````) to ignore markdown markers inside code blocks.
- Test coverage: Only 3 basic tests in `tests/test_auto_sync.py`.

**Strict Database Schema Option Equality Checks:**

- Files: `notion_brain/bootstrap.py:454-468`
- Why fragile: `_database_schema_matches` checks that Notion options exactly equal expected options. If a user customizes colors or adds a tag option in Notion UI, it flags a schema mismatch and marks the database for archival during `reset`.
- Safe modification: Check that expected options are a subset of actual options rather than demanding set equality.

## Scaling Limits

**Notion API Rate Limits (3 requests/second average):**

- Current capacity: ~3 requests/second average per integration token.
- Limit: A single turn with multiple classified entries or a search hydration triggers 10-25 requests, causing HTTP 429 Too Many Requests.
- Scaling path: Introduce an internal request rate limiter queue with token-bucket pacing.

**Notion Rich Text Block 2000-Character Maximum:**

- Current capacity: 2000 characters per text object.
- Limit: Content longer than 2000 characters is hard-truncated via `[:2000]` in `store._rich_text`.
- Scaling path: Split content into multiple rich-text objects or write page body blocks via `append_block_children`.

**Single Worker Daemon Thread Execution:**

- Current capacity: Single background worker thread with `queue.Queue`.
- Limit: Network lag on Notion or local LLM blocks memory processing for subsequent turns. On session end, `join(timeout=5.0)` may abandon in-flight writes.
- Scaling path: Increase session shutdown timeout to match max retry budget and use an asynchronous task runner.

## Dependencies at Risk

**`requests` Synchronous Client:**

- Risk: Synchronous, blocking network requests inside an agent runtime that uses asynchronous execution.
- Impact: Network delays block agent threads; no native asyncio integration.
- Migration plan: Migrate `store.py` to `httpx` or `aiohttp` for non-blocking I/O.

**Unpinned `setuptools` Build Backend:**

- Risk: Relies on `setuptools>=68.0` with custom build scripts and entry-point hooks.
- Impact: Vulnerable to upstream setuptools deprecations regarding editable installs and package discovery.
- Migration plan: Adopt `hatchling` or `flit` standard build backends.

## Missing Critical Features

**Body Block Writing for Long Content:**

- Problem: The provider only writes to database properties, truncating text at 2000 characters. Writing multi-paragraph notes or code snippets into page body blocks is not implemented.
- Blocks: Storing comprehensive documents, session summaries, and code snippets.

**Delete and Archive Tool Operations:**

- Problem: LLM agent tools have no action to delete or remove outdated memories via `notion_brain_remember` or `notion_brain_search`.
- Blocks: Memory self-correction, user privacy deletion requests, and knowledge deduplication.

**Filter by Tags or Entities in Search:**

- Problem: `notion_brain_search` only supports searching by keyword and filtering by database. Filtering by tags or linked entities is not exposed to the agent.
- Blocks: Precise contextual memory retrieval by project tag or person entity.

## Test Coverage Gaps

**`notion_brain/config_schema.py`:**

- What's not tested: Entire module has 0% coverage; crashes on standalone import due to missing `plugins` module.
- Files: `notion_brain/config_schema.py`
- Risk: Broken config definitions and runtime failure if loaded.
- Priority: High

**`notion_brain/__main__.py` Subcommands and Error Handling:**

- What's not tested: `update`, `import`, `setup`, and CLI error exits (45% statement coverage, 111 missed lines).
- Files: `notion_brain/__main__.py`
- Risk: Installer and CLI crashes when users execute CLI commands.
- Priority: High

**`notion_brain/bootstrap.py` Recovery and Interactive Paths:**

- What's not tested: Database rebinding, interactive setup wizard, schema repair edge cases (61% statement coverage, 183 missed lines).
- Files: `notion_brain/bootstrap.py`
- Risk: First-time setup failures on existing or partially configured workspaces.
- Priority: High

**`notion_brain/store.py` Network Failure and Retry Branches:**

- What's not tested: Retry-After HTTP header parsing on 429, timeout retry exhaustion, connection error handling (68% statement coverage, 94 missed lines).
- Files: `notion_brain/store.py`
- Risk: Unhandled API edge cases causing uncaught crashes during rate limits or network hiccups.
- Priority: Medium

**`notion_brain/helpers.py` Markdown Parser Edge Cases:**

- What's not tested: Multi-line headers, code blocks, complex frontmatter, and corrupted memory files (76% statement coverage, 30 missed lines).
- Files: `notion_brain/helpers.py`
- Risk: Silently malformed or dropped memories during disk auto-sync.
- Priority: Medium

---

*Concerns audit: 2026-09-20*
