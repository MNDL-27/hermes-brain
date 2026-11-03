# Phase 07 — Update UX: Commit-Level Drift & Release-Notes Link — Context

## Goal
A git-clone install behind `main` by N commits learns about it from `notion_brain update` and from the cached auto-update check; the printed release link lands directly on the canonical GitHub release notes page rather than the repo root.

## Scope & Requirements
- **UPD-06**: Commit-level drift detection between formal tags for git-clone installs (`behind N commits` alerts even when `__version__` is unchanged).
- **UPD-07**: `notion_brain update` and cached auto-update check render the canonical release-notes URL `https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z`.
- Strictly detect + instruct only (`UPD-05`). Never runs `git pull`, `pip install`, or any mutating commands automatically.
- Non-blocking background sync / cache read (`CHK-01..05`). Zero network blocking on startup path.

## Locked Decisions

### Area 1: Commit Drift Comparison Target
- **Target**: Remote default branch (`main`).
- **Method**: Local git command first (`git rev-list --count HEAD..origin/main`), with GitHub API compare endpoint (`/repos/{owner}/{repo}/compare/{sha}...main`) as fallback when remotes are un-fetched.
- **Branch isolation**: Only compute commit drift when checked out on branch `main`. Suppress commit drift on feature branches or detached HEAD to avoid false positives.
- **Divergence**: Support ahead/behind divergence format (`behind by N, ahead by M`).

### Area 2: CLI Exit Codes & Machine-Readable Output
- **Exit codes**:
  - `0`: Up-to-date, or commit-only drift (informational warning printed, but exit 0 so automated scripts checking formal releases are not broken).
  - `2`: Version tag drift detected (upgrade recommended).
- **JSON format (`--json`)**:
  - `drift: true` when either version drift OR commit drift is present.
  - `drift_type`: `"version"`, `"commit"`, or `"both"`.
  - Additional keys: `behind_commits: int`, `ahead_commits: int`.

### Area 3: Banner & Release Notes Presentation (UPD-07)
- Format:
  ```text
  installed: 1.0.3 (behind 3 commits on main)
  latest:    1.1.0  (UPDATE AVAILABLE)
  install:   git_clone
  upgrade:   git -C <dir> fetch --tags && git -C <dir> checkout v1.1.0 && ...
  release:   https://github.com/MNDL-27/hermes-brain/releases/tag/v1.1.0
  ```
- If only commit drift exists (no version drift):
  ```text
  installed: 1.0.3 (behind 3 commits on main)
  latest:    1.0.3  (up to date)
  install:   git_clone
  upgrade:   git -C <dir> pull --ff-only
  ```

### Area 4: Cache & Degradation
- Save `behind_commits` and `ahead_commits` inside `$HERMES_HOME/.update_cache.json`.
- Rate limit (403/429) or offline states degrade silently: fall back to cached data or omit commit drift without raising exceptions.

## Canonical References
- `.planning/REQUIREMENTS.md` (UPD-05, UPD-06, UPD-07)
- `.planning/ROADMAP.md` (Phase 7 definition)
- `notion_brain/update.py` (Version comparison, install mode detection, upgrade command generation)
- `notion_brain/update_cache.py` (TTL-based atomic cache read/write)
