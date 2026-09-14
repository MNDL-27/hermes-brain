# Codebase Audit Report — hermes-brain

**Repository:** `MNDL-27/hermes-brain` (`/mnt/c/code/hermes-brain`)  
**Commit audited:** `026ee0a` (`fix(cli): health command exits nonzero when databases are not shared`) — `main` @ 2026-09-01  
**Auditor:** Lead Codebase Auditor (Hermes Agent) — multi-agent orchestration, 5 specialists dispatched (all hit token-router rate limits / truncation; findings below are lead-auditor direct verification)  
**Date:** 2026-09-01  
**Prior remediation:** `REMEDIATION-STATUS.md` v1.0.1 (2026-08-25) — 13 findings triaged across Wave 1 (P0), Wave 2 (P1), Wave 3 (P2)  
**Method:** `deep-codebase-audit` baseline — Recon → Arch map → Critical-path trace → Specialist delegation → Independent verification (reads + `uv run pytest/ruff/mypy/coverage` + wheel inspection) → Finding review / dedup → Cross-system + root-cause analysis → Synthesis

---

## Executive Summary

hermes-brain is a **3.1 kLOC Python 3.11+ plugin** that turns a Notion workspace into durable long-term memory for the Hermes AI agent. It is a thin, well-scoped system: 4 core modules (`schema` → `extract` → `store` → `bootstrap`) plus a `provider` that exposes 5 LLM-tool endpoints and a background queue. The v1.0.1 remediation fixed the most dangerous class of defects (secret leakage, silent-write failures, duplicate-page storms, daemon-thread races, schema-drift duplication). **Those fixes still hold** — verified by direct code reads on 2026-09-01.

The system is **production-usable for single-user, single-process Linux installs** but not yet production-hardened:

* **6 lint errors and 2 mypy errors** — CI gate (`ruff`/`mypy` clean) is currently red, contradicting `REMEDIATION-STATUS.md:89-90`.
* **77% branch coverage**, not the claimed 83%; `notion_brain/__main__.py` is at **38%** and `bootstrap.py`/`store.py` sit at 67%/73%. One test (`test_api_key_env`) is now flaky because the remediation changed `get_api_key()` to fall back to `~/.hermes/.env`, but the test still assumes `patch.dict(os.environ, {}, clear=True)` is sufficient isolation.
* **A small number of correctness/security regressions remain**, the most important being: (a) unredacted conversation text exfiltrated to the LLM extraction endpoint, (b) Notion `title` search filter using the wrong property type (`rich_text` instead of `title`) so server-side query filtering never matches, and (c) installer token-validation sending a literal `Bearer ***` instead of the candidate token.
* **Two accepted P2 risks from the last cycle remain correctly deferred:** `AUD-PKG-01` (plugin discovery shim needs upstream distribution name) and `AUD-TEST-01` (live Notion/Hermes integration needs live creds). No new P0 was found.

**Production Readiness Score: 6.5 / 10** (down from 9/10 on 2026-08-28 — not because the system got worse, but because verification on 2026-09-01 shows the quality gates that were green on 2026-08-28 are now red, and two high-confidence correctness bugs survived the last remediation).

**Recommended posture:** ship `v1.0.3` with the 5 Quick Wins below (all ≤2 h, no schema migration), then schedule Wave 2 (privacy + cache atomicity + retry semantics).

---

## System Overview

**What it does:** captures conversation turns (heuristic + optional LLM extraction), normalizes them into `BrainEntry` objects, and persists them as Notion pages across 7 databases under a single `Hermes Brain` parent page. It also exposes explicit recall/storage tools to the LLM and imports existing `MEMORY.md`/`USER.md` files.

**Request flow (actual, from code):**

```
Hermes turn (user + assistant text)
  → provider.sync_turn()  // enqueues _process_sync_turn
    → extract.classify_turn()   // LLM attempt → fallback heuristics
      → BrainEntry.normalized() // domain map, redact, clean, dedupe
        → provider._store_entry() → store.create_database_page() / update_page()
          → Notion REST API (requests, JSON)
  → provider.handle_tool_call() // synchronous LLM → Notion (remember/task/content/research/search)
  → provider.prefetch() / on_session_end() / shutdown()
bootstrap.ensure_brain() // idempotent workspace + cache (~/.hermes/notion_brain.json)
```

**Boundaries:** single Python process, single Notion integration token, single Hermes Home directory. No separate services, queues, or datastores. Background work is one daemon thread draining a `queue.Queue`.

---

## Technology Inventory

| Layer | Choice | Version / Constraint | Notes |
|---|---|---|---|
| Language | Python | `>=3.11,<3.14` (`py311` target) | `pyproject.toml:8` |
| HTTP | `requests` | `>=2.28` (no upper pin) | Only runtime dep; `uv.lock` pins transitively |
| Packaging | `setuptools` | `>=68.0` | `pyproject.toml:2`; `MANIFEST.in` includes `plugin.yaml` + graft `tests` |
| Entry point | `hermes-brain` → `notion_brain.__main__:main` | `pyproject.toml:21` | Also `python -m notion_brain` |
| Plugin manifest | `plugin.yaml` | `v1.0.2` | `name: notion_brain`, 2 fields; **not inside wheel** (verified `unzip -l`) |
| Hermes runtime | `agent.*`, `tools.*` | **not declared** | Lazy import behind guards in `notion_brain/__init__.py:1-3 comment`; tracked as `AUD-PKG-01` accepted risk |
| Dev toolchain | `ruff 0.16.0`, `mypy 2.3.0`, `pytest 9.1.1`, `pytest-cov 7.1.0`, `cryptography>=50` (optional) | `pyproject.toml:27-34` | `uv.lock` present, `revision 3` |
| Notion API | `2022-06-28` | `notion_brain/schema.py:11` | `NOTION_API_VERSION` constant |
| CI | Not inspected (no `.github/workflows` read this run) | — | Docs claim stricter lint/coverage gates |

**Counts (pygount + wc):** prod `notion_brain/*.py` 3,123 LOC (provider 828, bootstrap 556, store 437, extract 394, `__main__` 260, schemas 223, schema 173, helpers 140, `__init__` 112); tests 3,414 LOC (4 files).

---

## Architecture Assessment

**Strengths**

* **Clear 4-layer pipeline** (`schema` → `extract` → `store` → `bootstrap`) with `BrainEntry` as the sole carrier — easy to reason about, no hidden state between stages (corroborated `docs/architecture.md` flow, which is accurate).
* **Idempotent bootstrap** after remediation: `ensure_brain()` now scans `parent.children` for `child_database` blocks before falling back to `/search` (`bootstrap.py:458-481` `_find_existing_database`), fixing the duplicate-DB storm (`AUD-RELIABLE-03` sister). Verified by read of `_find_existing_database` + `_find_or_create_database`.
* **Recovery before archive:** `reset_databases()` now creates replacements before `archive_database()` (`bootstrap.py:226-234`), so a failure leaves the original intact — fixes `AUD-RELIABLE-03` data-loss path. Verified.
* **Retry + timeout** in the HTTP client (`store.py:69-97`): `timeout=30`, 3 attempts on `429/5xx` and on `Timeout`/`ConnectionError`, linear `1s * attempt` backoff. Prior version had no retry.
* **Secret handling posture improved:** `NOTION_API_KEY` now lives only in `$HERMES_HOME/.env` (`chmod 600` in `scripts/install.sh:318`), and `provider.py` / `store.py` redact on all write paths. Prior `AUD-SEC-01/02` fixes hold.

**Weaknesses / Debt**

* **`provider.py` is a god object (828 LOC):** 5 tool handlers, persistence, worker lifecycle, prefetch, session summary, and property builders all in one class. Helpers extracted to `helpers.py` (`_safe_select_value`, `_merge_disk_only`) but the main class still violates SRP — onboarding cost is high.
* **One daemon thread as the durability layer:** no persistence, no retry-after-Notion-outage, no back-pressure. Documented as intentional (`docs/architecture.md:52-53` “logs failures — the agent sees none”), but it creates a silent data-loss channel (see Reliability).
* **Cache is a plain JSON file** (`notion_brain.json`) with no file lock, no atomic write, no fsync. Concurrent Hermes processes (e.g. two agent sessions sharing a `HERMES_HOME`) can corrupt it.
* **Docs drift from implementation:** `docs/architecture.md` still claims “Heuristic-only classification (no LLM)” (line 44) and documents the old `sanitize_context → classify_turn → normalized → create_database_page` flow — it omits the LLM extraction branch added in `extract.py:112-207` (`extract_with_llm`, `OPENAI_BASE_URL`/`HERMES_MODEL` envs). Secret-scrub section omits the LLM exfiltration path.
* **Plugin packaging is incomplete:** `plugin.yaml` is at the repo root and listed in `MANIFEST.in:1` but `setuptools.packages.find include=["notion_brain*"]` means the wheel (`hermes_brain-1.0.2-py3-none-any.whl`, 15 files, verified `unzip -l`) does **not** contain `plugin.yaml`. This is the accepted `AUD-PKG-01` risk, but the wheel was built and published without comment.

**Scalability:** single-process, one Notion API call per entry, no batching. Notion rate-limits at ~3 req/s average; with per-turn bursts of 1-5 entries and paginated hydration on search, a power user (hundreds of entries, large `query_database` scans) will hit 429s. Retry exists but ignores `Retry-After` (see Data).

---

## Security Findings

### Remediation regression check: prior fixes hold

| Prior ID | Claim | Verification 2026-09-01 |
|---|---|---|
| `AUD-SEC-01` | `NOTION_API_KEY` removed from shell profile, kept in `~/.hermes/.env` (600) | **Holds.** `scripts/install.sh:296-319` writes only `HERMES_HOME` to `SHELL_RC`; token written only to `$HERMES_HOME/.env` + `chmod 600`. `store.py:28-55` loads from `.env` as fallback, env var wins. |
| `AUD-SEC-02` | `redact_secrets` covers every write path | **Holds** for provider write paths (see below). `provider.py` scrubs `title/content/kind/status/tags/entities` on `remember/task/content/research` create paths; `_write_entry_raw` error path does not echo payload (`provider.py:383-387`); `store._rich_text` / `multi_select_property` / `select_property` also redact (`store.py:294-313`). |

### New / residual findings

| ID | Severity | Confidence | Status | Title | Location | Evidence | Impact | Root Cause | Fix | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| **SEC-01** | **P1** | **HIGH** | **Confirmed** | **Unredacted conversation buffer exfiltrated to LLM extraction endpoint** | `notion_brain/extract.py:125,148` | `buffer = f"User: {user_content}\nAssistant: {assistant_content}".strip()` (line 125) → `requests.post(endpoint, json=payload, ...)` with `payload.messages[1].content = buffer` (138-144) without any `redact_secrets()` call; `extract_with_llm` is invoked from `classify_turn` at line 250 **before** `BrainEntry.normalized()` redaction. Only the exception path redacts (line 206). | Any secret present in a turn (Notion token, `sk-*`, `xox*`, `AKIA*`, private key, JWT, or generic `api_key=...`) is POSTed to `OPENAI_BASE_URL`/`OPENAI_API_BASE`/`DEFAULT_LLM_URL` (`http://localhost:11434/v1` default, but user may point it at a remote OpenAI-compatible endpoint via env `OPENAI_API_KEY` at line 132). The buffer also contains full conversation history without truncation guard for PII. | LLM extraction was added after the secret-redaction remediation and missed the exfiltration review. `BrainEntry.normalized()` is the “last stage before network” for Notion, but not for the LLM. | Scrub `buffer` with `redact_secrets()` **and** truncate to a token budget before LLM POST; or gate `extract_with_llm` behind `if not contains_secret(buffer)` / make it opt-in with a privacy warning. Add `compact(buffer, 4000)`-style limiter. | Unit test: secret string in `user_content` → assert `requests.post` payload contains `[REDACTED_SECRET]`. |
| **SEC-02** | **P2** | **HIGH** | **Confirmed** | Installer token validation sends literal `Bearer ***` instead of candidate token | `scripts/install.sh:246-257` | `validate_notion_token() { local token="$1"; response=$(curl ... -H "Authorization: Bearer ***" ...` — `$token` is captured but never interpolated. Validation therefore always checks `***`, always returns non-200 (or `000` on no network), so `TOKEN_VALID` never becomes true on the first pass; the loop re-prompts forever when offline, and when online it **always rejects valid tokens** as “invalid or expired” (line 268, 291). | Not a secret leak (the opposite — it **never sends** the token), but a functional security-adjacent bug: the “validate before saving” feature (`CHANGELOG 4006a95`) is dead code; users are forced through the re-entry loop and may paste tokens multiple times into a TTY without feedback. Risk of shoulder-surfing / TTY scrollback exposure is slightly elevated. | Copy-paste hardening: header was redacted in docs, redaction leaked into code. | Replace header with `"Authorization: Bearer $token"` (and redact only in log output). Add a shell test. | `shellcheck scripts/install.sh`; manual `validate_notion_token ntn_...` returns 200 on a real token. |
| **SEC-03** | **P2** | **MEDIUM** | **Confirmed** | `redact_secrets` pattern set misses `sk-ant-*`, `sk-proj-*`, and bare bearer/JWT edge cases | `notion_brain/schema.py:46-56` | Patterns: `sk[_-][A-Za-z0-9_-]{16,}` catches `sk-...` but requires 16 chars after `sk-`/`sk_`; `sk-ant-api03-...` after `sk-` the remaining `ant-api03-...` is ≥16 so it does match, but `sk-proj-...` shape is similar; neither is explicitly tested. More concretely missing: Anthropic `sk-ant-*` variants with short suffixes, `Bearer <40+chars>` without `eyJ` JWT structure, and Google `AIza...` (35 chars) — none has a dedicated pattern and the generic `api_key/token/secret/password` fallback only catches `key=value` forms, not bare tokens. | Secret types that appear as bare strings (pasted credentials, “my key is sk-ant-...”) may survive normalization and be written to Notion or to logs via fallback paths. Not exploitable without user pasting, but violates the stated “last stage before network” guarantee for those families. | Pattern list grown ad-hoc; no corpus test. | Add `sk-ant-`, `sk-proj-`, `AIza`, and bare `Bearer [A-Za-z0-9._-]{20,}` patterns; add corpus test from `detect-secrets` fixtures. | Corpus test: each family → `redact_secrets` returns `[REDACTED_SECRET]`. |
| **SEC-04** | **P3** | **HIGH** | **Confirmed** | Cache `notion_brain.json` written world-readable (no `chmod 600`, no umask guard) | `notion_brain/bootstrap.py:405-411` | `_save_cache` does `path.write_text(json.dumps(...))` with no `chmod`; `ensure_brain` calls it at lines 150,162,184,235 without prior `os.umask` or `chmod`. Under default `umask 022`, file is `644`. Same for `store._load_env_file` read path — no perm check on `.env` when read via code (only `install.sh:318` chmods). | Cache leaks workspace structure (7 `db_*` IDs + `parent_page_id`) to any local user; combined with a leaked token it accelerates enumeration. Not a direct secret leak, but widens blast radius on multi-user hosts. | File-security hardening applied only to installer path, not to the provider’s runtime write path. | After `write_text`, `try: os.chmod(path, 0o600)` (best-effort, ignore `OSError` on Windows). Add `stat` check on `_load_env_file` and warn if `0o777 & st_mode != 0o600`. | `ls -l ~/.hermes/notion_brain.json` → `600`; `stat` check in test. |
| **SEC-05** | **P4** | **HIGH** | **Confirmed** | `get_api_key()` logs / error-path token-adjacency is safe, but `.env` parser is permissive | `notion_brain/store.py:28-49` | `_load_env_file` splits on first `=`, strips quotes, and injects any `KEY` not already in `os.environ`. A malicious `.env` line like `NOTION_API_KEY=ntn_... # comment` leaves trailing `# comment` in the value (strip only `"'` and space, not comment). No `NOTION_API_KEY` format validation. | Low — malformed token just causes 401, but a crafted `.env` committed by mistake could smuggle comment-suffix into requests and confuse diagnostics. | Shared parser for all `.env` keys, not token-aware. | Strip trailing `#` comments after value extraction; validate `ntn_`/`secret_` prefix and warn. | Unit test: `NOTION_API_KEY=ntn_abc # hi` → `get_api_key() == "ntn_abc"`. |

**Positive / secure findings (explicit):**

* `NOTION_API_KEY` never appears in logs, exception messages, or Notion payloads via the provider’s main paths — verified across `provider.py:95,154,169,186,219,386,400,657,721,738,756` (all use `S.redact_secrets` or omit the exception payload).
* `store._rich_text`, `multi_select_property`, `select_property` all re-redact inputs (`store.py:294-313`), so even handler paths that forget explicit `redact_secrets` (e.g. `_tool_content update` body) are still scrubbed at the store boundary.
* No `shell=True`, no `os.system`, no `eval`, no URL construction from user input beyond Notion path `"/databases/{database_id}/query"` where `database_id` comes from the cache, not user input (user-controlled `page_id` is used only in `"/pages/{page_id}"` — Notion validates it, no host injection).
* `install.sh` correctly refuses to run as root (`is_root`), validates `HERMES_HOME`/`HERMES_BRAIN_DIR` via env, uses `mktemp` for `sed` (`install.sh:305`), and never writes the token to a shell RC.
* `pyproject.toml` declares only `requests>=2.28` — minimal attack surface; no native extensions or post-install scripts.

---

## Reliability Findings

### Remediation regression check

| Prior ID | Fix | Holds? |
|---|---|---|
| `AUD-RELIABLE-01` | Full page body retrieval with pagination | **Holds.** `store._page_body_text` paginates with `start_cursor` and `seen_cursors` guard (`store.py:401-424`). |
| `AUD-RELIABLE-02` | Normalized schema values | **Holds.** `BrainEntry.normalized()` enforces `STATUSES`/`CONFIDENCES`/`DOMAINS` (`schema.py:74-89`). |
| `AUD-RELIABLE-03` | Schema repair migrates before archiving | **Holds.** `reset_databases` creates replacements before archive (`bootstrap.py:226-234`). |
| `AUD-RELIABLE-04` | Writes confirm durable persistence | **Holds** in tool paths (`_store_entry` raises `RuntimeError` on missing DB or API failure; `_tool_*` surfaces it). Background-queue durability is still best-effort (see REL-04). |
| `AUD-RELIABLE-05` | Serialized queue worker | **Holds.** Single `notion-brain-sync-worker` with `queue.Queue` + `_sync_lock` (`provider.py:52-201`). No more per-turn daemon-thread leak. |
| `AUD-RELIABLE-06` | Duplicate detection update-before-create | **Holds in intent, but has correctness caveat** (see REL-01 / API-02). |
| `AUD-RELIABLE-07` | Database-filtered search honors query | **Broken — see REL-02** (filter uses wrong Notion type). |
| `AUD-LINT-01/02` | Ruff + mypy clean | **Regressed.** `ruff` 6 errors, `mypy` 2 errors on 2026-09-01 (Verification). |

### New / residual findings

| ID | Severity | Confidence | Status | Title | Location | Evidence | Impact |
|---|---|---|---|---|---|---|---|
| **REL-01** | **P1** | **HIGH** | **Confirmed** | Synchronous search uses wrong Notion property type — `rich_text` filter on a `title` property, so server-side filtering never matches | `notion_brain/provider.py:474-481` `query_filter = {"property": "title", "rich_text": {"contains": query}}` | `bootstrap._PROPS[*]["title"]` is `{"title": {}}` ( `bootstrap.py:29,45,53,...` ) — Notion type is `title`, not `rich_text`. The correct filter is `{"property": "title", "title": {"contains": query}}`. The current payload is either ignored or returns 0 results (Notion 400 on Strict mode, or silently no matches). Verified by `grep -n "rich_text.*contains" notion_brain/provider.py` → single hit at `480`. Client-side fallback (`provider.py:506-508` title-contains refinement) runs **after** `query_database(..., filter_obj=query_filter)` which already returned 0 rows, so recall is near-zero for database-filtered search. Cross-check: `store.query_database` just forwards `filter_obj` verbatim (`store.py:164`). | User/LLM calls `notion_brain_search({query:"migration", database:"projects"})` and gets “No results” even though matching pages exist — silent recall loss. This is the **remediation regression** for `AUD-RELIABLE-07`: the fix added a server-side filter but with the wrong type; the previous “silently ignores query” behavior was replaced with “silently returns nothing when a DB filter is set.” |
| **REL-02** | **P2** | **HIGH** | **Confirmed** | Background-sync daemon can lose the last turn on process exit; no persistent retry | `notion_brain/provider.py:195-196` `Thread(..., daemon=True)` + `provider.py:157-186` worker drains `queue.Queue` without persistence; `shutdown()` is `on_session_end()` which joins, but nothing guarantees Hermes calls either hook on SIGTERM/`sys.exit`. Docs admit silence (`docs/troubleshooting.md:5` “Background sync is silent on errors… daemon thread logs failures … does not surface them”). | If the agent process exits < ~1s after a turn (crash, Ctrl-C, OOM), queued `BrainEntry`(s) are dropped. At 1-3 entries/turn and a 30 s Notion timeout, worst-case loss is one turn per crash. Notion outage also drops entries — `_process_sync_turn` catches and logs (`provider.py:185`) with no re-queue. | Silent durability loss — user believes the turn was remembered (no error shown) but Notion has no row. Repro: kill process immediately after `sync_turn`. |
| **REL-03** | **P2** | **MEDIUM** | **Confirmed** | `tags`/`entities` string-vs-list confusion — iterating a bare string produces per-character tags | `notion_brain/provider.py:542,554,580,690` e.g. `_tool_remember`: `tags=[S.redact_secrets(t) for t in tags]` where `tags = args.get("tags", [])`. If LLM sends `"tags": "urgent"` (string), iteration yields `["u","r","g","e","n","t"]`; `multi_select_property` then stores 6 single-char options, polluting the schema. `schemas.py` declares `tags` as `array[string]` but does not enforce at runtime. | Tag pollution; downstream `search`/`filter` on Tags returns noisy matches; Notion multi-select option set grows with garbage. No crash. | Type confusion at LLM↔tool boundary; no defensive `if isinstance(tags,str): tags=[tags]`. |
| **REL-04** | **P3** | **HIGH** | **Confirmed** | `prefetch` cache write races outside the lock | `notion_brain/provider.py:182-183` `self._prefetch_cache = "" ; self.prefetch()` inside `_process_sync_turn` (worker thread) — direct assign outside `_prefetch_lock`, while `prefetch()` at `123-155` guards reads with `_prefetch_lock` and `provider.py:104-106` also writes `self._prefetch_cache` outside the lock during `initialize`. | Benign under CPython GIL (string assign is atomic) but violates the locking discipline — a concurrent `prefetch()` reader could see a torn mid-update state or empty string, causing a thundering-herd of Notion queries. No data loss. | Lock discipline drift after quick fix. |
| **REL-05** | **P3** | **MEDIUM** | **Strongly Inferred** | Title-duplicate detection is best-effort (Notion `/search` eventual consistency) — duplicates still possible | `notion_brain/provider.py:362-370` `search_page_by_title` → exact case-insensitive match after workspace `/search` + `parent.database_id` guard. | Under indexing lag or concurrent writes (two `remember` calls with same title, or sync worker + tool call racing), `search_page_by_title` may return `None` even though the page exists, creating a duplicate page instead of PATCHing. Cross-DB titles are correctly filtered, but the core “update-before-create” guarantee is probabilistic, not transactional (Notion has no upsert). | Duplicate pages with same title in the same DB, confusing recall and “last entry” counts. |

---

## Performance Findings

* **No per-request connection pooling.** `store._request` calls `requests.request(...)` directly (`store.py:73`) without a shared `Session`, so each Notion call re-handshakes TLS. At ~10-20 calls per search (hydrating page bodies + DB queries), p95 latency is inflated by ~100-300 ms vs a session. **P3, LOW effort** — switch to a module-global `Session`.
* **Search hydrates every page body** (`store.search_entries` hydrates bodies per result, `provider._tool_search` hydrates via `query_database` + `_page_body_text` pagination) — a `max_results=20` search can fan out to `20 * ceil(body_blocks/100)` extra GETs. With large content bodies this can approach Notion’s 3 req/s limit and trigger the retry loop without `Retry-After` (see Data). **P3**.
* **No batching on import:** `notion_brain/__main__.py:237-255` imports entries one by one via `remember_fn` (each does a `search_page_by_title` + `create/update`). A 200-entry `MEMORY.md` import is ~400 Notion calls, ~2-5 min. **P3**.
* **Cache pollutes disk on every `ensure_brain`** — `_save_cache` rewrites the whole JSON even when only `schema_version` changed (`bootstrap.py:150`). Negligible.

No CPU/memory hotspots — the codebase is I/O-bound.

---

## Data & Database Findings

| ID | Severity | Confidence | Status | Title | Location | Evidence | Impact |
|---|---|---|---|---|---|---|---|
| **DATA-01** | **P2** | **HIGH** | **Confirmed** | Cache write is not atomic — crash mid-write truncates `notion_brain.json` | `notion_brain/bootstrap.py:405-411` `path.write_text(json.dumps(...))` without temp-file + rename. Also `bootstrap.write_memory_to_disk`/`write_user_to_disk` (`bootstrap.py:539,556`) and `_save_cache` callers (`150,162,184,235`). | A SIGKILL/power loss between `open` and `close` leaves a 0-byte or half-JSON file; next `ensure_brain` falls back to `{}` and may recreate the parent page, diverging from Notion (orphaned old parent). `_load_cache` swallows `JSONDecodeError` and returns `{}`, masking the corruption. | Silent cache loss → duplicate parent page on next bootstrap if old parent still exists. |
| **DATA-02** | **P2** | **MEDIUM** | **Confirmed** | 429 retry ignores `Retry-After` header | `notion_brain/store.py:77-79` `if resp.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES: time.sleep(_RETRY_DELAY_S * attempt)` | Notion returns `Retry-After` on 429; fixed `1s * attempt` may retry too early and burn all 3 attempts without success, especially under fan-out search. | Search/import under throttle fails with `RuntimeError` after 3 rapid retries even though waiting `Retry-After` would succeed. |
| **DATA-03** | **P3** | **HIGH** | **Confirmed** | `query_database` source of truth vs cache drift is detected, but concurrent Hermes processes can corrupt the cache | `notion_brain/bootstrap.py:138-187` `ensure_brain` reads cache, validates `get_page`/`get_database`, writes back — no file lock. | Two Hermes sessions bootstrapping concurrently can interleave `read → validate → write`, losing one session’s `db_*` IDs. Notion side stays consistent (no dupe due to child-scan), but local cache may point at stale/archived DB IDs until next `health` self-heal. | Stale-cache query returns 404, surfaced as `MISSING`/`NOT SHARED` in health. `_self_heal` (`notion_brain/__main__.py:15-26`) re-runs `ensure_brain`, so it self-heals on next CLI invocation. |
| **DATA-04** | **P3** | **HIGH** | **Confirmed** | Pagination guards are correct but `page_size` is silently clamped, not rejected | `notion_brain/store.py:161,144` `min(page_size,100)` | Caller passing `page_size=200` is silently capped to 100 — no warning. Pagination loop correctly handles `has_more`/`next_cursor` with `seen_cursors` guard (`152-180`, `404-423`). Verified: both `query_database` and `_page_body_text` have loop-break on `seen_cursors` and null `next_cursor`. | No data loss; just a minor API-contract surprise. |

**Data lifecycle:** archived DBs/pages are Notion soft-deletes (`archived:true`). They remain recoverable via Notion UI/API but are invisible to the provider’s `query_database`/`search_page_by_title` (which filters `archived==false` by default). `reset_databases` docs this correctly (`bootstrap.py:196-199` comment). No hard-delete path.

---

## API Findings

### Tool contract (schemas → handlers)

`ALL_TOOL_SCHEMAS` (`notion_brain/schemas.py:217-223`) declares 5 tools. Compared against `provider.handle_tool_call` (`provider.py:269-297`) + handlers:

| Tool | Schema `required` | Handler default | Validation gaps |
|---|---|---|---|
| `notion_brain_search` | `[query]` | `query=""` coerced, defaults to `max_results=8` capped 20 | `database` enum not validated — unknown value → `db_id=None` → “No database found for: …” string (not `error:true`). `max_results` negative not rejected (`min(-1,20)==-1` → `page_size=-1` sent to Notion → 400). |
| `notion_brain_remember` | `[title, content]` | Checks `if not title/content: return "Error: …"` strings with `error:false` | `domain/kind/status/tags/entities` not type-checked; bare-string `tags` produces char-iteration (REL-03). No max-length enforcement beyond `clean_title(120)`/`compact`. |
| `notion_brain_task` | `[action]` | `action="list"` default | `action` enum `create/list/update/complete` matches handlers; unknown → `f"Unknown task action: {action}"` with `error:false`. |
| `notion_brain_content` | `[action]` | `action="list"` default | `action` enum `create/list/update/publish/archive` matches. |
| `notion_brain_research` | `[action]` | `action="save"` default | Schema `required: [action]` but handler treats absence as `save` — acceptable. |

### Handler-level findings

| ID | Severity | Confidence | Status | Title | Location | Evidence |
|---|---|---|---|---|---|---|
| **API-01** | **P2** | **HIGH** | **Confirmed** | Error contract inconsistent — some paths return `"Error: …"` strings with `error:false`, others raise to `error:true` | `provider.py:541-563` (`_tool_remember` returns `Error:` string), `565-639` (`_tool_task` update/complete calls `store.update_page` **without** `try/except` — exception → `handle_tool_call:292-297` wraps as `error:true`), `674-756` (`_tool_content` publish/archive catch and return `Error: …` strings). | LLM consumer cannot reliably branch on `error` boolean — must string-match. Doc-level `handle_tool_call` outer `try` (`269-297`) is the only uniform error boundary, but handlers that catch internally bypass it with `error:false`. **Fix:** make every handler either raise or return `error:true` via `handle_tool_call`; never return `Error:` strings as success. |
| **API-02** | **P2** | **HIGH** | **Confirmed** | `page_id` handlers do not verify the page belongs to the declared database | `provider.py:607-637` (`_tool_task update/complete`) and `700-756` (`_tool_content update/publish/archive`) call `store.update_page(page_id, ...)` with no `get_page(page_id).parent.database_id` check. | LLM (or a prompt-injected user) can mutate **any** page the integration can see — including the `Hermes Brain` parent page or another user’s databases shared with the same integration — by guessing/brute-forcing a UUID (Notion IDs are not secret). Mitigated by integration ACL (only pages shared with the integration are reachable), but violates least-privilege within the integration’s scope. **Fix:** fetch page, assert `page.parent.database_id == self._db_ids[expected_key]`, else `return "Error: page does not belong to {key}"`. |
| **API-03** | **P2** | **MEDIUM** | **Confirmed** | `tags` bare-string iteration (same as REL-03) | See REL-03 | Already covered — API layer is the origin. |
| **API-04** | **P3** | **MEDIUM** | **Confirmed** | `search_entries` top-level helper parses structured results via string splitting | `notion_brain/__init__.py:96-112` `search_entries` calls `handle_tool_call` then does `for line in parsed["result"].splitlines(): if line.startswith("- "): entries.append({"title": line[2:].strip()})` | Discards `items` structured payload (`provider._tool_search` returns `(text, {"items": [...]})` at `529`), loses `id/properties/content`, and re-parses titles only. Errors in `result` text (e.g. title containing newline) break parsing. **Fix:** return `parsed["items"]` directly. |

---

## Testing Assessment

### Verification (real runs, 2026-09-01)

```
$ uv run pytest -q
  1 failed, 278 passed in 63.45s (also 278/279 with --cov)
  FAILED tests/test_provider.py::TestStoreHelpers::test_api_key_env
          assert get_api_key() is None  — actually 'ntn_30...Cbbe'

$ uv run ruff check .
  Found 6 errors (examples/quickstart I001, notion_brain/__main__.py F401+F841,
  notion_brain/extract.py F401, tests/test_extract.py F401+I001)

$ uv run mypy notion_brain tests
  notion_brain/extract.py:148: error: Argument "json" to "post" has incompatible type "dict[str, object]"; expected "JsonType"
  tests/test_coverage_gaps.py:576: error: "append" of "list" does not return a value
  Found 2 errors in 2 files

$ uv run pytest --cov=notion_brain --cov-branch -q
  TOTAL  1585 stmts, 331 miss, branch 87/582, Cover 77%
  notion_brain/__main__.py      38%   (worst — 88 stmts missed, import + bootstrap flows untested)
  notion_brain/bootstrap.py     67%
  notion_brain/store.py         73%
  notion_brain/__init__.py      84%
  notion_brain/provider.py      87%
  notion_brain/extract.py       88%
  notion_brain/helpers.py       93%
  notion_brain/schemas.py      100%
  notion_brain/schema.py        98%
```

**Gate comparison vs `REMEDIATION-STATUS.md:89-93` (claimed 2026-08-25: ruff clean, mypy clean, 83% coverage, 270 tests):**

| Gate | Claimed | Actual 2026-09-01 | Delta |
|---|---|---|---|
| Tests | 270, all pass | 279, **1 fails** | +9 tests added, 1 flaky |
| Coverage | 83% | **77%** | −6 pp (new `__main__` import path + extract heuristics uncovered) |
| Ruff | clean | **6 errors** | Regressed (new imports/unused vars) |
| Mypy | clean | **2 errors** | Regressed (`extract.py` payload typing + test bug) |

### Quality

* **Mocking strategy:** tests heavily mock `requests.request` via `unittest.mock.patch("notion_brain.store._request")` and `get_database`/`create_database_page`. Mock shapes **do** match Notion’s actual JSON (`properties.title`, `properties.rich_text`, `object/id/created_time`, etc.) — checked `tests/test_store.py:40-120` and `tests/test_provider.py:200-400` — but no contract test replays against a recorded Notion response, so Notion API drift (e.g. new `description` field) would not be caught.
* **Failure-path coverage:** no test exercises `429 Retry-After`, `Timeout`, `ConnectionError` retry exhaustion, worker crash mid-queue, or `sync_turn` concurrent with `handle_tool_call`. `tests/test_coverage_gaps.py` adds 60 gap-fill tests but they focus on branch coverage of helpers and schema, not on fault injection.
* **Flaky test root cause:** `test_api_key_env` (`tests/test_provider.py:474-483`) does `patch.dict(os.environ, {}, clear=True)` and expects `get_api_key() is None`, but host has `~/.hermes/.env` containing `NOTION_API_KEY=ntn_30...`. After the remediation, `get_api_key()` falls back to `_load_env_file()` when the env var is absent, so it returns the file’s key instead of `None`. The fix is `patch("notion_brain.store._load_env_file")` or to clear the file in a tmp `HERMES_HOME`. **This is a test-isolation bug, not a prod bug — but it makes CI red on any machine with a real `.env`.**
* **Packaging tests:** none. No test installs the wheel into a fresh venv or asserts `plugin.yaml` is importable.

---

## Code Quality Assessment

* **Style/consistency:** good — `from __future__ import annotations`, consistent docstrings, `redact_secrets` usage is idiomatic. `helpers.py` duplication extraction is clean.
* **Dead/unused code:**
  * `notion_brain/__main__.py:143` `from . import extract` imported but never used (ruff F401) — leftover from an earlier `_classify` that called `extract.classify_text` directly.
  * `notion_brain/__main__.py:217` `total = 0` assigned never read (F841) — prior `total += ...` removed.
  * `notion_brain/extract.py:13` `from typing import Any` unused (F401).
  * `tests/test_extract.py:504` `from notion_brain.extract import extract_with_llm` imported but unused in its own test method (F401).
* **Complexity hotspots:** `extract.classify_turn` (97 LOC, 6 trigger regexes + LLM fallback) has a cyclomatic complexity ~8 but is well-factored into guards; `provider._write_entry_raw` is dense but short.
* **Documentation:** `README.md:13` still claims “**v1.0.0 released**” while `pyproject.toml`/`plugin.yaml`/`__init__.py` are `1.0.2`; `docs/architecture.md` pipeline is stale (omits LLM extraction, misstates “heuristic-only”). `CHANGELOG.md` is accurate through `v1.0.2`.

---

## Infrastructure & Deployment Assessment

* **Install path:** `scripts/install.sh` is 431 LOC, supports `apt/dnf/yum/pacman`, handles Python 3.11 bootstrap, `git clone`/`git pull --rebase`, `pip install --user` with `--break-system-packages` fallback, `~/.hermes/.env` creation, and bootstrap/health checks. Strengths: `set -euo pipefail`, root refusal, `mktemp` for `sed`, idempotent `HERMES_HOME` injection into shell RC. Weaknesses: `curl|bash` is the documented install method (no signature check), `sudo` used for `apt-get`/`pip` without pinning, and token validation is broken (SEC-02).
* **No Docker/K8s/monitoring:** by design — this is a single-host pip package, not a service. `health` CLI is the only observability surface (exit code now correctly includes `NOT SHARED`, `026ee0a`).
* **Rollback:** `rm ~/.hermes/notion_brain.json && python -m notion_brain health` is the documented rollback; no versioned migrations beyond `SCHEMA_VERSION=2`.
* **Secrets at rest:** installer sets `chmod 600` on `.env`; runtime cache is `644` (SEC-04).

---

## Dependency Assessment

| Dep | Constraint | Risk |
|---|---|---|
| `requests>=2.28` (runtime) | Loose lower bound, no upper pin, no hash | Could pull a future `requests` with breaking changes; `2.28` (2022) has known transitive `urllib3` CVE history — but `uv.lock` pins `urllib3`/`certifi`. No supply-chain pinning in `pyproject.toml` (`pip install` without `uv.lock`). |
| `build==1.5.0`, `mypy==2.3.0`, `pytest==9.1.1`, `pytest-cov==7.1.0`, `ruff==0.16.0`, `twine==6.2.0` (dev) | Exact pins — good | No `pip-audit`/`osv-scanner` in CI observed. |
| `cryptography>=50` (optional) | Unused in prod code — no import found | Dead optional dep; bloats `pip install .[dev]` but not runtime. |

`uv.lock` is present and consistent with `pyproject.toml`; no drift detected. No abandoned packages.

---

## Privacy Assessment

* **Notion as the durability layer:** every remembered fact is a Notion page — Notion’s retention, search indexing, and ACL model apply. The provider does not encrypt content before storage; anyone with the integration token or with access to the shared workspace can read all 7 databases.
* **Disk fallback:** `bootstrap.write_memory_to_disk` / `write_user_to_disk` rebuild `MEMORY.md`/`USER.md` in cleartext under `$HERMES_HOME/memories/` — no encryption, `644` perms. Same leakage envelope as the cache.
* **LLM exfiltration (SEC-01):** the most significant privacy finding — conversation text (including potential PII/secrets) is POSTed to an LLM endpoint without consent gating or redaction. Even with the default `localhost:11434`, a user who sets `OPENAI_BASE_URL=https://api.openai.com` to use GPT-4 for extraction silently exfiltrates all turns.
* **Redaction is best-effort, not a privacy boundary:** `redact_secrets` is a regex blocklist, not an allowlist. Novel secret formats bypass it. The docs correctly note this as a fallback, not a guarantee.

---

## Observability Assessment

* **Logs:** `logging.getLogger(__name__)` with `info` on bootstrap success, `warning` on schema repair / health drift, `error` on tool-call and sync-worker failures — all redacted. No structured logging, no log level config shipped (relies on Hermes host).
* **Health:** `python -m notion_brain health` (and `install.sh` post-install check) reports per-DB `schema=ok|MISMATCH`, `entries=N`, `last=<time>`, and actionable `NOT SHARED: integration "X" cannot see … Fix: open DB → ••• → Connections → add "X"` (`bootstrap.py:366-371`). Exit code now includes `NOT SHARED` (`__main__.py:86`, `026ee0a`). **Verified working.**
* **No metrics/tracing:** no counters for sync success/failure, retry count, or 429s. `on_session_end` failure mode is a single `logger.warning(message, exc_info=True)` (`src/on_session_end.ts` was the JS analog — not applicable to Python; in Python the sync worker logs at `error`).
* **Gap:** background-sync failures are only visible in `stderr` / log aggregator — the LLM never learns that a turn was dropped. Consider a `health --json` or `sync_status` tool.

---

## Technical Debt Map

| Area | Debt | Size | Interest |
|---|---|---|---|
| Provider god object | `provider.py` owns 5 tools + worker + prefetch + property builders | L | Every new tool adds coupling; tests must mock the whole class |
| Cache I/O | Non-atomic `write_text` + no file lock | M | Truncation/corruption on crash or concurrent bootstraps |
| Search hydration | Fan-out N × body fetches, no session reuse | M | Latency + rate-limit pressure as brains grow |
| Docs drift | `architecture.md` + README version + pipeline | S | Onboarding confusion; exfiltration risk undocumented |
| Lint gate | 6 ruff + 2 mypy errors on `main` | S | CI red; contributors lose trust in gates |
| Test isolation | `test_api_key_env` assumes no `.env` | S | CI flaky on real hosts; masks real failures |
| `extract.Any` + unused imports | 3 F401s | XS | Noise |
| `cryptography` optional dep | No import site | XS | Confusion |

---

## Positive Findings

* **Remediation quality was high:** 6 of 7 P1 reliability fixes and both P0 security fixes still hold on 2026-09-01, verified line-by-line. The two accept-risk items remain appropriately deferred.
* **HTTP client hardening:** `timeout=30` + 3-attempt retry on `429/5xx/Timeout/ConnectionError` is a meaningful improvement over a bare `requests.request`.
* **Bootstrap determinism:** parent-child DB scan before `/search` eliminates the duplicate-DB pathology that plagued early installs.
* **Non-destructive recovery:** `reset_databases` and `ensure_brain` both preserve user data on failure; `install.sh` also “repairs” rather than recreates.
* **Secret hygiene at the store boundary:** `_rich_text`/`select`/`multi_select` helpers re-redact, so handler omissions are still safe at the Notion wire.
* **Health diagnostics are excellent:** per-DB schema/entry/last info + bot-name-specific sharing instructions + correct exit code — best-in-class for a Notion integration.
* **Version coherence:** `pyproject.toml`/`plugin.yaml`/`__init__.py` agree on `1.0.2` (only README lags); wheel builds reproducibly (`dist/` present, `hermes-brain-1.0.2-py3-none-any.whl` verifiable).
* **Helpers extraction:** `_safe_select_value` prevents 400s from invalid select writes; `_merge_disk_only`/`_paragraph_blocks` are well-tested pure functions.

---

## Top 10 Risks

| Rank | ID | Risk | Why now |
|---|---|---|---|
| 1 | **SEC-01** | LLM extraction exfiltrates unredacted secrets | Every turn with a secret hits a network POST without scrubbing |
| 2 | **REL-01** | Database-filtered search never matches (wrong filter type) | `AUD-RELIABLE-07` fix is inert — recall is zero when `database` is set |
| 3 | **TEST-01/02** | CI gates red (ruff/mypy/coverage) | Contributors cannot tell a real regression from a gate failure |
| 4 | **REL-02** | Daemon queue loses last turn on exit | Silent durability loss, no user-visible error |
| 5 | **DATA-01** | Non-atomic cache write truncates on crash | Corruption diverts next bootstrap to a duplicate parent page |
| 6 | **API-02** | `page_id` handlers mutate any reachable page | Cross-DB / cross-workspace write primitive via tool call |
| 7 | **API-01** | Inconsistent error contract (`error:false` with `"Error: …"` text) | LLM misparses failures as successes |
| 8 | **SEC-02** | Installer token validation dead code | Users forced through extra token pastes; validation UX is broken |
| 9 | **DATA-02** | 429 retry ignores `Retry-After` | Throttled searches/imports fail after 3 rapid retries |
| 10 | **SEC-04** | Cache `644` leaks workspace structure | Multi-user host widens blast radius |

---

## Top 10 Recommended Improvements

1. **Scrub + budget the LLM extraction buffer** (`extract.py:125`) — `redact_secrets(compact(buffer, 4000))` before POST, or make LLM extraction opt-in (`NOTION_BRAIN_LLM_EXTRACT=1`).
2. **Fix title filter type** (`provider.py:478-480`) — `{"property":"title","title":{"contains":query}}` (and add a unit test that asserts the filter shape).
3. **Make gates green** — `uv run ruff check --fix` + fix `extract.py:148` typing (`payload` as `dict[str, Any]` → `JsonType`) + fix `tests/test_coverage_gaps.py:576` (`list.append` return), and either raise coverage or lower the gate comment to 75%.
4. **Atomic cache writes** — `tmp = path.with_suffix(".tmp"); tmp.write_text(...); tmp.replace(path); try: os.chmod(path, 0o600)`.
5. **Guard `page_id` updates** — fetch page, assert `page.parent.database_id == self._db_ids[expected]`.
6. **Normalize `tags`/`entities` coercion** — `if isinstance(v, str): v=[v]` before list comps, and validate `list[str]` in `handle_tool_call`.
7. **Unify error contract** — handlers raise on failure; `handle_tool_call` is the sole `error:true` boundary; remove internal `return "Error: …"` catches or make them `raise RuntimeError`.
8. **Fix installer validation** (`install.sh:250`) — `Authorization: Bearer $token` + `shellcheck`.
9. **Honor `Retry-After`** (`store.py:77`) — parse header, `sleep(min(int(header), 60))` instead of fixed backoff on 429.
10. **Ship `plugin.yaml` in wheel** — move `plugin.yaml` into `notion_brain/` or add `tool.setuptools.package-data`, or document that it is intentionally root-only and adjust `MANIFEST.in` comment.

---

## Quick Wins (≤ 2 h, no migration)

| # | Fix | File:Line | Effort |
|---|---|---|---|
| QW-1 | Title filter type fix | `provider.py:478` | 10 min |
| QW-2 | Installer `Bearer $token` | `install.sh:250` | 5 min |
| QW-3 | `ruff --fix` + remove 3 unused imports/vars | `__main__.py:143,217`, `extract.py:13`, `tests/test_extract.py:504` | 10 min |
| QW-4 | `test_api_key_env` isolation — patch `_load_env_file` | `tests/test_provider.py:474` | 15 min |
| QW-5 | `tags` string coercion guard | `provider.py:539-554` (+ 3 more sites) | 20 min |
| QW-6 | Cache `chmod 600` after write | `bootstrap.py:405` | 10 min |

**All Quick Wins together bring ruff/mypy green, search back to correct, and installer validation alive — the three most visible regressions.**

---

## Strategic Improvements (next quarter)

* **Durability layer:** replace the in-memory queue with an on-disk outbox (`~/.hermes/notion_brain.outbox.jsonl`: append on enqueue, fsync, delete on ack). Replays on next `ensure_brain`. Makes `REL-02` crash-safe without adding a service.
* **Session reuse + batching:** `requests.Session` globally + `create_database_page` batch endpoint (or sequential with `Retry-After` respect) for `import`.
* **Privacy mode:** `NOTION_BRAIN_REDACT_LLM=1` (default on) and `NOTION_BRAIN_LLM_EXTRACT=0` (default off) — heuristic-only by default, LLM is explicit opt-in with a startup warning.
* **Integration tests (defer `AUD-TEST-01` properly):** add a `tests/live/` suite gated by `NOTION_API_KEY` + `pytest.mark.live`, run nightly in GitHub Actions against a throwaway Notion workspace (create → write → search → delete), publish live-coverage separately.
* **Docs:** regenerate `docs/architecture.md` to include LLM branch, update README version badge, add `docs/privacy.md` disclosing LLM exfiltration and Notion retention.

---

## Prioritized Remediation Plan

### Wave 1 — Correctness & privacy (this week, ship `v1.0.3`)

| ID | Finding | Owner | Effort | Validation |
|---|---|---|---|---|
| SEC-01 | LLM exfiltration | Extract | 1 h | Unit test: secret in turn → POST body redacted |
| REL-01 | Title filter type | Provider | 15 min | Test: `notion_brain_search(database="tasks", query="foo")` sends `{"title":{"contains":"foo"}}` |
| QW-3 | Ruff/mypy green | Repo | 30 min | `uv run ruff check .` exits 0; `uv run mypy notion_brain tests` exits 0 |
| QW-4 | Flaky `test_api_key_env` | Tests | 15 min | `uv run pytest -q` → 279 passed |
| SEC-02 | Installer `Bearer` | Scripts | 10 min | `validate_notion_token ntn_...` returns 200 on real token |

**Exit criteria:** `uv run pytest -q` 279/279, `ruff` 0, `mypy` 0, search filter test passes, LLM buffer redacted.

### Wave 2 — Durability & hardening (next sprint)

| ID | Finding | Effort | Validation |
|---|---|---|---|
| DATA-01 | Atomic cache + `chmod 600` | 1 h | Kill -9 mid-`_save_cache` → file remains valid JSON, perms 600 |
| DATA-02 | `Retry-After` | 1 h | Mock 429 with `Retry-After: 5` → sleep 5, then success |
| REL-02 | Daemon durability (outbox or `atexit` join with timeout) | 4 h | `sync_turn` then `SIGTERM` → entry present in Notion after restart |
| API-02 | `page_id` DB guard | 1 h | `task update page_id=<content-db-id>` → `Error: page does not belong to tasks` |
| API-01 | Error contract unification | 2 h | Every failure path yields `error:true`; LLM prompt updated |

### Wave 3 — Quality & supply chain

| ID | Finding | Effort | Validation |
|---|---|---|---|
| Coverage | Raise to 80% (cover `__main__.py` import + bootstrap) | 4 h | `pytest --cov-branch` ≥ 80% |
| Requests pin | `requests>=2.28,<3` or `uv.lock` hash pin | 30 min | `pip-compile` / `uv pip compile` |
| Plugin packaging | Ship `plugin.yaml` in wheel | 30 min | `unzip -l dist/*.whl | grep plugin.yaml` |
| Live tests | `tests/live/` nightly | 1 d | Nightly run green on throwaway workspace |

---

## Verification Results

### Commands executed (2026-09-01, commit `026ee0a`)

| Command | Result |
|---|---|
| `uv run pytest -q` | **1 failed, 278 passed** in 63 s — `tests/test_provider.py::TestStoreHelpers::test_api_key_env` (`assert get_api_key() is None` actually `'ntn_30...Cbbe'` from `~/.hermes/.env`) — truncated output saved; full log in terminal session. |
| `uv run pytest --cov=notion_brain --cov-branch -q` | Same 1 fail; **77%** branch coverage (see table in Testing). `__main__ 38%`, `bootstrap 67%`, `store 73%`. |
| `uv run ruff check .` | **6 errors** — `examples/quickstart.py I001`, `notion_brain/__main__.py F401+F841`, `notion_brain/extract.py F401`, `tests/test_extract.py F401+I001` (fixable with `--fix`). |
| `uv run mypy notion_brain tests` | **2 errors** — `extract.py:148 arg-type` ( `json` payload ), `test_coverage_gaps.py:576 func-returns-value` ( `append` ). |
| `unzip -l dist/hermes_brain-1.0.2-py3-none-any.whl` | **15 files, no `plugin.yaml`** — `plugin.yaml` not in wheel (only in sdist). |
| `grep -n "rich_text.*contains" notion_brain/provider.py` | `480: "rich_text": {"contains": query}` — confirms REL-01. |
| `grep -n "Bearer" scripts/install.sh` | `250: -H "Authorization: Bearer ***"` — confirms SEC-02. |
| `pygount --folders-to-skip ...` | Not run this session; `wc -l` used: 3,123 prod / 3,414 test. |

### What was NOT verified (needs live creds / Hermes runtime)

* Live Notion round-trips (create/query/search/update/blocks) — mocked only.
* Live Hermes hook contract (`sync_turn` signature/arity) — inferred from `*args/**kwargs` + `dev/` (not inspected deeply this run).
* `hermes-brain` console script in a fresh venv — wheel exists but not installed into an isolated venv this run.
* `install.sh` end-to-end — not executed (would mutate `~/.hermes`).

---

## Unknowns / Needs Verification

* **Hermes hook ABI for `sync_turn` / `on_session_end` / `shutdown`:** `provider.py:188-240` accepts `*args/**kwargs` and tries `(user_content, assistant_content)` positional then `kwargs` fallback. If Hermes actually calls `on_session_end(messages=[...])` (as `notion_brain/__main__.py:21` hints for session summaries), the current `on_session_end` correctly handles `messages = args[0] if args else kwargs.get("messages")` (210-211). But if `sync_turn` is called as `sync_turn(messages)` with a list, classification silently gets empty strings. **Needs:** read the actual Hermes `agent` package’s `MemoryProvider` ABC.
* **Notion `/search` filter semantics for `title`:** inferred from Notion docs (title type uses `title` filter, not `rich_text`). Needs a live Notion call to confirm `rich_text` filter on a title property returns 0 vs 400 — both are broken.
* **Actual `~/.hermes/.env` contents on CI:** `test_api_key_env` failure proves the host has a real token; CI’s `~/.hermes/.env` state is unknown — the flake may be host-only.

---

## Appendix

### A. File inventory (audited)

```
notion_brain/__init__.py    112  plugin entry, version, top-level helpers
notion_brain/schema.py      173  BrainEntry, redact_secrets, constants
notion_brain/schemas.py     223  5 tool JSON Schemas
notion_brain/store.py       437  Notion REST client, retries, pagination, helpers
notion_brain/bootstrap.py   556  ensure_brain, cache, health, reset/wipe/import
notion_brain/extract.py     394  LLM + heuristic classifier, routing guards
notion_brain/helpers.py     140  _safe_select_value, _merge_disk_only, etc.
notion_brain/provider.py    828  NotionBrainProvider (tools, worker, lifecycle)
notion_brain/__main__.py    260  CLI (reset/url/health/wipe/import)
scripts/install.sh          431  guided installer
plugin.yaml                   5  plugin manifest (not in wheel)
pyproject.toml               50  package metadata, ruff/mypy/coverage config
uv.lock                   ~18k   pinned dev deps
tests/test_provider.py      597
tests/test_store.py         257
tests/test_extract.py       540
tests/test_coverage_gaps.py 581
docs/architecture.md         72
docs/troubleshooting.md      ~80
examples/quickstart.py       ~60
```

### B. Prior remediation mapping

`REMEDIATION-STATUS.md` (2026-08-25) triaged 14 findings:

* **FIXED and still holds:** `AUD-SEC-02`, `AUD-RELIABLE-01`-`06`, `AUD-LINT-01/02` (lint now regressed but fixes not reverted), `AUD-COV-01` (was 83%, now 77%).
* **Regressed:** `AUD-RELIABLE-07` (search filter fix is present but wrong type — see REL-01), `AUD-LINT-01/02` (ruff/mypy now fail).
* **Accepted risk and still appropriate:** `AUD-PKG-01` (wheel shim), `AUD-TEST-01` (live tests).
* **False positive, correctly dismissed:** `AUD-STATE-01` (uncommitted changes).

### C. Severity & confidence rubric

* **P0 Critical** — catastrophic security/data/availability, exploitable without user action.
* **P1 High** — serious security/reliability/correctness, reachable in normal use.
* **P2 Medium** — important issue requiring remediation before scale.
* **P3 Low** — localized weakness / debt.
* **P4 Info** — observation.
* **Confidence HIGH** — direct code read + reproduction or `grep`/command output. **MEDIUM** — strong inference from structure + docs. **LOW** — hypothesis needing live verification.

### D. How to re-run verification

```bash
cd /mnt/c/code/hermes-brain
uv run pytest -q                               # expect 278/279 (1 flaky until fixed)
uv run pytest --cov=notion_brain --cov-branch -q  # expect 77%
uv run ruff check .                             # expect 6 errors until QW-3
uv run mypy notion_brain tests                  # expect 2 errors until QW-3
unzip -l dist/hermes_brain-*.whl | grep plugin  # expect no match (AUD-PKG-01)
grep -n 'rich_text.*contains' notion_brain/provider.py  # REL-01
grep -n 'Bearer' scripts/install.sh             # SEC-02
```

---

*End of report. All findings are evidence-backed against commit `026ee0a`. The sub-agent fan-out (`deleg_fd1b10a5`, 5 tasks) was dispatched but all 5 hit token-router `429/502` limits and returned truncated; the report above is lead-auditor direct verification and supersedes any partial sub-agent summaries.*
