---
phase: 08-developer-tooling-test-reliability
plan: "01"
subsystem: testing
tags: [pytest, hermetic-tests, offline, network-marker, codeql]
requires: []
provides:
  - Autouse hermetic offline fixture denying socket connect and DNS
  - `network` marker registered and deselected by default via addopts
  - Former hanging test files complete in well under a second
  - Auditable suite-count convention replacing the uncounted 361 claim
affects: [07-update-ux-commit-level-drift-release-notes-link, 08-developer-tooling-test-reliability]
tech-stack:
  added: []
  patterns: [hermetic offline unit suite, named network-marker deselection, fail-fast unmocked-egress detection]
key-files:
  created: []
  modified:
    - tests/conftest.py
    - pyproject.toml
    - tests/test_packaging.py
    - tests/test_provider.py
    - .github/workflows/publish.yml
key-decisions:
  - Deny `socket.connect`, `connect_ex` and `getaddrinfo` in an autouse fixture so an unmocked network call fails immediately instead of blocking on retries.
  - Register the `network` marker and deselect it with `-m "not network"` in `addopts`; name the one deselected build test explicitly.
  - Fix the two real mock defects in `test_provider.py` rather than weakening assertions.
  - Record the auditable suite count instead of retaining the uncounted "361 tests" claim.
requirements-completed: [TEST-HANGS]
coverage:
  - id: D1
    description: The offline unit suite is hermetic and the three former hangs finish promptly.
    requirement: TEST-HANGS
    verification:
      - kind: unit
        ref: tests/test_coverage_gaps.py tests/regressions/test_migration_privacy_blockers.py
        status: pass
      - kind: unit
        ref: tests/test_provider.py
        status: pass
    human_judgment: false
  - id: D2
    description: Network-marked tests are explicitly counted and deselected, not silently skipped.
    requirement: TEST-HANGS
    verification:
      - kind: unit
        ref: tests/test_packaging.py::test_offline_build_and_twine_check
        status: pass
      - kind: integration
        ref: full offline suite: 570 passed, 1 deselected
        status: pass
    human_judgment: false
status: complete
completed: 2026-11-07
---

# Phase 8 plan 01 summary

**Hermetic offline test suite with explicit network-marker deselection and the three former hangs cleared**

## Performance

- **Tasks:** 3
- **Files modified:** 8 (including planning artifacts)
- **Commits:** `e4362f7` in this branch; the original worktree commits `06fcec8`, `a32dddc`, `80774ea` are recorded in the archived quick-task summary but are not reachable in this history.

## Accomplishments

- `tests/conftest.py` gained an autouse `_hermetic_offline` fixture that neutralizes Notion credentials, points `HERMES_HOME` at a temp dir, and denies `socket.connect`, `socket.connect_ex` and `socket.getaddrinfo`. Unmocked egress now raises `_OfflineNetworkAttempt` immediately instead of blocking through retries.
- `pyproject.toml` registers the `network` marker and deselects it by default with `addopts = ["--strict-config", "--strict-markers", "-m", "not network"]`.
- `tests/test_packaging.py::test_offline_build_and_twine_check` is the single named network-marked test; it is deselected, never silently skipped.
- `tests/test_provider.py` mock targets were corrected (`store.query_database` for dispatch, `provider.update_cache.refresh` for init) so the tests exercise the real call sites.
- `.github/workflows/publish.yml` carries top-level `permissions: contents: read`.
- The original three hang sources complete quickly: `test_coverage_gaps.py` + `migration_privacy_blockers.py` run **70 passed in 0.26s**; `test_provider.py` is green in the 56-passing packaging/provider run.

## Files Created/Modified

- `tests/conftest.py` — network-deny fixture and offline error type.
- `pyproject.toml` — marker registration, strict config, default deselection.
- `tests/test_packaging.py` — named network marker on the build test.
- `tests/test_provider.py` — correct mock targets and init-refresh patch.
- `.github/workflows/publish.yml` — least-privilege permissions.
- Planning docs — auditable suite-count convention.

## Decisions Made

- A loud, immediate failure is preferable to a ten-minute hang when a test leaks egress.
- The 352+1 figure from the v1.2 closeout superseded the uncounted 361 claim; the current tree now reports 570 passed + 1 deselected because later phases added tests.
- No new test dependency was introduced; the suite relies on stdlib socket patching and pytest markers.

## Deviations from Plan

The plan described committing an uncommitted worktree state. In this branch the infrastructure landed through `e4362f7`; the archived quick-task commit hashes were not preserved as reachable objects. Behavior and tests match the plan.

## Issues Encountered

The pre-existing `test_provider.py` mocks targeted symbols the code did not call and the init path triggered a real update refresh; both were corrected rather than skipped.

## User Setup Required

None — the suite runs offline with no credentials.

## Next Phase Readiness

The pre-push hook in plan 08-02 inherits this hermetic contract.

## Self-Check

All checks passed: hermetic fixture present, network marker registered and deselected, former hang files complete in 0.26s, full suite green with only the named network test deselected, and commit `e4362f7` exists.
