# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Release Polish

**Shipped:** 2026-09-21
**Phases:** 3 | **Plans:** 3 | **Sessions:** 3

### What Was Built
- Offline unit test infrastructure for `notion_brain/config_schema.py` (5 tests, 100% coverage, conftest host stubs)
- Pre-commit quality gates (`.pre-commit-config.yaml` with 7 hooks mirroring CI `quality-debt` job)
- Darwin platform detection in `scripts/install.sh` with manual setup instructions and exit 0

### What Worked
- Test-first offline stubs in `conftest.py` eliminated external dependency on host Hermes runtime
- Leveraging project venv via `repo: local` for mypy hook avoided redundant wheel downloads and adhered to existing `mypy.ini`
- Stubbed `uname` command pattern in Python tests verified bash script branches without requiring multi-OS CI runner matrices

### What Was Inefficient
- Skipping formal `/gsd-verify-work` after each phase execution left phase verification status `missing` on all 3 phases
- Specifier discrepancy (`pre-commit>=4.0.0` vs `>=4.1.0`) was not caught until milestone audit

### Patterns Established
- Fake binary path injection via `PATH` prepend for unit testing shell scripts with platform-specific branches
- Host module fallback stubs inside `conftest.py` for offline-clean test execution

### Key Lessons
1. Always run `/gsd-verify-work` immediately after phase implementation rather than deferring verification to milestone close.
2. Cross-reference literal requirement specifiers against `pyproject.toml` and config files during plan execution.

### Cost Observations
- Model mix: 80% sonnet, 20% haiku
- Sessions: 3
- Notable: Fast local unit tests (303 tests in <2s) enabled continuous feedback without network latency

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 3 | 3 | Introduced automated pre-commit gates, offline test isolation, and Darwin installer guard |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 303 | 100% on config_schema.py | 2 test suites, 0 runtime dependencies |

### Top Lessons (Verified Across Milestones)

1. Host isolation via `conftest.py` keeps plugin tests 100% runnable offline without parent agent frameworks.
2. Local pre-commit parity with CI prevents broken commits before pushing.
