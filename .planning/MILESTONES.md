# Milestones

## v1.0 Release Polish (Shipped: 2026-09-21)

**Phases completed:** 3 phases, 3 plans, 10 requirements

**Key accomplishments:**

- Offline unit test infrastructure for `notion_brain/config_schema.py` — 5 tests via `tests/conftest.py` host stubs, 100% statement + branch coverage, imports cleanly without host Hermes (SCHEMA-01/02/03, GitHub #51)
- Pre-commit quality gates mirroring CI `quality-debt` job — ruff format/lint (v0.16.0), mypy (v2.3.0), file sanitizers; 7/7 hooks pass, `pre-commit>=4.1.0` in dev extras (HOOK-01/02/03/04, GitHub #52)
- Darwin platform detection in `scripts/install.sh` — Step 0 guard prints README Quickstart Step 2 manual setup and exits 0 before root/distro checks; Linux apt/dnf/yum/pacman paths unchanged; 2 tests with stubbed `uname` (PLAT-01/02/03, GitHub #53)
- Test suite grew 301 → 303 passing, fully offline (CI reliability constraint preserved)

**Closeout type:** override_closeout (formal per-phase VERIFICATION.md reports absent; milestone audit `.planning/milestones/v1.0-MILESTONE-AUDIT.md` verified code-level satisfaction of 8/10 requirements with HOOK-02 wording divergence and HOOK-03 specifier drift)

**Known verification overrides:** 0 newly acknowledged, 0 carried forward

**Known gaps (accepted at closeout):**

- HOOK-02: mypy hook implemented as `repo: local` + `uv run --no-sync mypy` instead of `mirrors-mypy v2.3.0` (functionally equivalent, reuses project venv)
- HOOK-03: `pyproject.toml` shipped `pre-commit>=4.0.0`; corrected to `>=4.1.0` at closeout (uv.lock resolves 4.6.2)
- Phase 1 `VALIDATION.md` remains `status: draft` (Nyquist reconciliation never ran); Phases 2-3 have no VALIDATION.md

**Git range:** `828f240` feat(test) → `23932c1` feat(install) (42 files, +1551/-596)

---

## v1.1 Distribution & Updates (Shipped: 2026-10-07)

**Phases completed:** 3 phases, 4 plans, 15 requirements (DIST-01..03, META-01..02, UPD-01..05, CHK-01..05)

**Key accomplishments:**

- **Modern packaging (Phase 4, META-01/02)** — `pyproject.toml` migrated to PEP 639 SPDX `license = "MIT"` + `license-files`; build-system floor raised to `setuptools>=77.0.3`; offline `tests/test_packaging.py` (4 tests) asserts metadata conformity, version sync, and clean zero-deprecation builds on Python 3.11/3.12/3.13.
- **Tokenless OIDC publishing (Phase 4, DIST-01/02/03)** — `.github/workflows/publish.yml` is a six-job gated OIDC release workflow (`test`/`lint` → `build` → `publish` → `release` → `smoke-test`) with `environment: pypi` + job-scoped `id-token: write`. Zero static PyPI tokens in CI; `docs/RELEASES.md` covers automated release, one-time Trusted Publisher setup, emergency twine fallback, and recovery.
- **CLI update drift detection (Phase 5, UPD-01..05)** — new `notion_brain/update.py` module with integer-tuple SemVer (pre-release ranking), per-mode upgrade command builder (uv / pip venv / pip user / git clone), `--check` and `--json` flags; 26 offline tests in `tests/test_update.py` + 8 characterization tests, including a behavioral no-mutation guard.
- **Cached non-blocking auto-update check (Phase 6, CHK-01..05)** — new `notion_brain/update_cache.py` (atomic tempfile + `os.replace` + `0o600` + `fsync`); provider `initialize()` reads cache synchronously before `bootstrap.ensure_brain()` (zero network on startup) and dispatches TTL-expired refresh onto the existing `notion-brain-sync-worker` queue; `health_report()` reads cache. 20 offline tests in `tests/test_update_cache.py`.
- **Test suite** grew 303 → 361 passing, fully offline; ruff + mypy clean across all 32 source files.

**Closeout type:** verified_closeout (all 3 phases have formal VERIFICATION.md reports; 5/5 + 5/5 + 10/10 must-haves passed across phases 5/6/4 respectively)

**Known verification overrides:** 0 newly acknowledged, 0 carried forward

**Known gaps (accepted at closeout):**

- Pre-existing test-suite hangs in `test_coverage_gaps`, `test_migration_privacy_blockers`, `test_provider` — unrelated to v1.1 scope; recorded as TEST-HANGS in PROJECT.md Active for next milestone.
- One-time manual PyPI Trusted Publisher registration (owner + repo + `publish.yml` + environment `pypi`) must be done in the maintainer runbook before the first `v*` tag push — also recorded as a STATE.md pending todo.

**Git range:** `9be1f77` docs: start milestone v1.1 → `bed0ee2` chore(state): sync STATE.md after Phase 06 re-verification (25 commits, 12 source files, +1522/-121 in scope)

---
