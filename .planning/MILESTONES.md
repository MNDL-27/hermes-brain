# Milestones

## v1.4 Semantic Brain Layer (Shipped: 2026-11-13)

**Phases completed:** 4 phases, 4 plans, 11 requirements (CAT-01..03, CERT-01..03, PROV-01..03, ANS-01/02)

**Key accomplishments:**

- **Deterministic semantic catalog (Phase 12, CAT-01..03)** — provider-neutral Terms, Entities, Relations and StorageRefs with atomic redacted persistence; `resolve_term`/`list_entities`/`get_relations` run without LLM inference; Notion page/database refs and premium Obsidian note refs drive selection.
- **User-gated certification (Phase 13, CERT-01..03)** — inferred by default, exact per-call confirmation is the only promotion path, certified facts rank first at equal recency, and certification bookkeeping isolates recoverable provenance/cache failures while failing closed on a rejected Truth write.
- **Provenance and relational recall (Phase 14, PROV-01..03)** — source agent/session and original created time survive the SQLite cache with conflict-safe backfill; prefetch and timeline expose the full block; supersession edges and bounded graph traversal drive related recall.
- **Answerability gate (Phase 15, ANS-01/02)** — deterministic coverage gates retrieval at zero coverage with approved uncertainty wording, and contradictions surface both structurally and as a bounded prefetch notice with an omitted-entry marker.

**Verification:** [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md) — passed, 21/21 requirements across Phases 9–15 (11/11 v1.4), 4/4 phases, Nyquist compliant. Full suite 582 passed, 1 deselected.

**Closeout type:** verified_closeout

**Known verification overrides:** 0 newly acknowledged, 0 carried forward

**Known gaps (accepted at closeout):**

- Obsidian section locators (`note.md#section`) are unsupported by design; note-level references are wired end to end.
- Merge to `main`, tag push/release and PyPI Trusted Publisher registration remain separate decisions.

**Git range:** `da6b1d4` feat(catalog) → `cf12265` fix(answerability) (implementation and gap closure)

---

## v1.3 Brain Architecture & Freemium Foundation (Shipped: 2026-11-13)

**Phases completed:** 3 phases, 3 plans, 10 requirements (RET-01..03, SUP-01..03, ADAPT-01..04)

**Key accomplishments:**

- **Retrieval correctness & local cache (Phase 9, RET-01..03)** — prefetch hydrates Content/Summary/body text; a SQLite read-through cache serves offline prefetch in ~1ms; every injection path is capped by the two-lane 400/400 budget.
- **Event-driven supersession (Phase 10, SUP-01..03)** — background and explicit writes share deterministic subject-key inference; changed same-title facts create a new page and supersede active inferred predecessors without losing history; timeline preserves fact chronology.
- **Storage adapters & freemium gate (Phase 11, ADAPT-01..04)** — provider-neutral `StorageAdapter` protocol, NotionAdapter routing for search/prefetch, entitlement-gated selection with graceful Notion fallback, and an Obsidian vault scaffold with markdown notes plus a SQLite index.

**Verification:** [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md) — passed, 10/10 requirements, 3/3 phases, Nyquist compliant. Full suite 582 passed, 1 deselected.

**Closeout type:** verified_closeout

**Known verification overrides:** 0 newly acknowledged, 0 carried forward

**Known gaps (accepted at closeout):**

- ADAPT-02 Memory write path remains on `store.*` because certification/provenance/graph semantics exceed the generic adapter protocol; provider recall routes through the adapter.
- Obsidian section locators are unsupported by design; note-level references are wired end to end.

**Git range:** `7b78b98` feat(brain) → `61a6247` feat(adapters) (implementation and gap closure)

---

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

## v1.2 Update UX & Tooling Polish (Shipped: 2026-11-07)

**Phases completed:** 2 phases, 4 plans, 5 requirements (UPD-06, UPD-07, TOOL-01, TOOL-02, TEST-HANGS)

**Key accomplishments:**

- **Commit-level update drift (Phase 7, UPD-06)** — `detect_git_drift` reads local `git rev-list` ahead/behind counts on `main` and falls back to the GitHub compare API; `check_for_update` reports `drift_type`, `behind_commits`, `ahead_commits`, and the cached payload persists them for offline banners.
- **Release-notes link (Phase 7, UPD-07)** — the banner and JSON payload carry `https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z` derived from the resolved tag; CLI exit codes distinguish commit-only drift (0) from version drift (2).
- **Hermetic, auditable test suite (Phase 8, TEST-HANGS)** — autouse socket/DNS denial, a registered `network` marker deselected by default, corrected provider mock targets, and a named single network test; the three former hang sources now finish in 0.26s.
- **Opt-in pre-push gate (Phase 8, TOOL-01)** — `scripts/pre-push` runs the CI-equivalent offline suite under a 300s timeout with a documented skip escape hatch; end-to-end run: 570 passed, 1 deselected.
- **Weekly hook maintenance (Phase 8, TOOL-02)** — `.github/workflows/pre-commit-autoupdate.yml` runs Mondays at 06:17 UTC, uses least-privilege permissions, and opens a human-merged PR when hook revs change.

**Closeout type:** retrospective_closeout (original Phase 7/8 SUMMARY and VERIFICATION artifacts were absent; reconstructed 2026-11-12 from committed behavior, tests and git history)

**Known verification overrides:** 0 newly acknowledged, 0 carried forward

**Known gaps (accepted at closeout):**

- The archived quick-task commits (`06fcec8`, `a32dddc`, `80774ea`, `56e467b`, `cddde1b`) are not reachable in this branch's history; their hermetic infrastructure landed here through `e4362f7`.
- Phase 5/6 retain no separate VALIDATION.md; their verification reports are the closure evidence.

**Git range:** `4c7afdf` feat(update): commit-level drift → `c42ac35` chore(v1.2): close out milestone

---
