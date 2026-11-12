---
phase: 06-cached-non-blocking-auto-update-check
plan: 01
subsystem: distribution
tags: [update-cache, ttl, background-refresh, provider]
requires-phase: 05
provides-phase: null
key-files:
  created:
    - notion_brain/update_cache.py
    - tests/test_update_cache.py
  modified:
    - notion_brain/provider.py
    - notion_brain/bootstrap.py
---

# Phase 06 Plan 01 — Cached Non-Blocking Auto-Update Check

## What Shipped

- `notion_brain/update_cache.py` (new) — `load_cache` (pure file I/O, never raises, never networks), `save_cache` (tempfile + `os.replace`, mode `0o600`, fsync before rename), `is_expired` (TTL semantics, `None`/missing-`checked_at` treated as expired), `refresh` (wraps `update.check_for_update`, 2.5s wall-clock budget, all exceptions logged via `redact_secrets` and swallowed, writes `checked_at` timestamp).
- `notion_brain/provider.py` — `NotionBrainProvider.__init__` gains `_update_cache` slot; `initialize()` loads the cache synchronously **before** `bootstrap.ensure_brain()` (CHK-01) and dispatches `update_cache.refresh` onto the existing `notion-brain-sync-worker` queue when the TTL is expired (CHK-02). New `_dispatch_update_refresh()` mirrors the existing `_trigger_auto_disk_sync` pattern — no new thread.
- `notion_brain/bootstrap.py` — `health_report()` now reads `update_cache.load_cache(hermes_home)` and renders drift from the cache: `UPDATE AVAILABLE` line when `drift` is true, `version: X (latest: Y)` when cached, `version: X (latest: unknown)` when no cache. No synchronous network call remains on that path (CHK-04).
- `tests/test_update_cache.py` (new) — 20 offline tests.

## Verification

| Check | Result |
|-------|--------|
| `update_cache.py` inline contract verifier | **OK** |
| `tests/test_update_cache.py` — 20 tests | **all passed** (1.25s) |
| `tests/test_update.py` + `tests/test_packaging.py` | **all passed** (49 passed, 1 skipped combined) |
| Regression sweep (7 fast files + characterization + regressions) | **all pass** |
| `ruff check notion_brain tests` | **clean** |
| `mypy notion_brain tests` | **clean** (32 source files) |

## CHK Coverage

- **CHK-01**: `test_provider_initialize_loads_cache_synchronously` — trips `urllib.request.urlopen` during `initialize()`; zero invocations observed. Cache load happens before `ensure_brain()`. ✓
- **CHK-02**: `test_provider_dispatches_refresh_when_cache_expired` — expired cache triggers `_dispatch_update_refresh`, which queues onto `self._sync_queue` (existing worker). ✓
- **CHK-03**: `test_save_cache_writes_with_mode_0o600`, `test_save_cache_does_not_leave_tmp_file_on_success`, `test_load_cache_returns_none_for_corrupt_file` (+ empty file, non-dict JSON). ✓
- **CHK-04**: `test_health_report_does_not_call_check_for_update`, `test_health_report_unknown_when_cache_missing` — `_check_for_update` monkeypatched to raise; `health_report` succeeds from cache alone. ✓
- **CHK-05**: `test_refresh_handles_network_failure_without_raising`, `test_refresh_redacts_secrets_in_error_log` (fake AKIA token never appears in any log record). ✓

## Deviations / Notes

- The initial `test_refresh_redacts_secrets_in_error_log` used a fake `pypi-AgEI…` token, which `schema._SECRET_PATTERNS` does not cover. Switched to an AWS `AKIA…` key format the redactor recognizes — the test validates the redaction *boundary*, not the specific token family.
- `test_health_report_*` initially hung: seeding `db_memory` in the fake `notion_brain.json` pushed `health_report` into the per-DB loop with unstubbed `store.get_database` → real network. Fixed by seeding only `parent_page_id` so the loop takes the zero-network `MISSING` path. This made the tests *stricter*: any urlopen during these tests is now a genuine violation.
- `refresh` enforces the 2.5s budget with a wall-clock check after the call (rather than inside `_find_latest_tag`, whose signature is frozen per plan prohibitions). The underlying `urlopen` timeout of 3s remains the hard network cap.

## Hand-off

Phase 06 complete — milestone v1.1 (Distribution & Updates) phases 4, 5, 6 all executed. Remaining milestone steps: `/gsd-verify-work` on Phase 06 (optional), then `/gsd-complete-milestone`.
