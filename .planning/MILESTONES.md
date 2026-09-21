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
