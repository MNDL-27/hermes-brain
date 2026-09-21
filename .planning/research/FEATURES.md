# Feature Research

**Domain:** Python Package Distribution, Release Automation, & Non-Blocking Drift Detection
**Researched:** 2026-09-21
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| PyPI Package Availability & Installation | Standard Python distribution expectation (`pip install hermes-brain`, `uv pip install hermes-brain`). Users should not be forced to clone git repositories to use the package. | LOW | Packaged via setuptools PEP 621, distributed via wheel and sdist to PyPI. |
| Automated Tag-Based PyPI Publishing | Pushing a version tag (e.g. `v1.1.0`) must automatically build, validate, and upload wheels/sdist without manual human intervention. | LOW | GitHub Actions workflow (`.github/workflows/publish.yml`) triggered on `push: tags: ['v*']`. |
| PyPI OIDC Trusted Publishing | Secure PyPI publication without storing long-lived, static API tokens in repository secrets. | LOW | Requires `id-token: write` permission and `pypa/gh-action-pypi-publish@release/v1` with `environment: pypi`. |
| Manual Twine Release Runbook | Offline or emergency distribution fallback when GitHub Actions runners are unavailable or OIDC exchange fails. | LOW | Documented step-by-step procedure: `python -m build`, `twine check dist/*`, and `twine upload dist/*`. |
| Modern SPDX License Declaration | Deprecation warning elimination under modern setuptools (>=77.0.3) and packaging tools adhering to PEP 639. | LOW | Replace deprecated `license = { text = "MIT" }` table with SPDX string `license = "MIT"` in `pyproject.toml`. |
| CLI Update Drift Detection Command | Users running `python -m notion_brain update` expect to know if a newer version exists and how to upgrade. | LOW | Queries GitHub Releases API; compares installed version against remote release tag. |
| Explicit Environment Detection | Update instructions must match how hermes-brain was actually installed (uv, pip venv, pip user, or editable git clone). | MEDIUM | Inspects `pkg_dir / ".git"`, `VIRTUAL_ENV`, and presence of `uv` binary to produce exact copy-paste command. |
| Zero-Latency Startup (<1ms) | Agent initialization (`NotionBrainProvider.initialize()`) must never stall on external network round-trips to GitHub or PyPI. | MEDIUM | Stale-while-revalidate pattern: synchronous read of local cache file (`$HERMES_HOME/.update_cache.json`), background refresh. |
| Machine-Friendly CLI Flags (`--check`, `--json`) | Scripts and CI automation need to check for updates programmatically without parsing human terminal text. | LOW | `--check` exits 0 if current, 2 if update available; `--json` emits structured machine-readable payload. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dual Release Source (Tags & Git Commits) | Developer installs from git clones receive commit-level drift alerts even between formal tag releases. | MEDIUM | Fallback to GitHub commits API or git remote rev-parse if current version is not a tagged release. |
| Tailored Per-Environment Copy-Paste Command | Eliminates confusion by printing the exact shell command needed for user's specific package manager (`uv`, `pip`, or `git pull && pip install -e .`). | MEDIUM | Distinguishes between `uv pip install --upgrade`, global/user pip, virtualenvs, and editable repository clones. |
| Non-Blocking Daemon Worker Dispatch | Automatically keeps update state fresh without adding even 10ms of lag to interactive conversational turns. | LOW | Reuses existing `notion-brain-sync-worker` background queue (`self._sync_queue`) in `NotionBrainProvider`. |
| Atomic, Secure Local Cache Perms (`0o600`) | Prevents multi-user cache snooping and partial file corruption on abnormal process exit or power loss. | LOW | Writes to temporary file `$HERMES_HOME/.update_cache.json.tmp`, applies `chmod 0o600`, and performs atomic filesystem replace. |
| Actionable Update Banners with Direct Release Notes URL | Directs user straight to changelog (`https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z`) to evaluate breaking changes before upgrading. | LOW | Extracted directly from GitHub release metadata and surfaced in CLI and agent logs. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Silent Automatic Self-Modification (`pip install` in running process) | Users want zero-touch auto-updates where the package updates itself in place without running commands. | Modifies byte-code (`.pyc`) and shared libraries in active `sys.path` while Python interpreter is executing. Causes `ImportError`, process corruption, permission crashes under PEP 668 externally-managed environments, and races against active daemon worker threads. Violates explicit project scope constraint. | "Detect + Instruct": Detect drift, output formatted alert banner, and provide exact one-line copy-paste upgrade command. |
| Synchronous GitHub API Calls on Runtime Boot | Developer wants freshest release status immediately on agent start. | Adds 200ms–2500ms network latency to every CLI invocation and agent turn. Blocks agent initialization completely when offline or when GitHub API is degraded. | Stale-while-revalidate: Read local cache JSON in <1ms; dispatch network refresh task asynchronously to background daemon thread if TTL (24h) is expired. |
| Permanent PyPI API Tokens in CI Repository Secrets | Simple to set up initially in GitHub Actions secrets. | Long-lived API tokens can leak, do not expire automatically, require manual rotation, and fail modern security audits. | PyPA OIDC Trusted Publishing (`pypa/gh-action-pypi-publish@release/v1` with `id-token: write`). |
| Bundling Update Cache in `notion_brain.json` | Reuses existing workspace metadata cache file instead of creating another file. | Conflates package distribution state with Notion database IDs. Breaks `notion_brain update` if Notion is unconfigured (`notion_brain.json` missing). Resetting databases (`notion_brain reset --force`) would wipe update cache. Creates concurrency write conflicts with background disk sync workers. | Dedicated, decoupled cache file at `$HERMES_HOME/.update_cache.json`. |
| Synchronous Network Calls in `bootstrap.health_report()` | Health report currently checks update status inline via urllib. | Running `notion_brain health` stalls for 2-3 seconds on slow network or hangs when offline. | Migrate `health_report()` to query `updater.get_cached_update_banner()` backed by the local update cache. |
| Hardcoded Terminal Color Escapes without TTY Check | Colored ASCII boxes look pretty in terminal output. | Mangles output when piped to files, logs, or downstream agent parsers (`TERM=dumb` or `NO_COLOR`). | Check `sys.stdout.isatty()` and respect `NO_COLOR` / `TERM=dumb` conventions. |

---

## Feature Dependencies

```
[PyPI Trusted Publishing]
    └──requires──> [SPDX License Declaration (PEP 639)]
    └──requires──> [GitHub Actions OIDC Workflow (`publish.yml`)]

[CLI `update` Drift Detection]
    └──requires──> [Drift Engine (`updater.py`)]
                       └──requires──> [GitHub Releases API Client (2.5s timeout)]
                       └──requires──> [Installation Type Detector (uv/pip/git)]
                       └──requires──> [Cache Layer (`.update_cache.json`)]

[Non-Blocking Auto-Update Check]
    └──requires──> [Cache Layer (`.update_cache.json`)]
    └──requires──> [Provider Background Worker (`notion-brain-sync-worker`)]
    └──enhances──> [CLI `update` Command]
    └──enhances──> [CLI `health` Command]

[Detect + Instruct Pattern] ──conflicts──> [Silent In-Place Self-Modification]
```

### Dependency Notes

- **`PyPI Trusted Publishing` requires `SPDX License Declaration`:** Modern packaging tools (setuptools >=77) building sdist and wheels validate metadata standards. Deprecated table syntax causes warnings and potential build rejections on PyPI.
- **`CLI update Drift Detection` requires `updater.py` & Cache Layer:** The CLI subcommand delegates all version parsing, GitHub HTTP requests, and environment detection to `updater.py`, caching results to prevent repeated rate-limited API calls.
- **`Non-Blocking Auto-Update Check` requires Provider Background Worker:** Provider `initialize()` enqueues the cache refresh onto `self._sync_queue` so the agent main thread never touches the network for update checks.
- **`Detect + Instruct Pattern` conflicts with `Silent In-Place Self-Modification`:** Silent modification mutates running files; detect + instruct intentionally isolates the update check from environment mutation.

---

## MVP Definition

### Launch With (v1.1)

Minimum viable product for Distribution & Updates milestone.

- [ ] **SPDX License Modernization** — Migrate `pyproject.toml` `license = { text = "MIT" }` to `license = "MIT"` to comply with PEP 639.
- [ ] **PyPI Publishing Workflow (`.github/workflows/publish.yml`)** — Trigger on `v*` tag push with `id-token: write` permissions and `pypa/gh-action-pypi-publish@release/v1`.
- [ ] **Manual Twine Runbook Documentation** — Step-by-step emergency release instructions in `docs/` or `CONTRIBUTING.md`.
- [ ] **Core Drift Engine (`notion_brain/updater.py`)** — GitHub API fetcher (2.5s timeout, secret sanitization), version comparator, and environment detector.
- [ ] **Isolated Local Cache (`$HERMES_HOME/.update_cache.json`)** — Atomic 0o600 file write with 24-hour default TTL.
- [ ] **Overhauled CLI `update` Subcommand** — Replaces git-checkout self-mutation with "Detect + Instruct" output format, `--check`, `--json`, and `--force` flags.
- [ ] **Non-Blocking Provider Integration** — Read cache on boot (<1ms); enqueue stale refresh into `notion-brain-sync-worker` daemon queue.
- [ ] **Offline Unit Test Suite (`tests/test_updater.py`)** — 100% offline tests mocking GitHub API, cache TTL, rate limits, corrupt JSON, and CLI formatting.

### Add After Validation (v1.1.x)

Features to add once core distribution is validated.

- [ ] **Configurable Update TTL via Environment Variable** — Allow `HERMES_UPDATE_CHECK_INTERVAL_HOURS` override for enterprise or offline setups.
- [ ] **CLI Upgrade One-Click Wrapper Script** — Interactive confirmation prompt (`Do you want to run this upgrade command now? [y/N]`) only when invoked interactively in a standalone terminal (never inside agent loop).

### Future Consideration (v2+)

Features deferred to future milestones.

- [ ] **Pre-push Git Hook (`pytest -q`)** — Local pre-push hook running test suite before remote push (TOOL-01).
- [ ] **Scheduled `pre-commit autoupdate` Action** — Weekly CI workflow validating hook version bumps (TOOL-02).
- [ ] **PyPI JSON API Fallback** — Fall back to `pypi.org/pypi/hermes-brain/json` if GitHub API is unreachable or rate-limited.

---

## Detailed Expected Behaviors

### 1. Update Paths & User Experience

| User Install Type | Detection Heuristic | User Sees / Gets | Exact Suggested Command |
|-------------------|---------------------|------------------|-------------------------|
| **uv Virtualenv** | `os.environ.get("VIRTUAL_ENV")` contains `bin/uv` or `uv` is on PATH in venv | Status banner showing current version, latest version, and release notes URL | `uv pip install --upgrade hermes-brain` |
| **Standard venv / pip** | `os.environ.get("VIRTUAL_ENV")` is set, or running in active Python virtualenv | Status banner showing current version, latest version, and release notes URL | `pip install --upgrade hermes-brain` |
| **pip User Install** | Not in venv, installed in `~/.local` or system user directory | Status banner with user flag reminder to avoid permission errors | `pip install --user --upgrade hermes-brain` |
| **Git Clone / Editable** | `(pkg_dir / ".git").is_dir()` | Status banner showing local commit/tag vs remote HEAD, warning if working tree is dirty | `cd <pkg_dir> && git pull --rebase && pip install -e .` |

### 2. Cache TTL & Startup Latency Behavior

- **Startup Latency Contract:** `< 1ms` disk read time. Zero HTTP requests on the main thread.
- **Cache Location:** `$HERMES_HOME/.update_cache.json` (mode `0o600`).
- **Cache Schema:**
  ```json
  {
    "last_checked_at": 1726915200.0,
    "current_version": "1.0.3",
    "latest_version": "1.1.0",
    "latest_commit_sha": "9be1f77d3f82a9918b9557b44588df8e59e3924f",
    "update_available": true,
    "installation_type": "uv",
    "upgrade_command": "uv pip install --upgrade hermes-brain",
    "release_url": "https://github.com/MNDL-27/hermes-brain/releases/tag/v1.1.0"
  }
  ```
- **Stale-While-Revalidate Lifecycle:**
  1. **T = 0s (First Boot / Missing Cache):** Read returns empty. Main thread proceeds immediately without waiting. Enqueues background refresh task to daemon thread queue.
  2. **T = 10s (Worker finishes):** Worker writes JSON to disk atomically.
  3. **T = 1 hour (Subsequent Boot):** Cache age is 3600s (< 86400s). Cache hit. If `update_available: true`, logs single notice: `notion_brain: Update available: 1.0.3 -> 1.1.0. Run: uv pip install --upgrade hermes-brain`. Zero background tasks queued.
  4. **T = 25 hours (Expired TTL):** Cache age is > 86400s. Displays cached status (stale data served immediately), and asynchronously dispatches background refresh to re-validate against GitHub.

### 3. "Detect + Instruct" Output Format

When user runs `python -m notion_brain update`:

#### Output: Update Available
```text
hermes-brain: Update Available
--------------------------------------------------
Current version:  1.0.3
Latest version:   1.1.0
Release notes:    https://github.com/MNDL-27/hermes-brain/releases/tag/v1.1.0
Environment:      uv virtualenv

To upgrade, run:
  uv pip install --upgrade hermes-brain
--------------------------------------------------
```
Exit code: `2` (when `--check` is specified) or `0` (interactive).

#### Output: Already Up to Date
```text
hermes-brain: Up to Date
--------------------------------------------------
Installed version: 1.0.3
Latest release:    1.0.3 (latest)
Repository:        https://github.com/MNDL-27/hermes-brain
--------------------------------------------------
```
Exit code: `0`.

#### Output: Machine Readable (`--json`)
```json
{
  "update_available": true,
  "current_version": "1.0.3",
  "latest_version": "1.1.0",
  "installation_type": "uv",
  "upgrade_command": "uv pip install --upgrade hermes-brain",
  "release_url": "https://github.com/MNDL-27/hermes-brain/releases/tag/v1.1.0",
  "checked_at": 1726915200.0
}
```

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| SPDX License Modernization (`pyproject.toml`) | HIGH | LOW | P1 |
| GitHub Actions OIDC PyPI Publishing (`publish.yml`) | HIGH | LOW | P1 |
| Manual Twine Release Fallback Runbook | MEDIUM | LOW | P1 |
| Core Drift Engine & Cache Layer (`updater.py`) | HIGH | MEDIUM | P1 |
| CLI `update` Subcommand Overhaul (Detect + Instruct) | HIGH | LOW | P1 |
| Non-Blocking Provider Boot Integration (`provider.py`) | HIGH | LOW | P1 |
| Unit & Offline Characterization Tests (`test_updater.py`) | HIGH | MEDIUM | P1 |
| Machine-Readable CLI Output (`--json`) | MEDIUM | LOW | P2 |
| Configurable TTL via Environment Variable | LOW | LOW | P2 |
| Scheduled Pre-Commit Autoupdate (TOOL-02, v2) | MEDIUM | LOW | P3 |
| Optional Pre-Push Test Hook (TOOL-01, v2) | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for v1.1 milestone launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration (v2)

---

## Competitor & Ecosystem Feature Analysis

| Feature | pip / pipx | Homebrew CLI Tools | hermes-brain v1.1 Approach |
|---------|------------|--------------------|----------------------------|
| **Update Notification** | Checks PyPI on invocation; prints notice at end of stderr | Checks git / tap index on command execution; prints notice | Synchronous local cache check (<1ms) on boot; background daemon refresh |
| **Upgrade Execution** | Requires explicit user command (`pip install -U ...`) | Requires explicit user command (`brew upgrade ...`) | "Detect + Instruct": Prints exact per-environment command for copy-paste |
| **Self-Modification** | Never self-modifies running binary; requires wrapper/runner | Never self-modifies running process | Explicit anti-feature: strictly avoids in-process virtualenv mutation |
| **Packaging Publishing** | PyPA Trusted Publishing via OIDC | Release bottle upload via GitHub Actions | PyPA Trusted Publishing via GitHub Actions OIDC (`publish.yml`) |
| **Cache Storage** | Dedicated cache directory (`~/.cache/pip`) | Local cache tap directory | Isolated JSON file (`$HERMES_HOME/.update_cache.json`, mode 0o600) |

---

## Sources

- PyPA Trusted Publishing Specification: https://docs.pypi.org/trusted-publishers/
- PyPA Sample Project Release Workflow: https://deepwiki.com/pypa/sampleproject/3-continuous-integration
- PEP 639 – Improving License Expression in pyproject.toml: https://peps.python.org/pep-0639/
- Python Packaging User Guide (Declaring License): https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- Hermes Brain Codebase Architecture: `notion_brain/provider.py`, `notion_brain/__main__.py`, `notion_brain/bootstrap.py`

---
*Feature research for: Python Package Distribution, Release Automation, & Non-Blocking Drift Detection*
*Researched: 2026-09-21*
