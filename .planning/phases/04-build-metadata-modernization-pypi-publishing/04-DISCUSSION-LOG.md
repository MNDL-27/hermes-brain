# Phase 4: Build Metadata Modernization & PyPI Publishing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-22
**Phase:** 4-Build Metadata Modernization & PyPI Publishing
**Areas discussed:** Version & tag discipline, Runbook placement & content, Publish gate behavior, Verification depth

---

## Version & Tag Discipline

| Option | Description | Selected |
|--------|-------------|----------|
| Enforce tag == pyproject version | Build step verifies git tag matches pyproject.toml and `__version__` in `notion_brain/__init__.py`. Fails early if they mismatch — eliminates partial or mislabeled releases. | ✓ |
| Trust maintainer (no validation) | Build packages whatever version is in pyproject.toml, regardless of tag name. | |
| v-prefix: `v*` (v1.1.0) | GitHub release standard: `v1.1.0` (workflow strips the `v` prefix to compare with `1.1.0` in pyproject.toml). Already used in v1.0 tag. | ✓ |
| Accept both `v*` and bare `*.*.*` | Allow both `v1.1.0` and bare `1.1.0` tags to trigger publishing. | |
| Publish pre-releases to PyPI | Publish all `v*` tags (e.g. `v1.1.0b1`, `v1.1.0rc1`) to PyPI. PyPI automatically classifies pre-releases; users only get them with `--pre`. | ✓ |
| Block pre-releases in CI | Only publish stable `vX.Y.Z` tags (no beta/rc). | |
| Create GitHub Release on publish | Publish workflow uploads to PyPI, then creates a matching GitHub Release with auto-generated release notes linking tag and commit diff. | ✓ |
| PyPI upload only | Maintainer writes GitHub releases manually when changelog is drafted. | |
| Manual commit + tag | Maintainer edits pyproject.toml version, commits `chore: release vX.Y.Z`, then pushes tag. Documented in runbook. | ✓ |
| Dynamic version via importlib | Read version dynamically at runtime via importlib.metadata. | |
| Document recovery steps | Document in runbook: failed publish → fix → delete tag → re-tag; published versions yanked on PyPI. | ✓ |
| Automated yank workflow | Add a `publish-yank.yml` workflow to yank a tag via PyPI API. | |

**User's choice:** Strict tag-version synchronization, standard `v*` format, pre-release auto-publish, GitHub release generation, manual bump flow, documented recovery.
**Notes:** Prevents mislabeled packages and enforces strict git tag consistency.

---

## Runbook Placement & Content

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `docs/RELEASES.md` | Dedicated, comprehensive guide for maintainers covering the full release lifecycle (automated OIDC + manual fallback + PyPI one-time setup). Keeps README clean for users. | ✓ |
| Section in `CONTRIBUTING.md` | Add a "Release Process" section to `CONTRIBUTING.md`. | |
| Section in `README.md` | Add to `README.md` under an "Advanced / Maintainers" heading. | |
| Full PyPI OIDC setup guide | Include step-by-step walkthrough: log in to pypi.org → account settings → publishing → add publisher (`MNDL-27/hermes-brain`, `publish.yml`, `pypi` env). | ✓ |
| Link to PyPA docs only | Link to official PyPA documentation without detailing the steps. | |
| API token (`TWINE_PASSWORD`) | Document standard PyPI API token via `~/.pypirc` or environment variable `TWINE_PASSWORD=pypi-...` for emergency local uploads. | ✓ |
| Keyring + API token | Recommend `keyring` library for system credential storage in addition to token env var. | |
| Enforce pre-build dist/ wipe | Document `rm -rf dist/ build/ *.egg-info` before building to prevent accidentally re-uploading stale artifacts. | ✓ |
| Standard build command only | Mention `python -m build` directly without explicit pre-clean command. | |

**User's choice:** Dedicated `docs/RELEASES.md`, complete PyPI OIDC setup guide, `TWINE_PASSWORD` emergency auth, and explicit pre-build cleaning.
**Notes:** Ensures clean maintainer onboarding and safe offline/emergency distribution.

---

## Publish Gate Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Fully automated (no approval) | Pushing the tag triggers build + publish with no manual approval button. Standard for small/solo open source. | ✓ |
| Manual approval gate in GitHub | Configure GitHub environment `pypi` with "Required reviewers". | |
| Require tag on `main` branch | Workflow verifies the tag points to a commit on `main` branch. Prevents accidental release of experimental branch tags. | ✓ |
| Allow tags from any ref | Publish any `v*` tag from any branch or detached HEAD. | |
| Run full test matrix before publish | Publish workflow runs full test suite (`pytest`, `ruff`, `mypy`) as a required first job before the publish job runs. | ✓ |
| Build + twine check only (fast) | Assume tests already passed on PR/main merge commit. Publish workflow only does `build` + `twine check` + upload. | |
| Enable build attestations | `pypa/gh-action-pypi-publish` with `attestations: true` generates cryptographic build provenance attestations on PyPI. | ✓ |
| Standard upload only | Standard upload without attestations. | |
| Standard GitHub re-run | GitHub Actions standard one-click Re-run on tag push for transient network/PyPI errors. | ✓ |
| In-workflow retry loop | Custom retry loop wrapper around upload step. | |
| Serialize tag publishes | `concurrency: group: publish` queues concurrent tag pushes. | ✓ |
| Allow concurrent publishes | Concurrent tag publishing without serialization. | |
| Strict format validation | Strict PEP 440/SemVer tag format validation prior to building. | ✓ |
| Fail naturally at build | Let build fail if tag is malformed. | |

**User's choice:** Fully automated execution, `main` branch restriction, full test matrix pre-flight, build attestations, standard GitHub re-runs, serialized execution, strict tag validation.
**Notes:** Balances convenience with strong automated quality and supply chain security gates.

---

## Verification Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Direct to PyPI only | Publish directly to production PyPI on tag push. Omit TestPyPI overhead. | ✓ |
| Support TestPyPI dry-run | Support TestPyPI target via manual workflow_dispatch input or test tags. | |
| `twine check --strict` | Run `twine check --strict` on wheel and sdist in CI build job. | ✓ |
| Twine + wheel contents check | Add `check-wheel-contents` alongside twine. | |
| Automated PyPI smoke install | CI polls PyPI index, installs published wheel in clean container, and runs `python -c "import notion_brain"`. | ✓ |
| Skip CI install check | Skip post-publish install job. | |
| Unit test packaging offline | Add unit tests in `tests/test_packaging.py` asserting `pyproject.toml` SPDX license string, build-backend floor, and clean offline `build` + `twine check`. | ✓ |
| CI-only packaging test | Only test build during CI or manual release runs. | |

**User's choice:** Direct PyPI publication, strict twine verification, automated post-publish smoke test, offline unit tests for packaging metadata in `tests/test_packaging.py`.
**Notes:** Maintains the project's 100% offline test suite guarantee while providing live end-to-end verification in release CI.

---

## Claude's Discretion

None. All decisions explicitly confirmed by maintainer.

## Deferred Ideas

None. All discussed items were directly in scope for Phase 4.
