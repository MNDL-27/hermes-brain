---
status: complete
phase: 04-build-metadata-modernization-pypi-publishing
source:
  - .planning/phases/04-build-metadata-modernization-pypi-publishing/04-01-SUMMARY.md
  - .planning/phases/04-build-metadata-modernization-pypi-publishing/04-02-SUMMARY.md
started: 2026-09-24T10:55:00Z
updated: 2026-09-24T10:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. PEP 639 SPDX license declaration (META-01)
expected: `pyproject.toml` declares `license = "MIT"` and no legacy `license = { text = ... }` table exists.
result: pass
evidence: `grep -E "^license" pyproject.toml` returns `license = "MIT"` and `license-files = ["LICENSE"]`. No legacy table.

### 2. Setuptools build-system floor (META-02)
expected: `pyproject.toml` build-system requires `setuptools>=77.0.3`.
result: pass
evidence: `requires = ["setuptools>=77.0.3"]` confirmed.

### 3. Version sync between pyproject and `__init__.py`
expected: `pyproject.toml [project].version` equals `notion_brain/__init__.py __version__`.
result: pass
evidence: Both contain `1.0.3`. `tests/test_packaging.py::test_version_strings_match` passes.

### 4. Packaging tests pass offline
expected: `uv run pytest tests/test_packaging.py` reports 3 passed, 1 skipped.
result: pass
evidence: Last run: `3 passed, 1 skipped in 1.69s`.

### 5. `publish.yml` is valid YAML (DIST-02)
expected: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml'))"` exits 0.
result: pass
evidence: `YAML parse: OK`.

### 6. Workflow has all six required jobs (DIST-02)
expected: Jobs `test`, `lint`, `build`, `publish`, `release`, `smoke-test` all present.
result: pass
evidence: Inline verifier asserts each job name; all six found.

### 7. OIDC trust bridge scoped to publish job (DIST-01)
expected: `id-token: write` appears exactly once, scoped under `publish:`, not at workflow level. `environment: pypi` declared.
result: pass
evidence: Inline verifier: `id-token count = 1`; `environment: pypi` present.

### 8. No static PyPI token anywhere (DIST-01, D-11)
expected: Zero occurrences of `PYPI_API_TOKEN`, `TWINE_TOKEN`, or `secrets.PYPI`.
result: pass
evidence: Inline verifier asserts none present.

### 9. Tag-trigger only — no branch or PR trigger (D-02)
expected: `on.push.tags: ['v*']` is the sole trigger; no `branches:` or `pull_request:`.
result: pass
evidence: Inline verifier checks for `tags: ['v*']` literal.

### 10. Ancestry guard present (D-12, D-17)
expected: Build job runs `git merge-base --is-ancestor HEAD origin/main` with `fetch-depth: 0`.
result: pass
evidence: Inline verifier confirms both literals.

### 11. Version guard present (D-12, D-17)
expected: Inline Python script uses `tomllib` to assert tag version equals `[project].version`.
result: pass
evidence: Inline verifier confirms `tomllib` and `pyproject.toml` literals.

### 12. Pre-build cleanup + twine check --strict (D-10, D-19)
expected: `rm -rf dist/ build/ *.egg-info` runs before `python -m build`; `twine check --strict dist/*` runs before upload.
result: pass
evidence: Inline verifier confirms both literals.

### 13. Native gh release, no softprops (D-04)
expected: `gh release create` used; `softprops` absent.
result: pass
evidence: Inline verifier asserts both.

### 14. Concurrency group serializes publishes (D-16)
expected: Top-level `concurrency: { group: publish, cancel-in-progress: false }` declared.
result: pass
evidence: Inline verifier confirms both literals.

### 15. Smoke-test polls PyPI with backoff (D-20)
expected: 12-attempt polling loop using `pip install --no-cache-dir` and `seq 1 12`.
result: pass
evidence: Inline verifier confirms both literals.

### 16. RELEASES.md has 4 numbered sections (DIST-03, D-07)
expected: H2 sections for Automated Release, Trusted Publisher Setup, Emergency Manual Release, Release Recovery.
result: pass
evidence: Inline verifier enumerates H2 sections; all four present.

### 17. RELEASES.md names both version-bump targets (DIST-03)
expected: Both `pyproject.toml` and `notion_brain/__init__.py` named in §1.
result: pass
evidence: Inline verifier confirms both literals present.

### 18. RELEASES.md lists all PyPI Trusted Publisher fields (D-08)
expected: `hermes-brain`, `MNDL-27`, `publish.yml`, `pypi` all named in §2.
result: pass
evidence: Inline verifier confirms all four.

### 19. RELEASES.md manual fallback is env-var only (D-09)
expected: `export TWINE_USERNAME="__token__"`, `export TWINE_PASSWORD=...`, never CLI args.
result: pass
evidence: §3 fenced block uses `export` form exclusively.

### 20. RELEASES.md recovery covers both pre- and post-publish (D-06)
expected: Both tag-delete + re-tag path and yank + patch-release path documented.
result: pass
evidence: §4 has two branches with explicit commands.

### 21. No real PyPI token literal in repo
expected: No `pypi-AgEI...` literal anywhere.
result: pass
evidence: Inline verifier regex confirms.

## Summary

total: 21
passed: 21
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

(none)
