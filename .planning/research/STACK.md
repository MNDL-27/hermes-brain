# Stack Research

**Domain:** Python Package Distribution, Release Automation & CLI Drift Detection
**Researched:** 2026-09-21
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python Standard Library** (`json`, `pathlib`, `urllib.request`, `re`, `os`) | `>=3.11,<3.14` | Local update cache storage, atomic JSON writes, version tuple parsing, and daemon-thread network checks | Zero new runtime dependencies. `json` + `pathlib.Path` + `os.replace` provide atomic cache persistence. SemVer/PEP 440 parsing for `X.Y.Z` tags is trivial with regex tuple comparison. |
| **`requests`** | `>=2.28` (locked `2.34.2`) | Existing HTTP client across `notion_brain` | Already the sole runtime dependency. Available for GitHub API calls with timeouts, custom headers (`User-Agent`, `Accept`), and error handling if preferred over `urllib.request`. |
| **GitHub Actions OIDC** (`id-token: write`) | v1 / OIDC standard | Cryptographic identity exchange between GitHub Actions and PyPI | Eliminates long-lived PyPI API tokens stored in repository secrets. Token is ephemeral, scoped exclusively to `refs/tags/v*` and the specific workflow. |
| **`pypa/gh-action-pypi-publish`** | `release/v1` | Official PyPA GitHub Action for PyPI uploads via Trusted Publishing | Official PyPA distribution upload action. Automatically requests OIDC token from GitHub, exchanges with PyPI for short-lived token, generates Sigstore digital attestations, and uploads wheels/sdists. |
| **`setuptools`** | `>=77.0.3` | Build backend supporting PEP 639 SPDX license expressions | setuptools 77.0.3 introduced formal support for PEP 639 string-based `license = "SPDX"` in `pyproject.toml`. Eliminates deprecated `license = { text = "..." }` table without deprecation warnings. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **`actions/upload-artifact`** | `v4` | Shares built distributions from `build` job to `publish` job | In `.github/workflows/publish.yml` to preserve artifact immutability between build and publish stages. |
| **`actions/download-artifact`** | `v4` | Retrieves distributions in `publish` job | In `.github/workflows/publish.yml` prior to invoking `pypa/gh-action-pypi-publish`. |
| **`build`** | `1.5.0` (existing dev dep) | PEP 517 build frontend | Used in CI build job (`python -m build`) to generate wheel and sdist in `dist/`. |
| **`twine`** | `6.2.0` (existing dev dep) | Distribution metadata linter and manual upload fallback | Used in CI to run `twine check --strict dist/*`. Used by maintainers for manual emergency release fallback with API tokens. |

### Development & Maintenance Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **`uv`** | Fast local virtualenv, lockfile management, build runner | Lockfile revision 3 already committed (`uv.lock`). Run `uv run --no-sync python -m build` and `uv run --no-sync twine check dist/*`. |
| **`pytest` + `pytest-cov`** | Offline unit test execution | Mock GitHub API responses via `monkeypatch` and cache file paths via `tmp_path`. Must maintain 100% offline test reliability. |
| **`ruff`** (`0.16.0`) | Formatting and linting | Enforces imports and formatting in any new or modified modules (`bootstrap.py`, `__main__.py`). |
| **`mypy`** (`2.3.0`) | Strict static type checking | Enforces `str | None`, `Path`, and JSON dict typing for cache and update functions. |

## Installation

No new runtime dependencies are added to `pyproject.toml`.

```bash
# Core runtime: unchanged
# Only requests>=2.28 remains in dependencies

# Dev dependencies: already pinned in pyproject.toml [project.optional-dependencies]
uv pip install -e ".[dev]"
```

Build-system configuration update in `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=77.0.3"]
build-backend = "setuptools.build_meta"

[project]
name = "hermes-brain"
version = "1.0.3"
description = "Persistent long-term memory for the Hermes AI agent ecosystem — turns Notion into a structured brain that never forgets."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.11,<3.14"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **Stdlib tuple/regex version comparison** | `packaging>=24.0` (`packaging.version.Version`) | `packaging` is superior if supporting complex version ranges (e.g. `~=`, PEP 508 specifiers) or arbitrary pre-release/post-release alpha combinations. For `hermes-brain`, releases follow standard SemVer `vX.Y.Z`. Adding `packaging` violates the zero-additional-runtime-dep rule for 5 lines of code. |
| **Ephemeral `$HERMES_HOME/.update_cache.json` with 24h TTL** | Live API check on startup / turn sync | Live check is acceptable only when user explicitly invokes `hermes-brain update` or `hermes-brain health`. For agent startup, live checks introduce 200–2000ms latency and blow through GitHub's unauthenticated 60 req/hr rate limit. |
| **GitHub Actions OIDC (Trusted Publishing)** | Long-lived PyPI API token in GitHub Secrets | Legacy PyPI token is used only if PyPI organization policy forbids OIDC or for manual offline maintenance scripts via `twine upload`. OIDC is the PyPA standard and eliminates secret leakage risk. |
| **Detect + Instruct UX in `notion_brain update`** | Auto-in-place `git pull` + `pip install` | In-place self-modification was attempted in v1.0 but causes virtual environment corruption, permission errors on root-owned installs, and breakages in containerized or git-submodule deployments. |
| **GitHub REST Tags/Releases API** | PyPI JSON API (`https://pypi.org/pypi/hermes-brain/json`) | PyPI API only tracks PyPI releases. Many Hermes agent users run directly from git clones or release tags. GitHub API catches both git and PyPI releases simultaneously. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Adding `packaging` to `dependencies`** | Unnecessary runtime dependency. Python stdlib does not include `packaging` (distutils was removed in 3.12, packaging is PyPA third-party). | Stdlib regex `re.findall(r"\d+", version)` or integer tuple comparison `tuple(map(int, ver.lstrip("v").split(".")[:3]))`. |
| **Unauthenticated live GitHub API checks on agent startup** | GitHub limits unauthenticated requests to **60 requests per hour per IP**. Multi-agent loops or frequent CLI invocations quickly trigger HTTP 403 `rate limit exceeded`. | Read local `$HERMES_HOME/.update_cache.json`. Only refresh cache in background worker if cache age exceeds TTL (default 24h). |
| **Silent self-updating (`subprocess.run(["git", "pull"])`)** | Corrupts running interpreter state, fails on immutable containers, breaks package manager ownership (pip vs uv vs apt). | Print clean, copy-pasteable instructions (`pip install -U hermes-brain` or `git checkout <tag>`). |
| **`pypa/gh-action-pypi-publish@master`** | The `master` branch of the PyPA publish action has been sunset and disabled. | Use `pypa/gh-action-pypi-publish@release/v1`. |
| **Global `permissions: id-token: write` in GitHub workflow** | Grants privilege escalation permissions to all jobs, including build and test jobs that run arbitrary user or PR code. | Set `permissions: id-token: write` strictly inside the isolated `publish` job, with `needs: build`. |
| **Deprecated `license = { text = "MIT" }` table** | Deprecated by PEP 621 / PEP 639. Triggers deprecation warnings in newer packaging toolchains. | `license = "MIT"` string expression with `setuptools>=77.0.3`. |
| **`pip` or `twine` in runtime `dependencies`** | Packaging tools belong in build environments (`[project.optional-dependencies].dev`), not in end-user agent runtimes. | Keep runtime dependencies strictly limited to `requests>=2.28`. |

## Stack Patterns by Variant

**If running CLI `hermes-brain update`:**
- Check cache first; if `--check` flag is passed, evaluate cached or perform immediate one-off query to GitHub API.
- Print current version vs latest remote version.
- If current < latest, output tailored command:
  - If `.git` directory exists at package root: `git -C <path> fetch --tags && git -C <path> checkout <tag>`
  - Otherwise: `pip install --upgrade hermes-brain` (or `uv pip install -U hermes-brain` if uv detected).
- Exit 0 on success (or exit 2 on drift if used as a check gate in scripts).

**If running inside Hermes Agent daemon loop (`NotionBrainProvider`):**
- On provider initialization or turn sync:
  - Read `$HERMES_HOME/.update_cache.json`.
  - If missing or `time.time() - last_checked > 86400`:
    - Dispatch background task to existing `_sync_queue` (`notion-brain-sync-worker`).
    - Worker executes GitHub tag fetch with 3.0s timeout and standard headers.
    - Atomically write updated cache JSON.
  - Zero blocking on foreground turn processing.

**If GitHub API rate limit (403) or network failure occurs:**
- Catch exception silently (`raise ... from None` or `logger.debug`).
- Touch cache timestamp with exponential backoff (e.g. defer next check by 1 hour) so failing calls do not retry on every turn.
- Never raise to user or Hermes agent.

## Version Compatibility

| Package / Tool | Compatible With | Notes |
|----------------|-----------------|-------|
| `setuptools>=77.0.3` | PEP 639 (`license = "MIT"`) | Earlier setuptools versions (`<77.0.3`) fail when `license` is a string instead of a table. |
| `pypa/gh-action-pypi-publish@release/v1` | `actions/upload-artifact@v4` / `download-artifact@v4` | Must download artifacts into `dist/` before running the publish action. |
| `Python 3.11, 3.12, 3.13` | CPython stdlib `json`, `pathlib`, `urllib.request` | Fully compatible across all supported Python versions without deprecation warnings. |
| `requests>=2.28` | `urllib3 2.x` | Handled via existing `uv.lock`. |

## Sources

- `/pypa/packaging.python.org` — Verified PEP 639 specification, `license` SPDX expression syntax, and `setuptools>=77.0.3` requirement.
- `pypa/gh-action-pypi-publish` README (`gh api repos/pypa/gh-action-pypi-publish/readme`) — Verified `release/v1`, `id-token: write` permission, separate `build` and `publish` jobs, and `environment: pypi`.
- PyPI Trusted Publishers Guide (`docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/`) — Verified pending publisher workflow, GitHub owner/repo/workflow/environment fields.
- GitHub REST API Rate Limit Documentation — Verified unauthenticated rate limit of 60 req/hr per IP and `x-ratelimit-*` response headers.

---
*Stack research for: hermes-brain v1.1 Distribution & Updates*
*Researched: 2026-09-21*
