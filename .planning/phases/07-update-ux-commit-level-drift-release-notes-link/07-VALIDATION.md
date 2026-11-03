---
phase: "07"
slug: "update-ux-commit-level-drift-release-notes-link"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-15"
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Sourced from `07-RESEARCH.md` §Validation Architecture (researched 2026-10-15).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 [VERIFIED: pyproject.toml] |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, addopts: `-m "not network"`) |
| **Quick run command** | `timeout 60 uv run --no-sync pytest tests/test_update.py tests/test_update_cache.py -q` |
| **Full suite command** | `timeout 300 uv run --no-sync pytest -q` |
| **Estimated runtime** | ~10 seconds (empirical 7.75s measured 2026-10-14) |
| **Test count baseline** | 352 passed + 1 deselected (network-marked) — must not shrink silently |

## Sampling Rate

- **After every task commit:** Run `{quick run command}` above (update + update_cache files)
- **After every plan wave:** Run `{full suite command}` above, must exit 0 in ≤30s
- **Before `/gsd-verify-work`:** Full suite must be green; suite count must be ≥352 passed + 1 deselected (not silent drops)
- **Max feedback latency:** 30 seconds (full suite)

---

## Per-Task Verification Map

Task IDs are pre-assumed in the canonical v1.0/v1.1 pattern (matches the eventual PLAN.md). The planner should produce plans that match this map 1:1.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | UPD-06 | T-07-01 | `detect_git_drift` returns skipped on non-main branch / detached HEAD | unit | `grep -E "def detect_git_drift" notion_brain/update.py` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | UPD-06 | T-07-02 | Local `git rev-list --left-right --count HEAD...origin/main` parsed for ahead/behind | unit | `grep -E "rev-list" notion_brain/update.py` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 1 | UPD-06 | T-07-03 | GitHub Compare API fallback used when origin/main absent; 403/429/offline degrade silently | unit | `grep -E "compare/" notion_brain/update.py` | ❌ W0 | ⬜ pending |
| 07-01-04 | 01 | 1 | UPD-06 | T-07-04 | `check_for_update` payload carries `drift_type`, `behind_commits`, `ahead_commits` | unit | `grep -E "drift_type" notion_brain/update.py` | ❌ W0 | ⬜ pending |
| 07-01-05 | 01 | 1 | UPD-07 | T-07-05 | `release_url` = `https://github.com/MNDL-27/hermes-brain/releases/tag/v{tag}` in human + JSON output | unit | `grep -E "releases/tag" notion_brain/update.py` | ❌ W0 | ⬜ pending |
| 07-01-06 | 01 | 1 | UPD-06 | T-07-06 | `_cmd_update` exits 0 on commit-only drift, 2 on version drift | unit | `grep -E "drift_type" notion_brain/__main__.py` | ❌ W0 | ⬜ pending |
| 07-01-07 | 01 | 1 | UPD-06 | — | No mutation: no `git pull`/`git fetch`/`pip install` executed by check paths | lint | `! grep -E "git (pull|fetch)|pip install" notion_brain/update.py` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 2 | UPD-06 | T-07-07 | `update_cache.refresh` stores `behind_commits`/`ahead_commits`/`drift_type` | unit | `grep -E "behind_commits" notion_brain/update_cache.py` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 2 | UPD-06 | T-07-08 | Cache read on startup remains zero-network (<1ms) | unit | `timeout 60 uv run --no-sync pytest tests/test_update_cache.py -q` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 2 | UPD-06 | — | New tests cover: clean local count, API fallback, non-main skip, both-drift precedence, release URL, offline tolerance | unit | `timeout 60 uv run --no-sync pytest tests/test_update.py tests/test_update_cache.py -q` | ❌ W0 | ⬜ pending |
| 07-02-04 | 02 | 2 | UPD-06 | — | Full offline suite green: ≥352 passed + 1 deselected, no hangs | integration | `timeout 300 uv run --no-sync pytest -q` | ✅ verified (7.75s) | ⬜ pending (re-verify) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_update.py` — extend with git-drift scenarios (temp git repos via `subprocess`, mocked GitHub API)
- [ ] `tests/test_update_cache.py` — extend with commit-drift cache round-trip
- [ ] Existing infrastructure covers the rest (hermetic socket-deny fixture in `tests/conftest.py`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real git-clone install behind `main` reports "behind N commits" | UPD-06 | Requires a real clone with an un-fetched remote | Clone the repo at an older commit, run `hermes-brain update --check`, confirm "behind N commits" appears and exit code is 0 |
| Release notes URL opens the correct release page | UPD-07 | Requires a browser / live GitHub | Copy the printed `release:` URL, open it, confirm it lands on the release notes page for the resolved tag |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (post-execute; pre-execute = draft)

**Approval:** pending
