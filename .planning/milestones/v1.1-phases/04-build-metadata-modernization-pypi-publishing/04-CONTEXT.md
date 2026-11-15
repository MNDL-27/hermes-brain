# Phase 4: Build Metadata Modernization & PyPI Publishing - Context

**Gathered:** 2026-09-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Modernize packaging to PEP 639 SPDX string declarations (`license = "MIT"`), raise `setuptools>=77.0.3` build-system floor, configure automated GitHub Actions PyPI publishing with OIDC Trusted Publishing (`id-token: write`, `environment: pypi`, build provenance attestations), and author a comprehensive maintainer release runbook (`docs/RELEASES.md`) with emergency manual twine fallback.

</domain>

<decisions>
## Implementation Decisions

### Version & Tag Discipline
- **D-01:** Enforce git tag strictly matches `pyproject.toml` version — build job validates tag matches version and fails early on mismatch. — **Reversibility:** costly — changing tag matching convention affects CI workflows and release scripts.
- **D-02:** Use standard `v*` tag format (`v1.1.0`), stripping leading `v` to validate against `pyproject.toml` version.
- **D-03:** Publish all `v*` tags including pre-releases (`v1.1.0b1`, `v1.1.0rc1`) to PyPI. PyPI automatically flags pre-releases so standard pip users won't receive them without `--pre`.
- **D-04:** Publish workflow automatically generates a matching GitHub Release with release notes linking the git tag and commit diff upon successful PyPI upload.
- **D-05:** Release version bumping is manual: maintainer updates version in `pyproject.toml`, commits `chore: release vX.Y.Z`, and pushes git tag `vX.Y.Z`.
- **D-06:** Document release recovery in runbook: if workflow fails before publish, fix and re-tag; if bad package is already published to PyPI, yank release via PyPI UI / twine (PyPI forbids re-uploading existing version numbers).

### Runbook Placement & Content
- **D-07:** Create dedicated maintainer guide `docs/RELEASES.md` covering automated OIDC release lifecycle, PyPI one-time setup, and manual twine emergency fallback. Keeps user-facing `README.md` clean.
- **D-08:** Include full step-by-step walkthrough in `docs/RELEASES.md` for configuring PyPI Trusted Publishing (PyPI account → Publishing → Add publisher for `MNDL-27/hermes-brain` / `publish.yml` / `pypi` environment) before the first tag push.
- **D-09:** Document emergency manual uploads using PyPI API token via `TWINE_PASSWORD` environment variable or `~/.pypirc`.
- **D-10:** Document explicit pre-build cleaning (`rm -rf dist/ build/ *.egg-info`) in runbook to prevent stale artifact re-upload attempts.

### Publish Gate Behavior
- **D-11:** Fully automated publish on tag push without manual GitHub environment approval gate.
- **D-12:** Workflow verifies that the pushed tag points to a commit reachable from the `main` branch before building/publishing, blocking accidental releases from experimental branches.
- **D-13:** Run full test suite (`pytest`, `ruff`, `mypy`) across Python matrix in CI as a prerequisite job before the publish job runs. Never publish from a broken tag.
- **D-14:** Enable PyPI build provenance attestations (`attestations: true` in `pypa/gh-action-pypi-publish`).
- **D-15:** Standard GitHub Actions re-run for transient network/PyPI errors; no custom retry loops inside workflow.
- **D-16:** Use `concurrency: group: publish` to serialize tag publish runs and prevent racing GitHub releases.
- **D-17:** Strict PEP 440 / SemVer format validation of tag before initiating build.

### Verification Depth
- **D-18:** Direct publication to production PyPI only; TestPyPI is omitted to minimize operational overhead.
- **D-19:** Artifact verification runs `twine check --strict` on both wheel and sdist in the build job before upload.
- **D-20:** Automated post-publish smoke install job in CI: polls PyPI for new release, installs in isolated container, and verifies `python -c "import notion_brain"`.
- **D-21:** Unit test packaging offline in `tests/test_packaging.py` asserting `pyproject.toml` SPDX license string, build-backend floor (`setuptools>=77.0.3`), and clean offline `build` + `twine check`. Preserves 100% offline test guarantee.

### Claude's Discretion
None — all key release workflow parameters explicitly selected during discussion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — Active v1.1 requirements (META-01, META-02, DIST-01, DIST-02, DIST-03)
- `.planning/ROADMAP.md` — Phase 4 scope, goals, and success criteria
- `.planning/research/SUMMARY.md` — Synthesized findings on PEP 639 setuptools floor and OIDC workflow patterns

### Existing Configuration
- `pyproject.toml` — Current packaging metadata, dependencies, build-system requirements
- `.github/workflows/ci.yml` — Current CI test matrix and quality-debt workflow structure

### Documentation Targets
- `docs/RELEASES.md` — Release process and emergency runbook (to be created in this phase)
- `.github/workflows/publish.yml` — OIDC release workflow (to be created in this phase)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/workflows/ci.yml`: Actions structure, Python matrix (`3.11`, `3.12`, `3.13`), `astral-sh/setup-uv@v6`, and dependency installation steps.
- `notion_brain/__init__.py`: Version string declaration (`__version__ = "1.0.3"`).

### Established Patterns
- PEP 621 declarative configuration in `pyproject.toml`.
- Strict secret scrubbing and offline test requirements across the repo.

### Integration Points
- `.github/workflows/publish.yml`: Triggered on `push: tags: ['v*']`.
- `pyproject.toml`: Modernized `license = "MIT"` and `requires = ["setuptools>=77.0.3"]`.
- `tests/test_packaging.py`: Offline packaging and metadata tests.
- `docs/RELEASES.md`: Maintainer release instructions.

</code_context>

<specifics>
## Specific Ideas
- The build step must strip `v` from tag `vX.Y.Z` and assert string equality with `pyproject.toml` version.
- Smoke test job in CI should retry package installation with exponential backoff to tolerate PyPI index CDN replication delay.

</specifics>

<deferred>
## Deferred Ideas
None — discussion stayed strictly within Phase 4 boundaries.

</deferred>

---

*Phase: 4-Build Metadata Modernization & PyPI Publishing*
*Context gathered: 2026-09-22*
