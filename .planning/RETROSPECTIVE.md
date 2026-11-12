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

## Milestone: v1.1 — Distribution & Updates

**Shipped:** 2026-10-07
**Phases:** 3 | **Plans:** 4 | **Sessions:** ~3 | **Requirements:** 15/15 complete

### What Was Built
- PEP 639 SPDX license metadata + setuptools>=77.0.3 floor, with offline packaging tests asserting zero-deprecation builds on Python 3.11/3.12/3.13
- Tag-triggered OIDC PyPI publish workflow with `environment: pypi` + `id-token: write` (tokenless) and a four-section `docs/RELEASES.md` maintainer runbook covering automated release, one-time TP setup, manual twine fallback, and recovery
- `notion_brain update` CLI subcommand with integer-tuple SemVer, per-mode upgrade commands (uv / pip venv / pip user / git clone), `--check` / `--json` flags, and a no-mutation guarantee
- `$HERMES_HOME/.update_cache.json` with atomic writes (`os.replace`, `0o600`, `fsync`), synchronous <1ms startup read, background TTL refresh on the existing `notion-brain-sync-worker` thread, and `health_report()` reading from cache

### What Worked
- Re-verification pattern caught digest staleness after Phase 06's commit a0c7390 modified shared source — re-ran Phase 05/06 verifications, no regressions surfaced.
- Code review surfaced a real bug (WR-01: `refresh()` timeout default off by 0.5s) and a design guard (reworded docstring to match the actual ~2.5s wall-clock check, not a "3.0s inside urlopen" story).
- Choosing to drop legacy mutating helpers (`_git_pull_and_install`, `_checkout_tag_and_install`, `_reinstall`) and rewriting the characterization test (`test_update_command_detects_drift_without_mutating`) made the no-mutation guarantee load-bearing — four subprocess-guard tests now prevent regression.
- Strict test seeding discipline (only `parent_page_id` in `notion_brain.json` fixture for `test_health_report_*`) made those tests *stricter* than originally planned — any urlopen during the test is now a genuine violation.

### What Was Inefficient
- Pre-existing `publish.yml` had drifted from the plan contract (`secrets.PYPI_API_TOKEN`, no guards) — caught at Plan 02 execution, but it cost a full rewrite before any new verification could happen.
- `test_refresh_redacts_secrets_in_error_log` initially used a fake `pypi-AgEI…` token format the `_SECRET_PATTERNS` redactor doesn't cover — wasted one test run before switching to an AWS `AKIA…` key to validate the redaction *boundary* rather than a specific token family.
- `test_health_report_*` initially hung because the fixture over-seeded `notion_brain.json` with `db_memory`, pushing the path into unstubbed `store.get_database` real-network territory — fixed by trimming the fixture to only `parent_page_id`.
- The three pre-existing test hangs (`test_coverage_gaps`, `test_migration_privacy_blockers`, `test_provider`) are unrelated to milestone scope but blocked the full-suite test run that the verification recipe wanted to invoke — recorded as debt for next milestone.

### Patterns Established
- "Sync-read cached state, async-refresh on existing worker thread" — the universal pattern for "I need fresh data but I also need to start fast" with a hard constraint of zero network on the startup path.
- `redact_secrets` + bare `except Exception` boundary in any background-thread function that touches the network — workers never crash, secrets never reach logs.
- Wall-clock timeout check *after* the call when the upstream signature is frozen by the plan — preserves the contract while bounding exposure.
- Atomic write via tempfile + `os.replace` + explicit `fsync` + restrictive `0o600` mode is the right shape for any small JSON file that needs to survive crashes and not leak permissions.
- Test-seeding minimalism: only seed what the path under test needs; the strictness of the test grows with how much the seed could have inadvertently triggered.

### Key Lessons
1. Always re-verify downstream phases after any commit that touches shared source (covered_digest staleness is the normal failure mode at phase boundaries).
2. Code review with a real WR-NN ID trail (WR-01 → commit → re-verify) closes the loop and is auditable later.
3. Detect + instruct (no `pip install`/`git pull` in `update`) is the only safe shape for in-process self-update — and the guarantee needs a *behavioral* test, not just a code-grep.
4. Reuse the existing sync worker thread (don't spawn a new one) — keeps the runtime threading model unchanged and the failure domain identical.
5. When the redactor covers a known family of secrets (AWS `AKIA…`), test the *boundary* — feed that family and assert the redacted form — rather than the specific token shape the original test imagined.

### Cost Observations
- Model mix: ~85% sonnet, ~15% haiku (heavy on planning/verification reasoning)
- Sessions: ~3 (one per phase, plus one re-verification sweep)
- Notable: 58 new tests across 3 test files, all offline, all <2s wall-clock per file — fast feedback loop preserved.

---

## Milestone: v1.3 — Brain Architecture & Freemium Foundation

**Shipped:** 2026-11-13
**Phases:** 3 | **Plans:** 3

### What Was Built
- Read-through SQLite cache with offline cold prefetch and a two-lane 400/400 injection budget (Phase 9).
- Event-driven supersession with background subject-key inference and retained history (Phase 10).
- StorageAdapter protocol, entitlement-gated selection and an Obsidian vault scaffold (Phase 11).

### What Worked
- Verification-driven gap plans closed each audited requirement without reopening the broader phase.
- Per-concern failure isolation in cache, graph and certification paths survived later changes.
- Targeted evidence re-runs before each digest refresh caught real staleness at phase boundaries.

### What Was Inefficient
- Verification digests went stale repeatedly when later phases touched shared files (`provider.py`, `brain_cache.py`); each close needed a refresh.
- Some original phase artifacts were missing, requiring retrospective reconstruction from commits and tests.
- The ROADMAP/REQUIREMENTS files covered multiple milestones, complicating archival.

### Patterns Established
- Refresh `covered_files`/`covered_digest` after any shared-source change.
- Accepted-state success boundaries with failure-isolated auxiliary bookkeeping.
- Explicitly document adapter write-path ceilings instead of claiming full abstraction.

### Key Lessons
1. Refresh verification digests at the end of a phase sequence, not only at each phase close.
2. Keep milestone-scoped ROADMAP/REQUIREMENTS files so archival does not strand downstream phases.
3. A passing suite is not closure evidence; phase summaries, verification and validation must exist.

### Cost Observations
- Model mix: not instrumented in this session
- Sessions: one continuous closeout session across Phases 10–15
- Notable: 10 requirements verified; full suite grew 532 → 582; 181 cross-phase tests.

---

## Milestone: v1.4 — Semantic Brain Layer

**Shipped:** 2026-11-13
**Phases:** 4 | **Plans:** 4

### What Was Built
- Provider-neutral semantic catalog with deterministic queries and Notion/Obsidian locator resolution (Phase 12).
- User-gated certification with exact per-call confirmation and failure-isolated supersession (Phase 13).
- Cache-safe provenance, explicit supersession edges and bounded graph traversal (Phase 14).
- Coverage-gated retrieval plus a bounded contradiction notice (Phase 15).

### What Worked
- Closing already-wired behavior with verification-first checks avoided unnecessary rewrites.
- Focused gap plans (adapter routing, ref recall, failure isolation, provenance continuity, notice bound) stayed small and auditable.
- Independent probes caught real gaps the test suite did not cover, notably Obsidian ref-driven selection.

### What Was Inefficient
- Verification digests went stale repeatedly as later phases touched shared files; the final audit required a refresh sweep.
- Original Phase 12/13/14 artifacts were retrofitted around existing implementation, adding documentation overhead.
- Multi-milestone ROADMAP/REQUIREMENTS files made v1.3 and v1.4 archival interact.

### Patterns Established
- Catalog refs drive deterministic row selection before fuzzy matching, including premium vault paths.
- Accepted-state success boundaries with isolated auxiliary bookkeeping.
- Explicit caps with overflow counts for rendered conflict notices.

### Key Lessons
1. Run the verification-digest refresh once at the end of the phase sequence, not only at each phase close.
2. Keep one milestone per ROADMAP/REQUIREMENTS file so archival does not strand downstream phases.
3. Treat "already implemented" as a hypothesis; verify it with probes and failure injection before closing.

### Cost Observations
- Model mix: not instrumented in this session
- Sessions: one continuous audit/closeout session
- Notable: 11 requirements verified; 12 new closure regressions; full suite 582 passed.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 3 | 3 | Introduced automated pre-commit gates, offline test isolation, and Darwin installer guard |
| v1.1 | ~3 | 3 | Re-verification discipline, code-review-driven fixes, and 58 new offline tests across packaging/update/cache |
| v1.2 | ~2 | 2 | Retrospective closure, hermetic suite, opt-in pre-push gate and weekly hook maintenance |
| v1.3 | ~2 | 3 | Cache/supersession foundation plus adapter abstraction and entitlement gate |
| v1.4 | ~1 | 4 | Semantic catalog, certification, provenance continuity and bounded answerability |

### Cumulative Quality

| Milestone | Tests | New Tests | Coverage | Zero-Dep Additions |
|-----------|-------|-----------|----------|-------------------|
| v1.0 | 303 | 8 | 100% on config_schema.py | 2 test suites, 0 runtime dependencies |
| v1.1 | 361 | 58 | (per-test) | 0 new runtime deps — all v1.1 work uses stdlib + existing requests |
| v1.2 | 451 | 90 | (per-test) | 0 new runtime deps; hermetic socket denial |
| v1.3 | 582 | 131 | (per-test) | 0 new runtime deps; SQLite already stdlib |
| v1.4 | 582 | 12 | (per-test) | 0 new runtime deps; v1.4 code was present during the v1.3 baseline |

*The v1.3 and v1.4 tree-wide counts overlap because v1.4 implementation was present before v1.3 closed; the 12 figure is the closure-regression delta during the v1.4 phase sequence.*

### Top Lessons (Verified Across Milestones)

1. Host isolation via `conftest.py` keeps plugin tests 100% runnable offline without parent agent frameworks.
2. Local pre-commit parity with CI prevents broken commits before pushing.
3. Detect + instruct, never auto-mutate, for any "self-update" surface in a running process — preserves bytecode integrity and operator trust.
4. Stale-while-revalidate cache pattern (sync read, async refresh on existing worker) is the right shape for "I need fresh data but I also need to start fast" — zero network on the startup path.
5. Re-run verification after any commit that touches shared source — covered_digest staleness is a normal artifact of moving phase boundaries.
