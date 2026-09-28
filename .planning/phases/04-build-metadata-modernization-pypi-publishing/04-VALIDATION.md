---
phase: "04"
slug: "build-metadata-modernization-pypi-publishing"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-22"
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --no-sync pytest tests/test_packaging.py -q` |
| **Full suite command** | `uv run --no-sync pytest -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --no-sync pytest tests/test_packaging.py -q`
- **After every plan wave:** Run `uv run --no-sync pytest -q && uv run --no-sync ruff check . && uv run --no-sync mypy notion_brain tests`
- **Before `/gsd-verify-work`:** Full suite must be green, build succeeds with zero deprecations, twine check passes
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | META-01 | — | N/A | unit | `uv run --no-sync pytest tests/test_packaging.py -k test_pyproject_metadata_conforms_to_pep_639` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | META-02 | — | N/A | integration | `python -m build --sdist --wheel && twine check --strict dist/*` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | DIST-01 | T-04-01 | Zero static secrets; PyPI OIDC minting | ci-contract | `python3 -c "import yaml; w = yaml.safe_load(open('.github/workflows/publish.yml')); assert 'id-token' in str(w)"` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | DIST-02 | T-04-02 | Separate build and publish jobs; environment: pypi | ci-contract | `python3 -c "import yaml; w = yaml.safe_load(open('.github/workflows/publish.yml')); assert 'pypi' in str(w['jobs']['publish']['environment'])"` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 2 | DIST-03 | T-04-03 | Clean release artifacts and manual offline twine instructions | doc-audit | `test -f docs/RELEASES.md && grep -q 'twine upload' docs/RELEASES.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_packaging.py` — unit tests for META-01, META-02, and version synchronization
- [ ] `.github/workflows/publish.yml` — automated OIDC release workflow for DIST-01, DIST-02
- [ ] `docs/RELEASES.md` — maintainer runbook for DIST-03

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PyPI Trusted Publisher initial one-time configuration | DIST-01 | Requires PyPI web UI admin interaction | Verify pending publisher or project settings on pypi.org per docs/RELEASES.md |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
