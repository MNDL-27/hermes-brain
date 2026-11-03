---
phase: "08"
slug: "developer-tooling-test-reliability"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-08"
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Sourced from `08-RESEARCH.md` §Validation Architecture (researched 2026-10-08, empirical pytest runs).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 [VERIFIED: pyproject.toml:38] |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, addopts: `-m "not network"`) [VERIFIED: pyproject.toml:48-55] |
| **Quick run command** | `timeout 60 uv run --no-sync pytest tests/test_coverage_gaps.py tests/regressions/test_migration_privacy_blockers.py tests/test_provider.py -q` |
| **Full suite command** | `timeout 300 uv run --no-sync pytest -q` |
| **Estimated runtime** | ~10 seconds (empirical 8.50s measured 2026-10-08) |
| **Test count** | 352 passed + 1 deselected (`@pytest.mark.network` — `test_offline_build_and_twine_check`) |

## Sampling Rate

- **After every task commit:** Run `{quick run command}` above (the three TEST-HANGS files)
- **After every plan wave:** Run `{full suite command}` above, must exit 0 in ≤30s
- **Before `/gsd-verify-work`:** Full suite must be green; suite count must be 352 passed + 1 deselected (not silent drops)
- **Max feedback latency:** 30 seconds (full suite)
- **TOOL-02 dry-run (after workflow file is created):** `python -c "import yaml; yaml.safe_load(open('.github/workflows/pre-commit-autoupdate.yml'))"` + `actionlint .github/workflows/pre-commit-autoupdate.yml` if available

---

## Per-Task Verification Map

Task IDs are pre-assumed in the canonical v1.0/v1.1 pattern (matches the eventual PLAN.md). The planner should produce plans that match this map 1:1.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | TEST-HANGS | T-08-01 | Hermetic offline contract: socket-deny + `network` marker + env-neutralize | unit | `grep -E "socket.connect" tests/conftest.py` | ❌ W0 (uncommitted) | ⬜ pending |
| 08-01-02 | 01 | 1 | TEST-HANGS | T-08-02 | `test_search_dispatches` patches real call site (`notion_brain.store.query_database`) | unit | `grep -E "query_database" tests/test_provider.py` | ❌ W0 (uncommitted) | ⬜ pending |
| 08-01-03 | 01 | 1 | TEST-HANGS | T-08-03 | `test_initialize_error_redacts_secrets` neutralizes init-refresh worker | unit | `grep -E "update_cache.refresh" tests/test_provider.py` | ❌ W0 (uncommitted) | ⬜ pending |
| 08-01-04 | 01 | 1 | TEST-HANGS | T-08-04 | `pyproject.toml` addopts deselects network-marked + markers declared | unit | `grep -E '"-m", "not network"' pyproject.toml && grep -E '"network"' pyproject.toml` | ❌ W0 (uncommitted) | ⬜ pending |
| 08-01-05 | 01 | 1 | TEST-HANGS | T-08-05 | `tests/test_packaging.py` marks `test_offline_build_and_twine_check` as `@pytest.mark.network` | unit | `grep -B1 "test_offline_build_and_twine_check" tests/test_packaging.py \| grep -E "@pytest.mark.network"` | ❌ W0 (uncommitted) | ⬜ pending |
| 08-01-06 | 01 | 1 | TEST-HANGS | T-08-06 | `.github/workflows/publish.yml` has top-level `permissions: contents: read` (CodeQL medium) | ci-contract | `python3 -c "import yaml; w=yaml.safe_load(open('.github/workflows/publish.yml')); assert w.get(True, {}).get('permissions', {}).get('contents') == 'read'"` | ❌ W0 (uncommitted) | ⬜ pending |
| 08-01-07 | 01 | 1 | TEST-HANGS | — | Three named test files finish individually under 60s | integration | `timeout 60 uv run --no-sync pytest tests/test_coverage_gaps.py tests/regressions/test_migration_privacy_blockers.py tests/test_provider.py -q` | ✅ verified (5.40s) | ⬜ pending (commit) |
| 08-01-08 | 01 | 1 | TEST-HANGS | — | Full offline `pytest -q` finishes under 300s, 352 passed + 1 deselected, no hangs | integration | `time timeout 300 uv run --no-sync pytest -q` | ✅ verified (8.50s) | ⬜ pending (commit) |
| 08-02-01 | 02 | 2 | TOOL-01 | T-08-07 | Hook script at `scripts/pre-push`, executable, exits non-zero on pytest failure | shell | `test -x scripts/pre-push && bash -n scripts/pre-push` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | TOOL-01 | T-08-08 | Hook invokes `uv run --no-sync pytest -q` (matches CI) | shell | `grep -E "uv run --no-sync pytest -q" scripts/pre-push` | ❌ W0 | ⬜ pending |
| 08-02-03 | 02 | 2 | TOOL-01 | T-08-09 | Hook fails fast via `timeout 300` shell wrapper (no new dev dep) | shell | `grep -E "^timeout 300" scripts/pre-push` | ❌ W0 | ⬜ pending |
| 08-02-04 | 02 | 2 | TOOL-01 | T-08-10 | Hook honors escape hatch `HERMES_BRAIN_SKIP_PRE_PUSH=1` | shell | `grep -E "HERMES_BRAIN_SKIP_PRE_PUSH" scripts/pre-push` | ❌ W0 | ⬜ pending |
| 08-02-05 | 02 | 2 | TOOL-01 | T-08-11 | Hook never mutates environment (no `pip install`, no `git pull`) | lint | `! grep -E "pip install\|git pull" scripts/pre-push` | ❌ W0 | ⬜ pending |
| 08-02-06 | 02 | 2 | TOOL-01 | T-08-12 | `README.md` / `CONTRIBUTING.md` documents opt-in install + escape hatch | doc-audit | `grep -E "scripts/pre-push\|HERMES_BRAIN_SKIP_PRE_PUSH" README.md CONTRIBUTING.md 2>/dev/null` | ❌ W0 | ⬜ pending |
| 08-02-07 | 02 | 2 | TOOL-01 | T-08-13 | Hook dry-run on no-op push exits 0; on staged-fail push exits non-zero | integration | `cp scripts/pre-push .git/hooks/pre-push && bash scripts/pre-push` (both branches) | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 2 | TOOL-02 | T-08-14 | `.github/workflows/pre-commit-autoupdate.yml` exists, valid YAML | ci-contract | `python -c "import yaml; yaml.safe_load(open('.github/workflows/pre-commit-autoupdate.yml'))"` | ❌ W0 | ⬜ pending |
| 08-03-02 | 03 | 2 | TOOL-02 | T-08-15 | Workflow has `schedule:` cron + `workflow_dispatch` fallback | ci-contract | `python -c "import yaml; d=yaml.safe_load(open('.github/workflows/pre-commit-autoupdate.yml')); assert 'schedule' in d[True]; assert 'workflow_dispatch' in d[True]"` | ❌ W0 | ⬜ pending |
| 08-03-03 | 03 | 2 | TOOL-02 | T-08-16 | Workflow-level `permissions: contents: read`; autoupdate job overrides to `contents: write, pull-requests: write` only | ci-contract | `python -c "import yaml; d=yaml.safe_load(open('.github/workflows/pre-commit-autoupdate.yml')); assert d['permissions'] == {'contents': 'read'}; assert d['jobs']['autoupdate']['permissions'] == {'contents': 'write', 'pull-requests': 'write'}"` | ❌ W0 | ⬜ pending |
| 08-03-04 | 03 | 2 | TOOL-02 | T-08-17 | Workflow runs `pre-commit autoupdate` and uses `peter-evans/create-pull-request@v6` with `branch-suffix: timestamp` + `delete-branch: true` | ci-contract | `grep -E "pre-commit autoupdate" .github/workflows/pre-commit-autoupdate.yml && grep -E "peter-evans/create-pull-request@v6" .github/workflows/pre-commit-autoupdate.yml` | ❌ W0 | ⬜ pending |
| 08-03-05 | 03 | 2 | TOOL-02 | T-08-18 | Workflow declares `concurrency:` group to cancel in-progress duplicate runs | ci-contract | `grep -E "concurrency:" .github/workflows/pre-commit-autoupdate.yml` | ❌ W0 | ⬜ pending |
| 08-03-06 | 03 | 2 | TOOL-02 | T-08-19 | `.pre-commit-config.yaml` exists at repo root (else autoupdate is a no-op) | doc-audit | `test -f .pre-commit-config.yaml` | ❓ (verify first) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/pre-push` — TOOL-01 hook (POSIX shell, ~50 lines, with `timeout 300 uv run --no-sync pytest -q` + `HERMES_BRAIN_SKIP_PRE_PUSH` escape hatch + README doc comment)
- [ ] `README.md` — new "Local pre-push tests (opt-in)" subsection documenting the install one-liner and the escape hatch
- [ ] `.github/workflows/pre-commit-autoupdate.yml` — TOOL-02 weekly workflow (cron + workflow_dispatch, workflow-level `permissions: contents: read`, autoupdate job override, `peter-evans/create-pull-request@v6`, concurrency group)
- [ ] `.pre-commit-config.yaml` — only if not already present; if absent, hook autoupdate is a no-op (still a valid workflow, just won't PR)
- [ ] The five uncommitted infra files committed as Wave 1 (these ARE the TEST-HANGS resolution, not separate debt):
  - `tests/conftest.py` — autouse `_hermetic_offline` fixture, socket-deny + env-neutralize
  - `pyproject.toml` — `[tool.pytest.ini_options] addopts = ["-m", "not network"]` + markers declaration
  - `tests/test_packaging.py` — `@pytest.mark.network` on `test_offline_build_and_twine_check`
  - `tests/test_provider.py` — `test_search_dispatches` mock-target fix + `test_initialize_error_redacts_secrets` init-refresh patch
  - `.github/workflows/publish.yml` — top-level `permissions: contents: read` (CodeQL medium)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pre-push hook blocks a real `git push` on a known-failing local test | TOOL-01 | Requires a real `git push` against the contributor's remote | Run a deliberately failing test (`pytest.fail("x")`), commit, attempt `git push`, confirm push is rejected and pytest output is surfaced |
| Autoupdate workflow's first PR (when `.pre-commit-config.yaml` is updated by upstream) | TOOL-02 | Requires first cron run (or manual `workflow_dispatch`); requires repo write access | Either wait for the Monday 06:17 UTC cron, or run `gh workflow run pre-commit-autoupdate.yml` once. Confirm an autoupdate PR appears (or a summary posts if no update) |
| Branch-protection interaction with autoupdate PR auto-merge | TOOL-02 | Repo setting under owner's control | Document in PR body that maintainer approval-and-squash is required (matches `publish.yml` `environment: pypi` pattern) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all 5 uncommitted-infra items + the 4 new artifacts (hook script, README subsection, autoupdate workflow, .pre-commit-config.yaml if missing)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (post-execute; pre-execute = draft)

**Approval:** pending
