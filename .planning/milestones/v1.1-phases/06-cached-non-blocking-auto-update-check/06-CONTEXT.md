# Phase 06 — Cached Non-Blocking Auto-Update Check

## Goal
The agent provider learns about new releases in the background with zero startup cost and zero network on the startup path.

## Scope
- Add `$HERMES_HOME/.update_cache.json` TTL cache for update check results.
- Wire `NotionBrainProvider.initialize()` to load cache synchronously (<1ms, zero network) and dispatch a background refresh when TTL expires.
- Replace `bootstrap.health_report()`'s synchronous network call with a cache read.

## Requirements
- **CHK-01**: Provider init reads `$HERMES_HOME/.update_cache.json` synchronously in <1ms with zero network calls. Verified with and without a network connection.
- **CHK-02**: When TTL (default 24h, configurable) is expired, refresh dispatched to the existing `notion-brain-sync-worker` background queue; stale data served until refresh lands — no startup stall.
- **CHK-03**: Cache writes are atomic (tempfile + `os.replace`, mode `0o600`); `JSONDecodeError` guard so a corrupt or interrupted cache degrades silently and never crashes startup.
- **CHK-04**: `health_report()` reads cached update status instead of performing its own synchronous network update check.
- **CHK-05**: Refresh queries GitHub API unauthenticated with ~2.5s timeout, redacts secrets from error/log paths, offline-safe (no exception escapes when network is down).

## Current State
- `notion_brain/bootstrap.py:health_report()` calls `_check_for_update()` synchronously at line 669 — blocks on `urllib.request.urlopen` for up to 3s.
- `notion_brain/provider.py:NotionBrainProvider.__init__` (line 68) is synchronous and currently does no update check.
- `notion_brain/update.py:check_for_update` (Phase 05) is the natural refresh engine — already offline-safe, redacts secrets.
- `bootstrap._find_latest_tag()` uses 3s timeout (CHK-05 wants 2.5s — but Phase 05 wraps `_find_latest_tag`; we'll either parametrize the timeout or set a separate `urlopen` timeout inside the refresh wrapper).

## Files Touched
- **New**: `notion_brain/update_cache.py` — atomic cache read/write + TTL check + redacted refresh.
- **Modified**: `notion_brain/provider.py` — call cache loader in `__init__`; dispatch refresh on TTL expiry via `_sync_queue`.
- **Modified**: `notion_brain/bootstrap.py` — `health_report()` reads from cache, not network.
- **New**: `tests/test_update_cache.py` — offline tests for cache atomicity, TTL, JSONDecodeError tolerance, redacted refresh, no-mutation guarantee.

## Out of Scope
- Release-notes URL banner (UPD-07) — deferred; CHK cache only stores drift status.
- Commit-level drift (UPD-06) — not required by CHK-01..05.
- PyPI Trusted Publisher interaction with the cache — out of scope.

## Acceptance
- `python -m notion_brain update --check` reads cache and reflects last-refresh state
- Provider init completes in <50ms (no network)
- `health_report` exits without any HTTP call (verified by monkeypatching `urllib.request.urlopen` and asserting it was never called)
- Corrupt cache file does not crash startup
- Refresh never propagates an exception to the worker (only logs)
- All offline tests pass; ruff + mypy clean
