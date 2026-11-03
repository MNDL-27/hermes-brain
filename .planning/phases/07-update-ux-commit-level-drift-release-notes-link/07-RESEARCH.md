# Phase 7: Update UX — Commit-Level Drift & Release-Notes Link — Research

**Researched:** 2026-10-15
**Domain:** Git plumbing, GitHub REST API commit comparisons, TTL update caching, CLI drift reporting
**Confidence:** HIGH

<user_constraints>
## User Constraints (from REQUIREMENTS.md, ROADMAP.md, and 07-CONTEXT.md)

### Locked Decisions

- **UPD-06 (locked):** Commit-level drift detection between formal tags so git-clone installs see "behind N commits" alerts even when `__version__` is unchanged.
- **UPD-07 (locked):** `notion_brain update` and the cached auto-update check render the canonical release-notes URL `https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z`, copy-pasteable and derived from the same tag the drift check resolves.
- **UPD-05 (locked, carried):** Strictly detect + instruct only. Never runs `git pull`, `pip install`, or any mutating commands automatically.
- **CHK-01..05 (locked, carried):** Non-blocking background worker / cache read. Zero network blocking on the startup path (`<1ms` cache load).
- **Comparison target (locked in 07-CONTEXT.md D-01..D-04):**
  - Target branch is remote default branch `main`.
  - Calculation attempts local fast git command first (`git rev-list --count HEAD..origin/main`), falling back to GitHub Compare API (`/repos/{owner}/{repo}/compare/{local_sha}...main`) when remote tracking branch is absent or un-fetched.
  - Only computed when local checkout is on `main`. Suppress commit drift on feature branches or detached `HEAD`.
  - Supports divergence reporting (`ahead by N, behind by M`).
- **CLI exit codes & JSON schema (locked in 07-CONTEXT.md D-05..D-06):**
  - `hermes-brain update --check` exits `0` when only commit drift exists (informational warning). Exit code `2` reserved for formal version tag mismatches.
  - In `--json` output, `drift: true` is emitted with `drift_type: "commit"` when local commits are behind remote `main` while `__version__` matches. If both version and commit drift exist, `drift_type: "version"` takes precedence with exit code `2`.
- **Cache & offline tolerance (locked in 07-CONTEXT.md D-09..D-10):**
  - Commit drift metrics (`behind_commits`, `ahead_commits`) are stored inside `$HERMES_HOME/.update_cache.json`.
  - Rate limits (403/429) or offline states degrade gracefully with zero startup overhead or unhandled exceptions.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **UPD-06** | Commit-level drift detection for git-clone installs | Local `git -C <repo_dir> rev-parse --abbrev-ref HEAD`, `git -C <repo_dir> rev-list --count HEAD..origin/main`, plus unauthenticated GitHub Compare API fallback. |
| **UPD-07** | Direct release-notes URL in banners | `https://github.com/{owner}/{repo}/releases/tag/v{latest_version}` constructed and printed across CLI formatters and cache payloads. |

</phase_requirements>

## Summary

Phase 07 extends `notion_brain/update.py` and `notion_brain/update_cache.py` to give git-clone users clear visibility into unpulled commits on `main` and direct release notes access, without violating any prior safety constraints.

1. **Git Plumbery in `notion_brain/update.py`**:
   - `detect_git_drift(repo_dir: Path | None) -> dict[str, Any]`:
     - Checks if `repo_dir` is a valid git repository via `git -C <repo_dir> rev-parse --is-inside-work-tree`.
     - Verifies current branch via `git -C <repo_dir> rev-parse --abbrev-ref HEAD`. If not `main`, returns no drift (`branch: <name>`, `skipped: true`).
     - Tries local git count: `git -C <repo_dir> rev-list --left-right --count HEAD...origin/main`. If `origin/main` exists, parses `ahead\tbehind`.
     - If local tracking branch is missing or stale, fetches local commit SHA `git -C <repo_dir> rev-parse HEAD` and queries GitHub Compare API: `GET https://api.github.com/repos/MNDL-27/hermes-brain/compare/{local_sha}...main` (using standard urllib with 2.5s timeout). GitHub's response provides `ahead_by` and `behind_by` directly.
2. **Release Notes URL in `notion_brain/update.py`**:
   - For any resolved tag `vX.Y.Z`, constructs canonical release notes link `https://github.com/MNDL-27/hermes-brain/releases/tag/v{latest}`.
   - Formats human output cleanly with `release: <url>`.
3. **Cache Storage in `notion_brain/update_cache.py`**:
   - Augmented cache schema:
     ```json
     {
       "current": "1.0.3",
       "latest": "1.1.0",
       "drift": true,
       "drift_type": "version",
       "install_mode": "git_clone",
       "behind_commits": 3,
       "ahead_commits": 0,
       "release_url": "https://github.com/MNDL-27/hermes-brain/releases/tag/v1.1.0",
       "checked_at": 1729000000
     }
     ```
   - Refresh worker performs git check inside the background thread, surviving offline and rate-limited environments.
4. **CLI Entrypoint in `notion_brain/__main__.py`**:
   - `_cmd_update()` evaluates `result.get("drift_type")`: exits `2` if version drift is present; exits `0` if only commit drift or no drift.

## Standard Stack

| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| **git CLI** | system | Local branch and commit counts | Zero runtime dependencies; standard for git clones |
| **urllib.request** | stdlib | Unauthenticated GitHub API calls | Standard across `notion_brain/bootstrap.py` and `update.py` |
| **pytest** | 9.1.1 | Unit testing | Standard runner with offline socket-deny compatibility |

## Validation Architecture

The test suite must maintain strict offline hermeticity (socket-deny fixture). All git subprocess invocations and GitHub API requests must be unit-tested using `unittest.mock` and temporary git repositories.

### Quick run command
`uv run --no-sync pytest tests/test_update.py tests/test_update_cache.py -q`

### Key Test Scenarios
1. **Local git count clean**: Repo on `main`, `origin/main` available, behind 3 commits -> `drift: true`, `drift_type: "commit"`, `behind: 3`. Exit code 0.
2. **GitHub API compare fallback**: Repo on `main`, `origin/main` missing -> queries compare API, parses JSON, returns `behind: 3`.
3. **Non-main branch skipped**: Repo on `feature-1` -> commit drift skipped, `behind: 0`.
4. **Both version and commit drift**: Behind 3 commits AND version is `1.0.3` vs `1.1.0` -> `drift: true`, `drift_type: "version"`, exit code 2.
5. **Release notes URL populated**: Tag `1.1.0` -> release URL `https://github.com/MNDL-27/hermes-brain/releases/tag/v1.1.0`.
6. **Offline / Rate limit tolerance**: 403 or network failure during git compare -> returns `behind: 0` without exception.
