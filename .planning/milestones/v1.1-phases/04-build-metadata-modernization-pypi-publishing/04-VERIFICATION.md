---
phase: 04-build-metadata-modernization-pypi-publishing
verified: 2026-09-26T00:00:00Z
status: passed
score: 10/10 must-haves verified
covered_files:
  - .github/workflows/publish.yml
  - .planning/phases/04-build-metadata-modernization-pypi-publishing/04-01-PLAN.md
  - .planning/phases/04-build-metadata-modernization-pypi-publishing/04-01-SUMMARY.md
  - .planning/phases/04-build-metadata-modernization-pypi-publishing/04-02-PLAN.md
  - .planning/phases/04-build-metadata-modernization-pypi-publishing/04-02-SUMMARY.md
  - docs/RELEASES.md
  - notion_brain/__init__.py
  - pyproject.toml
  - tests/test_packaging.py
covered_digest: "v1:sha256:d674763a72c24329ab22bd609e551688e21cbdb6ebd6ad2f2665444a01880084"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 04: Build Metadata Modernization & PyPI Publishing Verification Report

**Phase Goal:** hermes-brain ships as a clean, modernly-packaged PyPI distribution with tokenless automated publishing and a documented manual fallback.
**Verified:** 2026-09-26
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Success Criteria Verdicts

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | PEP 639 SPDX `license = "MIT"`, no legacy table, clean `build` + `twine check --strict` with zero deprecation warnings (META-01, META-02) | ✓ VERIFIED | `pyproject.toml:10` `license = "MIT"`, `:11` `license-files = ["LICENSE"]`, `:2` `requires = ["setuptools>=77.0.3"]`. No `{ text = ... }` table present. `uv run --no-sync pytest tests/test_packaging.py -q` → `4 passed in 95.52s` — `test_offline_build_and_twine_check` asserts exit 0, no `deprecationwarning`/`deprecated` in stderr, 1 wheel + 1 sdist, and `twine check --strict` exit 0. |
| 2 | `v*` tag triggers CI that builds wheel+sdist and uploads to PyPI via OIDC; NO static PyPI token in CI (DIST-01) | ✓ VERIFIED | `publish.yml:3-6` `on.push.tags: ['v*']`; `:90-93` build sdist+wheel then `twine check --strict`; `:114-117` `pypa/gh-action-pypi-publish@release/v1`. grep for `PYPI_API_TOKEN`/`TWINE_TOKEN`/`PYPI_PASSWORD` in publish.yml → none. Only `secrets.GITHUB_TOKEN` (`:133`, standard release-notes token, not a PyPI credential). No other workflow publishes to PyPI (scanned `ci.yml`, `orcarouter-code-review.yml`). |
| 3 | Publish workflow separates build/publish jobs, gates on `refs/tags/v*`, `environment: pypi` + `id-token: write` scoped to publish job | ✓ VERIFIED | Separate `build` (`:51`) and `publish` (`:101`) jobs; `publish` `needs: [build]` (`:102`); `environment: pypi` (`:104`); job-scoped `permissions: id-token: write, contents: read` (`:105-107`). No workflow-level `permissions` block (grep confirms `permissions:` appears only at `:105` publish and `:122` release/contents:write). Tag gate via `on.push.tags: ['v*']` + build-job ancestry/version guard (`:58-78`). |
| 4 | Maintainer can do offline/emergency release via documented twine runbook, no GitHub Actions (DIST-03) | ✓ VERIFIED | `docs/RELEASES.md:49-65` §3 "Emergency Manual Release": `rm -rf dist/ build/ *.egg-info` → `python -m build` → `twine check --strict dist/*` → `export TWINE_USERNAME/TWINE_PASSWORD` → `twine upload dist/*`. Env-var-only credential handling, placeholder token, explicit "never as a CLI argument and never committed" (`:63`). |

### Observable Truths (from PLAN must_haves)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | D-02: `v*` tag triggers publish.yml; no other workflow publishes | ✓ VERIFIED | `publish.yml:3-6`; no `pypi-publish`/`twine upload` in other workflows |
| 2 | D-01/D-03: publish job `environment: pypi` + `id-token: write, contents: read` | ✓ VERIFIED | `publish.yml:104-107` |
| 3 | D-12/D-17: build refuses unless PEP440/SemVer tag, version==pyproject, ancestor of origin/main | ✓ VERIFIED | `publish.yml:58-78` (`git merge-base --is-ancestor`, regex `^\d+\.\d+\.\d+...`, tomllib version-equality assert) |
| 4 | D-10/D-19: `rm -rf` before build, `twine check --strict`, upload only on success | ✓ VERIFIED | `publish.yml:88-98` |
| 5 | D-04: release job uses native `gh release create --generate-notes` with `dist/*` | ✓ VERIFIED | `publish.yml:131-137`; no `softprops` present |
| 6 | D-20: smoke-test polls `pip install` with backoff and imports notion_brain | ✓ VERIFIED | `publish.yml:139-159` (12×10s loop, `import notion_brain`) |
| 7 | D-08/D-09: RELEASES.md covers automated, one-time TP setup, manual twine, recovery/yank | ✓ VERIFIED | `docs/RELEASES.md` §1 (`:7`), §2 (`:22`), §3 (`:49`), §4 (`:67`) |
| 8 | D-11: no static PyPI API token anywhere in workflow/repo | ✓ VERIFIED | grep of publish.yml + RELEASES.md → no token secret refs |
| 9 | D-16: `concurrency: group: publish`, `cancel-in-progress: false` | ✓ VERIFIED | `publish.yml:8-10` |
| 10 | D-13: build depends on test+lint matrix across 3.11/3.12/3.13 | ✓ VERIFIED | `publish.yml:13-49, 52` (`build.needs: [test, lint]`, matrix `["3.11","3.12","3.13"]`) |

**Score:** 10/10 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `.github/workflows/publish.yml` | Six-job gated OIDC workflow | ✓ VERIFIED | 160 lines; jobs test, lint, build, publish, release, smoke-test all present and wired via `needs` |
| `docs/RELEASES.md` | Four-section maintainer runbook | ✓ VERIFIED | 86 lines; 4 H2 sections present |
| `pyproject.toml` | PEP 639 license + setuptools>=77.0.3 | ✓ VERIFIED | `:10-11`, `:2` |
| `notion_brain/__init__.py` | `__version__` matches pyproject | ✓ VERIFIED | `:16` `__version__ = "1.0.3"` == pyproject `version = "1.0.3"` |
| `tests/test_packaging.py` | Offline packaging tests | ✓ VERIFIED | 4 tests, all pass offline (no network/mocks) |

### Key Link Verification

| From | To | Via | Status |
| --- | --- | --- | --- |
| publish.yml `on.push.tags` | tag push event | `['v*']` | ✓ WIRED |
| publish.yml `jobs.publish.permissions.id-token` | PyPI OIDC exchange | job-scoped `id-token: write` | ✓ WIRED |
| build ancestry step | origin/main | `fetch-depth: 0` + `git merge-base --is-ancestor` | ✓ WIRED |
| build version step | pyproject `[project].version` | tomllib assert equality | ✓ WIRED |
| build twine-check | dist/* | `twine check --strict` gates upload | ✓ WIRED |
| publish job | pypa/gh-action-pypi-publish@release/v1 | `packages-dir: dist/` | ✓ WIRED |
| RELEASES §2 | PyPI Trusted Publisher | owner=MNDL-27, repo=hermes-brain, workflow=publish.yml, env=pypi | ✓ WIRED |
| RELEASES §3 | twine upload | TWINE_USERNAME/TWINE_PASSWORD env vars | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Offline build + twine + version sync + PEP639 | `uv run --no-sync pytest tests/test_packaging.py -q` | `4 passed in 95.52s` | ✓ PASS |
| No PyPI token secret in CI | grep publish.yml for token secrets | none found | ✓ PASS |
| id-token scoped to publish job only | grep `permissions:` in publish.yml | only job-level (`:105`,`:122`) | ✓ PASS |
| No other PyPI publishing workflow | grep workflows for pypi-publish/twine upload | none besides publish.yml | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| META-01 | 04-01 | PEP 639 SPDX license, no legacy table, setuptools>=77.0.3 | ✓ SATISFIED | pyproject.toml:2,10-11; test_pyproject_metadata_conforms_to_pep_639, test_no_legacy_license_table pass |
| META-02 | 04-01 | Clean zero-deprecation build + strict twine | ✓ SATISFIED | test_offline_build_and_twine_check passes (no deprecation, twine exit 0) |
| DIST-01 | 04-02 | Tokenless OIDC automated publish on `v*` tag | ✓ SATISFIED | publish.yml OIDC via gh-action-pypi-publish; no static token |
| DIST-02 | 04-02 | Split build/publish, `environment: pypi`, job-scoped id-token | ✓ SATISFIED | publish.yml:101-107 |
| DIST-03 | 04-02 | Documented offline twine fallback | ✓ SATISFIED | docs/RELEASES.md §3 |

### Security Must-Haves

| Constraint | Status | Evidence |
| --- | --- | --- |
| No PYPI_API_TOKEN/TWINE_TOKEN/PYPI_PASSWORD outside manual fallback | ✓ VERIFIED | grep of publish.yml + RELEASES.md → no such secret refs; RELEASES §3 uses TWINE_USERNAME/TWINE_PASSWORD env vars only |
| `id-token: write` scoped to publish job, not workflow-level | ✓ VERIFIED | publish.yml:105-107 (no top-level permissions block) |
| Manual fallback uses env vars, no token CLI arg, no committed literal | ✓ VERIFIED | RELEASES.md:57-63 (`export TWINE_PASSWORD="pypi-<your-token-here>"` placeholder; explicit "never as a CLI argument and never committed") |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| docs/RELEASES.md | 40 | word "placeholder" | ℹ️ Info | Prose describing PyPI placeholder-upload procedure; not a code stub |

No debt markers (TODO/FIXME/XXX/TBD) in any phase-modified file.

### Operational Prerequisite (Informational — one-time, external)

The workflow is correctly and completely configured for tokenless OIDC publishing. The *first live publish* additionally requires the PyPI Trusted Publisher to be registered on pypi.org (owner=MNDL-27, repo=hermes-brain, workflow=publish.yml, environment=pypi) and a GitHub `pypi` environment to exist. This is an external, deploy-time setup step explicitly documented in `docs/RELEASES.md` §2 — it is a runbook prerequisite, not a codebase gap, and does not affect this phase's deliverables.

### Gaps Summary

None. All four success criteria, all ten PLAN truths, all five requirements (META-01/02, DIST-01/02/03), and all three security constraints are verified against the actual codebase. Packaging tests pass 4/4 offline.

---

_Verified: 2026-09-26_
_Verifier: Claude (gsd-verifier)_
