---
last_mapped_commit: 7e1e184f80b4352228eef67fc0fa0a4432cdabbd
last_mapped_at: 2026-09-20
---
<!-- refreshed: 2026-09-20 -->

# Architecture

**Analysis Date:** 2026-09-20

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Hermes Agent Runtime                            │
├──────────────────────┬───────────────────────────────┬──────────────────────┤
│    Lifecycle Hooks   │        Prefetch Engine        │     Tool Dispatch    │
│ `provider.sync_turn` │      `provider.prefetch`      │ `handle_tool_call`   │
└──────────┬───────────┴───────────────┬───────────────┴──────────┬───────────┘
           │                           │                          │
           ▼                           ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Extraction & Normalization Layer                     │
│  `notion_brain/extract.py` (LLM / Regex Heuristic Classifier)                │
│  `notion_brain/schema.py`  (`BrainEntry`, Redaction, Domain Mapping)        │
│  `notion_brain/helpers.py` (Disk Parsing & Schema Coercion)                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Background Sync & Worker                           │
│  `notion_brain/provider.py` (Threaded `_worker_loop` + `queue.Queue`)       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Notion REST Store Client                          │
│  `notion_brain/store.py` (Retry, Pagination, Property Encoders)             │
│  `notion_brain/bootstrap.py` (Workspace Setup, DB Repair & Cache)           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                External Notion API / Workspace (7+ Databases)               │
│  `https://api.notion.com/v1`                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `NotionBrainProvider` | Plugin lifecycle, Hermes hooks, background sync queue, tool routing | `notion_brain/provider.py` |
| `BrainEntry` & Schema | Canonical data carrier, secret sanitization, domain-to-database routing | `notion_brain/schema.py` |
| `Extract` | Turn classification into structured entries via LLM or regex heuristics | `notion_brain/extract.py` |
| `Store` | Low-level HTTP REST client for Notion API with exponential backoff and pagination | `notion_brain/store.py` |
| `Bootstrap` | Parent page and database provisioning, schema drift repair, disk sync hash caching | `notion_brain/bootstrap.py` |
| `Helpers` | Disk memory parsing (`MEMORY.md`, `USER.md`, `CLAUDE.md`) and select option guards | `notion_brain/helpers.py` |
| `Tool Schemas` | Declarative JSON schemas for Hermes agent function calling | `notion_brain/schemas.py` |
| `CLI Interface` | Command-line management (`reset`, `health`, `import`, `setup`, `url`, `wipe`) | `notion_brain/__main__.py` |
| `Config Surface` | Declarative UI configuration spec for desktop integration | `notion_brain/config_schema.py` |

## Pattern Overview

**Overall:** Layered Provider Plugin with Pipeline Processing and Asynchronous Background Persistence.

**Key Characteristics:**

- **Decoupled carrier object:** `BrainEntry` serves as the sole strongly-typed entity passed through classification, sanitization, and persistence stages.
- **Non-blocking agent loop:** Conversation turns and disk sync routines run in a serialized background daemon thread (`queue.Queue`), ensuring agent interactions never stall on Notion API network round-trips.
- **Fail-safe fallback design:** LLM memory extraction transparently falls back to deterministic regex heuristics on timeout or HTTP failure; missing Notion schemas fail gracefully without dropping memory payloads.
- **Strict redaction boundary:** Multi-pattern regex token redactor operates as a mandatory pre-network and pre-log gate across all write paths.

## Layers

**Plugin & Tool Interface Layer:**

- Purpose: Integrates with Hermes memory provider contract and exposes agent tools.
- Location: `notion_brain/provider.py`, `notion_brain/schemas.py`
- Contains: `NotionBrainProvider` class, tool execution dispatchers, tool JSON schemas.
- Depends on: `extract.py`, `store.py`, `bootstrap.py`, `schema.py`, `helpers.py`.
- Used by: Hermes Agent Runtime, CLI scripts, and `notion_brain/__init__.py`.

**Extraction & Transformation Layer:**

- Purpose: Classifies raw dialogue turns and markdown text into categorized memory structures.
- Location: `notion_brain/extract.py`, `notion_brain/helpers.py`
- Contains: `classify_turn()`, `extract_with_llm()`, `parse_disk_memory_text()`, trigger regexes.
- Depends on: `schema.py`, `requests` (for local LLM extraction).
- Used by: `provider.py`, `__main__.py` (import subcommand).

**Domain Model & Security Layer:**

- Purpose: Defines entity contracts, constants, secret sanitization, and routing mappings.
- Location: `notion_brain/schema.py`
- Contains: `BrainEntry`, `redact_secrets()`, `normalize_domain()`, `clean_title()`, custom domain registry.
- Depends on: Python stdlib (`re`, `dataclasses`).
- Used by: All modules across `notion_brain`.

**Persistence & API Client Layer:**

- Purpose: Executes synchronous HTTP requests against Notion's REST API.
- Location: `notion_brain/store.py`
- Contains: HTTP request wrappers, pagination handlers, property payload formatters.
- Depends on: `requests`, `schema.py` (`NOTION_API_VERSION`, `redact_secrets`).
- Used by: `provider.py`, `bootstrap.py`.

**Infrastructure & Workspace Provisioning Layer:**

- Purpose: Idempotent Notion workspace bootstrap, schema repair, and local state management.
- Location: `notion_brain/bootstrap.py`
- Contains: `ensure_brain()`, `health_report()`, `reset_databases()`, schema repair logic.
- Depends on: `store.py`, `schema.py`.
- Used by: `provider.py` (initialization), `__main__.py` (CLI commands).

## Data Flow

### Primary Request Path (Turn Sync)

1. Hermes invokes background turn hook: `NotionBrainProvider.sync_turn(user_content, assistant_content)` (`notion_brain/provider.py:203`).
2. Turn task enqueued into `self._sync_queue` and consumed by background thread worker `_worker_loop` (`notion_brain/provider.py:172`).
3. Worker invokes `_process_sync_turn` (`notion_brain/provider.py:188`).
4. Extractor classifies turn: `extract.classify_turn()` attempts `extract_with_llm()` (`notion_brain/extract.py:112`) and falls back to regex rules (`notion_brain/extract.py:258`).
5. Extracted items normalized: `BrainEntry.normalized()` (`notion_brain/schema.py:126`) strips secrets and enforces field constraints.
6. Target database resolved: `S.database_for_domain()` maps domain to database key (`notion_brain/schema.py:170`).
7. Title deduplication check: `store.search_page_by_title()` checks if matching entry exists (`notion_brain/provider.py:458`).
8. Page creation or update: calls `store.update_page()` (`notion_brain/store.py:250`) if existing, otherwise `store.create_database_page()` (`notion_brain/store.py:237`).
9. Network dispatch: `store._request()` executes `POST /v1/pages` with auth headers and retry handling (`notion_brain/store.py:69`).
10. Invalidate prefetch cache: `self._prefetch_cache = ""` ensures subsequent turns retrieve fresh context (`notion_brain/provider.py:197`).

### Secondary Flow 1: Context Prefetch (Smart Recall)

1. Hermes runtime requests memory context before user query: `NotionBrainProvider.prefetch()` (`notion_brain/provider.py:138`).
2. Checks cached context in memory under `self._prefetch_lock` (`notion_brain/provider.py:139`).
3. If empty, queries Notion Memory database: `store.query_database()` with sort on `Last Seen` descending (`notion_brain/provider.py:148`).
4. Formats top 10 entries as markdown bullet list with kind, title, and sanitized content (`notion_brain/provider.py:157`).
5. Stores formatted string in `self._prefetch_cache` and returns block for prompt injection.

### Secondary Flow 2: Explicit Tool Execution

1. Agent calls tool via `NotionBrainProvider.handle_tool_call(tool_name, arguments)` (`notion_brain/provider.py:365`).
2. Dispatcher maps name to internal tool methods (`_tool_search`, `_tool_remember`, `_tool_task`, `_tool_content`, `_tool_research`).
3. For write operations, input arguments are sanitized via `S.redact_secrets()` (`notion_brain/provider.py:665`).
4. Updates run page ownership verification via `_check_page_in_db()` (`notion_brain/provider.py:792`) to prevent cross-database overwrites.
5. Returns JSON response string `{"result": ..., "error": False/True}`.

### Secondary Flow 3: Local Disk Auto-Sync

1. Provider initialization checks local `$HERMES_HOME/MEMORY.md` and `USER.md` (`notion_brain/provider.py:111`).
2. Computes SHA-256 digest of concatenated disk files (`notion_brain/provider.py:240`).
3. Compares against `disk_sync_hash` stored in `$HERMES_HOME/notion_brain.json` (`notion_brain/provider.py:243`).
4. If hash changed, parses sections with `helpers.parse_disk_memory_text()` (`notion_brain/helpers.py:48`).
5. Iterates parsed items, normalizes into `BrainEntry`, writes to Notion, and updates cache file (`notion_brain/provider.py:270`).

**State Management:**

- **Persistent remote state:** Maintained in Notion workspace across 7 core databases (`Memory`, `Tasks`, `Projects`, `Content`, `Research`, `Career`, `Entities`) plus registered custom databases.
- **Local metadata cache:** Stored in flat JSON file `$HERMES_HOME/notion_brain.json` holding `parent_page_id`, database IDs (`db_<name>`), custom database schemas, and disk sync checksums.
- **In-memory state:** `NotionBrainProvider` instance holds thread locks, background task queue, database ID map, and ephemeral string prefetch cache.

## Key Abstractions

**`BrainEntry` Dataclass:**

- Purpose: Uniform representation of an extracted or user-supplied memory item before persistence.
- Examples: `notion_brain/schema.py:112`
- Pattern: Value Object / Data Transfer Object (DTO) with self-normalizing `.normalized()` method.

**`NotionBrainProvider`:**

- Purpose: Facade implementing Hermes agent long-term memory provider interface.
- Examples: `notion_brain/provider.py:65`
- Pattern: Adapter / Provider pattern implementing pluggable lifecycle hooks and tool handlers.

**`store` Module:**

- Purpose: Stateless functional wrapper over Notion HTTP API.
- Examples: `notion_brain/store.py:69`
- Pattern: Gateway / Data Mapper isolating Notion JSON schema shapes and HTTP semantics from domain logic.

**`_STATUS_OPTIONS` & Schema Definitions:**

- Purpose: Definitive source of truth for database properties and selectable values.
- Examples: `notion_brain/bootstrap.py:25`, `notion_brain/bootstrap.py:70`
- Pattern: Schema Specification enforcing database column types across initial setup and automated repair.

## Entry Points

**Hermes Plugin Hook (`register`):**

- Location: `notion_brain/provider.py:969`, `notion_brain/__init__.py:20`
- Triggers: Loaded by Hermes plugin discovery via entry point `"hermes_agent.memory_providers"`.
- Responsibilities: Instantiates and registers `NotionBrainProvider` with agent context.

**CLI Entry Point (`hermes-brain` / `python -m notion_brain`):**

- Location: `notion_brain/__main__.py:30`
- Triggers: Invoked by user in terminal or installer scripts.
- Responsibilities: Dispatches subcommands (`reset`, `health`, `url`, `wipe`, `import`, `setup`, `update`).

**Module Helper Functions:**

- Location: `notion_brain/__init__.py:59-114`
- Triggers: Direct import in automation scripts or third-party workflows (`ensure_brain`, `remember`, `search_entries`).
- Responsibilities: Creates lightweight provider instance to run standalone memory tasks.

## Architectural Constraints

- **Threading:** Background worker runs on a single daemon thread (`notion-brain-sync-worker`) consuming from a synchronized `queue.Queue`. All worker tasks are serialized, eliminating race conditions against Notion API rate limits.
- **Global state:** Custom databases registered at runtime reside in module-level dictionaries in `notion_brain/schema.py` (`_CUSTOM_DOMAINS`, `_CUSTOM_DATABASES`, `_CUSTOM_DOMAIN_DB`, `_CUSTOM_METADATA`). Must be refreshed or cleared via `clear_custom_domains()` in test fixtures.
- **Dependency boundaries:** Zero heavy framework dependencies; strictly `requests>=2.28` and Python standard library. Hermes framework imports remain duck-typed and lazy.
- **Token limit chunking:** Notion block text limits (2,000 characters per block) require input truncation to 900–1,900 characters via `compact()` before transmission.

## Anti-Patterns

### Unsanitized Error Logging

**What happens:** Logging raw exceptions or error messages when Notion API calls fail: `logger.error(f"Error: {exc}")`.
**Why it's wrong:** Exception strings often echo the requested payload or URL containing private keys, access tokens, or sensitive user conversation snippets.
**Do this instead:** Wrap all exception logging in `S.redact_secrets(str(exc))` as enforced in `notion_brain/provider.py:108` and `notion_brain/store.py:96`.

### Creating Duplicate Pages on Title Match

**What happens:** Directly invoking `store.create_database_page()` for every write without checking existing titles.
**Why it's wrong:** Clutters Notion databases with repetitive pages when agent revisits tasks or project decisions.
**Do this instead:** Look up existing page by title in target database using `store.search_page_by_title()` and update via `store.update_page()` when found (`notion_brain/provider.py:458-475`).

### Bypassing Status Option Validation

**What happens:** Writing arbitrary string values into a Notion `status` or `select` property.
**Why it's wrong:** Notion API strictly validates status against predefined schema options and returns HTTP 400 rejection for unknown options.
**Do this instead:** Validate candidate values against live database schema options using `_safe_select_value()` and `_status_property()` (`notion_brain/helpers.py:9`, `notion_brain/provider.py:540`).

## Error Handling

**Strategy:** Fail-soft with graceful degradation for user-facing agent turns; strict fail-fast with actionable error reports for administrative CLI workflows.

**Patterns:**

- **Retry with Exponential Backoff:** Transient network errors, rate limits (HTTP 429), and 5xx gateway errors automatically retry up to 3 times with dynamic delay honoring the `Retry-After` header (`notion_brain/store.py:77-89`).
- **Heuristic Fallback:** If local LLM extraction (`extract_with_llm`) times out (default 5.0s) or fails, extraction automatically falls back to regex pattern matching without raising exceptions (`notion_brain/extract.py:255`).
- **Self-Healing DB IDs:** CLI routines trigger `_self_heal()` prior to running queries, detecting archived or trashed databases and rebinding cache IDs to active instances (`notion_brain/__main__.py:16`, `notion_brain/bootstrap.py:227`).

## Cross-Cutting Concerns

**Logging:** Standard library `logging.getLogger(__name__)`. All logged payloads and exception strings pass through `S.redact_secrets()` to ensure zero credential leakage in system logs.
**Validation:** Domain keys normalized to known database mapping (`notion_brain/schema.py:144`); string lengths constrained (`clean_title` max 120 chars, `compact` max 900 chars); status properties strictly checked against schema options.
**Authentication:** Synchronous token resolution via `store.get_api_key()`. Checks process `NOTION_API_KEY`, falling back to reading `$HERMES_HOME/.env`. Shell profiles are strictly bypassed to adhere to least-privilege security policy.

---

*Architecture analysis: 2026-09-20*
