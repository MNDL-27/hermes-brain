---
phase: quick-260927-p1q
plan: 01
subsystem: test-infrastructure
status: complete
tags: [testing, offline-ci, security, redaction, pytest]
requires: []
provides:
  - autouse socket-deny + env-neutralize test fixture (tests/conftest.py)
  - registered/deselected `network` pytest marker
affects:
  - tests/conftest.py
  - tests/test_provider.py
  - tests/test_packaging.py
  - pyproject.toml
tech-stack:
  added: []
  patterns:
    - "stdlib socket + monkeypatch autouse fixture (no pytest-socket dependency)"
    - "network-marked tests deselected by default via addopts '-m not network'"
key-files:
  created: []
  modified:
    - tests/conftest.py
    - tests/test_provider.py
    - tests/test_packaging.py
    - pyproject.toml
decisions:
  - "Deny network at socket.connect/connect_ex/getaddrinfo (fail before DNS) rather than add pytest-socket — keeps zero new deps per CLAUDE.md dependency-boundary constraint."
  - "Neutralize the init-time background refresh in test_initialize_error_redacts_secrets by patching provider.update_cache.refresh (the symbol the daemon worker runs), preserving the real bootstrap-error redaction assertion."
metrics:
  duration: ~4 min
  completed: 2026-09-27
actuals:
  tokens: 6500
  tasks: 3
  commits: 3
commits: 3
plan_head_before: 1039fc1d779ec2c7d1f43fdf08df8c9fc562d115
plan_head_after: 80774ea273e822bc6179ccb8baccb5b09daf74e8
requirements: [CI-OFFLINE-01]
---

# Quick 260927-p1q: Make the hermes-brain unit test suite hermetic offline Summary

Autouse socket-deny + NOTION_API_KEY/HERMES_HOME neutralization fixture, a corrected
`store.query_database` mock target, a neutralized init-time update refresh, and a
registered/deselected `network` marker — the full unit suite now runs offline with no
hang and no live-credential dependency, satisfying the CLAUDE.md CI-reliability constraint.

## What Was Built

- Task 1 (tracer): `tests/conftest.py` gains a function-scoped `autouse` fixture that
  (1) `delenv`'s `NOTION_API_KEY`/`NOTION_TOKEN` and points `HERMES_HOME` at a per-test
  tmp dir so `store._headers()` fast-fails with "NOTION_API_KEY not set" regardless of the
  host's `~/.hermes/.env`, and (2) patches `socket.socket.connect`, `connect_ex`, and
  `socket.getaddrinfo` to raise a clearly named `_OfflineNetworkAttempt` — any unmocked
  outbound call (Notion requests, daemon-worker GitHub urlopen) now fails fast and loud
  instead of blocking ~10 min on `timeout=30` x3 retries. Existing dataclass stubs and
  `pytest_configure` preserved. stdlib only, no new dependency.
- Task 2: `test_search_dispatches` now patches `notion_brain.store.query_database` (what
  `_tool_search` actually invokes) instead of the never-called `store.search_entries`.
  `test_initialize_error_redacts_secrets` now patches `notion_brain.provider.update_cache.refresh`
  to a no-op so the init-time background refresh performs no real network, while still
  exercising the real `initialize()` bootstrap-error path and its redaction assertion.
- Task 3: registered the `network` marker in `pyproject.toml` (required under
  `--strict-markers`) and appended `-m` / `not network` to `addopts` so network tests are
  deselected by default; marked only `test_offline_build_and_twine_check` with
  `@pytest.mark.network` (PEP517 build isolation fetches from PyPI) and documented the
  `uv run pytest -m network` opt-in in the module docstring. The other 3 packaging tests
  stay in the default offline run.

## Verification

All commands run with `--extra dev` (pytest/ruff live in the dev optional-dependencies group);
this machine has no network egress, which is the exact condition the fix must survive.

Per-task `<verify>` (all passed, no hang):
- Task 1: `pytest tests/test_coverage_gaps.py tests/regressions/test_migration_privacy_blockers.py` → 70 passed in 3.51s.
- Task 2: `pytest tests/test_provider.py -k "test_search_dispatches or test_initialize_error_redacts_secrets"` → 2 passed, 44 deselected in 1.35s.
- Task 3: collection checks → default run deselects the build test; `-m network` collects exactly it (TASK3_VERIFY_PASS). Offline packaging run → 3 passed, 1 deselected.

Phase-level offline gate:
- `timeout 120 uv run pytest tests/ -p no:cacheprovider -m "not network"` → **352 passed, 1 deselected in 8.76s** (elapsed 13s wall), exit 0, no hang.
- `timeout 90 uv run pytest tests/test_update_cache.py tests/characterization -p no:cacheprovider` → **72 passed in 2.87s** (elapsed 5s), exit 0 — Phase 6's already-offline suites unbroken.

The `-m network` build test was NOT run here (needs real network by design).

Ruff (`uv run --extra dev ruff check`) passed on every touched file; pre-commit hooks
(ruff format, ruff, mypy) passed on all 3 commits.

## Deviations from Plan

None — plan executed exactly as written. One environment note (not a code deviation):
pytest and ruff are declared in the `dev` optional-dependency group, so all invocations
used `uv run --extra dev ...`; the commands are otherwise identical to the plan's.

## Threat Model Coverage

- T-P1Q-01 (info disclosure via live NOTION_API_KEY): mitigated — env neutralization +
  socket-deny (Task 1).
- T-P1Q-02 (DoS hang on blocked egress): mitigated — socket-deny raises immediately;
  hard-timeout verify wrappers all completed well under budget (Tasks 1-3).
- T-P1Q-SC (package-manager install tampering): N/A — no install task; stdlib only, zero
  new dependency.

## Known Stubs

None.

## Self-Check: PASSED

- tests/conftest.py — FOUND
- tests/test_provider.py — FOUND
- tests/test_packaging.py — FOUND
- pyproject.toml — FOUND
- Commit 06fcec8 — FOUND
- Commit a32dddc — FOUND
- Commit 80774ea — FOUND
