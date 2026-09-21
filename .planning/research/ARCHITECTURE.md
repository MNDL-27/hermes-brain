# Architecture Research: Distribution & Auto-Update Subsystem

**Domain:** Python Package Distribution, Release Automation, & Non-Blocking Drift Detection
**Researched:** 2026-09-21
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Remote Release Plane                             │
├──────────────────────────────────────┬──────────────────────────────────────┤
│          GitHub Releases & Tags      │               PyPI Registry          │
│        `MNDL-27/hermes-brain` (v*)   │         `pypi.org/p/hermes-brain`    │
└──────────────────┬───────────────────┴──────────────────▲───────────────────┘
                   │                                      │ OIDC Trusted Publish
                   │ Public API (unauthenticated)         │ (`id-token: write`)
                   ▼                                      │
┌─────────────────────────────────────────────────────────┴───────────────────┐
│                       Continuous Integration / Deployment                   │
│                         `.github/workflows/publish.yml`                     │
│         (Trigger: `push: tags: ['v*']` -> `pypa/gh-action-pypi-publish`)    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         Hermes Brain Package Boundary                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  CLI Entry (`__main__.py`)            Provider Facade (`provider.py`)       │
│  `python -m notion_brain update`      Background Worker (`queue.Queue`)     │
│  - Interactive / force check          - Daemon thread: non-blocking         │
│  - Detect install type (uv/pip/git)   - Zero startup latency                │
│  - Print exact upgrade instructions   - Logs notice on drift                │
└──────────────────┬──────────────────────────────────────┬───────────────────┘
                   │                                      │
                   ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Update & Drift Engine (`updater.py` [NEW])               │
├─────────────────────────────────────────────────────────────────────────────┤
│  - `get_update_info(home, ttl=86400, force=False)`                          │
│  - `fetch_latest_remote()`: `requests.get` (2.5s timeout, secret redaction) │
│  - `detect_installation_type()`: uv / pip / git_clone / editable           │
│  - `format_upgrade_command()`: exact copy-paste CLI string                  │
└──────────────────┬──────────────────────────────────────▲───────────────────┘
                   │                                      │
                   │ Cache Read / Atomic Write (0o600)    │
                   ▼                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Local Filesystem Cache                          │
├──────────────────────────────────────┬──────────────────────────────────────┤
│     Update Cache [ISOLATED]          │      Workspace Metadata [EXISTING]   │
│   `$HERMES_HOME/.update_cache.json`  │    `$HERMES_HOME/notion_brain.json`  │
│   - `last_checked_at` (unix epoch)   │    - `parent_page_id`                │
│   - `latest_version` & `commit`      │    - `db_<name>` database IDs        │
│   - `upgrade_command` string         │    - `disk_sync_hash`                │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### Component Responsibilities

| Component | Status | Responsibility | Implementation Details |
|-----------|--------|----------------|------------------------|
| `notion_brain/updater.py` | **NEW** | Remote GitHub release fetching, drift detection, install environment detection, and update command generation | Uses `requests.get` with 2.5s timeout; reads/writes `$HERMES_HOME/.update_cache.json`; sanitizes error strings |
| `.github/workflows/publish.yml` | **NEW** | Automated PyPI package build and release upload on git tag push | GitHub Actions with OIDC Trusted Publishing (`id-token: write`), uses `pypa/gh-action-pypi-publish@release/v1` |
| `notion_brain/__main__.py` | **MODIFIED** | CLI interface for `update` subcommand | Replaces self-mutation with `updater.py` integration; formats status, release notes URL, and upgrade command; supports `--check` and `--json` |
| `notion_brain/provider.py` | **MODIFIED** | Agent runtime integration; non-blocking background check dispatch | In `initialize()`, checks cache (0ms network delay); if stale, enqueues background check to existing `notion-brain-sync-worker` queue |
| `notion_brain/bootstrap.py` | **MODIFIED** | Deprecate in-file update helpers; route `health_report()` update check to `updater.py` | Aliases `_check_for_update()` and `_find_latest_tag()` to `updater.py` for backward compatibility |
| `pyproject.toml` | **MODIFIED** | Package build metadata modernization | Migrates `license = { text = "MIT" }` to SPDX expression string `license = "MIT"` (PEP 639 standard) |
| `tests/test_updater.py` | **NEW** | Unit and contract tests for drift detection, cache TTL, and command generation | 100% offline; mocks `requests.get` responses; tests cache expiration, invalid JSON, network errors, and CLI formatting |

---

## Recommended Project Structure

```
hermes-brain/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Existing: test, coverage, quality-debt, package build
│       └── publish.yml               # NEW: PyPI publishing on v* tags via OIDC Trusted Publishing
├── notion_brain/
│   ├── __init__.py                   # Package exports & __version__ = "1.0.3"
│   ├── __main__.py                   # MODIFIED: CLI subcommands; update subcommand refactored
│   ├── bootstrap.py                  # MODIFIED: Workspace setup; delegates update check to updater.py
│   ├── config_schema.py              # Desktop UI settings schema (unmodified)
│   ├── extract.py                    # Dialogue memory extraction (unmodified)
│   ├── helpers.py                    # Markdown parsing & text helpers (unmodified)
│   ├── provider.py                   # MODIFIED: Provider facade; enqueues update check in worker
│   ├── schema.py                     # Schema, constants, secret redaction (unmodified)
│   ├── schemas.py                    # Hermes tool definitions (unmodified)
│   ├── store.py                      # Notion REST client (unmodified)
│   └── updater.py                    # NEW: Drift engine, cache manager, upgrade command builder
├── tests/
│   ├── conftest.py                   # Pytest fixtures & stubs
│   ├── test_bootstrap_schema.py      # Updated: tests for bootstrap shims
│   ├── test_cli_contract.py          # Updated: tests for `update` CLI subcommand flags
│   └── test_updater.py               # NEW: Offline tests for updater.py (mocking GitHub API)
├── pyproject.toml                    # MODIFIED: SPDX license migration; build system config
└── uv.lock                           # Locked dependencies
```

### Structure Rationale

- **Dedicated `notion_brain/updater.py` vs bloated `bootstrap.py`:** `bootstrap.py` is >800 lines dedicated to Notion workspace hierarchy, database properties, status select validation, and schema drift repair. Extracting update checking to `updater.py` adheres to the Single Responsibility Principle and eliminates circular dependencies.
- **Isolated `.github/workflows/publish.yml` vs extending `ci.yml`:** PyPI publishing requires elevated OIDC permissions (`id-token: write`) and strict release environment constraints. Keeping publish logic in a dedicated tag-triggered workflow (`push: tags: ['v*']`) prevents PR builds or standard branch pushes from requesting ambient OIDC tokens.
- **Dedicated `tests/test_updater.py`:** Mirrors `test_store.py` and `test_config_schema.py` isolation. Allows testing all drift permutations, cache states, and network failure modes offline without running live Notion or GitHub network calls.

---

## Architectural Patterns

### Pattern 1: Ephemeral File-Based TTL Cache with Atomic Permitted Writes

**What:** Update checks query GitHub's public API and persist a lightweight JSON document containing the check timestamp, remote version, latest commit SHA, and suggested upgrade command. Subsequent checks verify the TTL (default: 24 hours / 86,400s) before issuing HTTP calls.

**When to use:** Every runtime initialization and standard CLI health check where network round-trips would induce startup latency.

**Trade-offs:** Stale notifications for up to TTL duration; mitigated by allowing `--force` on CLI or passing `force=True` programmatically.

**Example:**
```python
# notion_brain/updater.py
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

CACHE_FILENAME = ".update_cache.json"
DEFAULT_TTL_SECONDS = 86400  # 24 hours


def load_update_cache(home: Path) -> dict[str, Any]:
    cache_file = home / CACHE_FILENAME
    try:
        if cache_file.is_file():
            return json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_update_cache(home: Path, data: dict[str, Any]) -> None:
    cache_file = home / CACHE_FILENAME
    tmp_file = home / f"{CACHE_FILENAME}.tmp"
    try:
        home.mkdir(parents=True, exist_ok=True)
        tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp_file, 0o600)
        except OSError:
            pass
        tmp_file.replace(cache_file)
        try:
            os.chmod(cache_file, 0o600)
        except OSError:
            pass
    except Exception:
        pass  # Never crash host application on cache write failure
```

---

### Pattern 2: Non-Blocking Background Dispatch via Producer-Consumer Worker Queue

**What:** When `NotionBrainProvider.initialize()` runs, it immediately reads the local update cache. If the cache is missing or expired, it does NOT make a synchronous network call. Instead, it places an `(updater.get_update_info, (home, True), {})` task onto the existing background sync queue (`self._sync_queue`), consumed by the daemon thread `notion-brain-sync-worker`.

**When to use:** Inside long-lived daemon runtimes (Hermes Agent framework) to guarantee sub-millisecond provider initialization.

**Trade-offs:** The current session will not see an update banner until the worker finishes and writes to disk; next session or next health check will display it. This is the optimal trade-off for interactive AI agent responsiveness.

**Example:**
```python
# notion_brain/provider.py
def initialize(self, session_id: str, **kwargs) -> None:
    ...
    # Non-blocking update check: read local cache synchronously (0 network delay)
    cached_banner = updater.get_cached_update_banner(Path(self._hermes_home))
    if cached_banner:
        logger.info("notion_brain: %s", cached_banner)

    # If TTL expired, dispatch background fetch onto the worker thread
    if updater.is_cache_stale(Path(self._hermes_home)):
        self._sync_queue.put((updater.refresh_update_cache, (Path(self._hermes_home),), {}))
        self._ensure_worker_running()
```

---

### Pattern 3: "Detect & Instruct" CLI Execution Pattern

**What:** The CLI command `python -m notion_brain update` checks for drift against remote tags/commits, determines the host installation method (pip user install, uv virtual environment, or editable git clone), and prints the exact upgrade command for the user to copy-paste or execute. It explicitly avoids self-modifying the active Python environment.

**When to use:** For all update commands in CLI and library tools where mutating a running virtualenv or system site-packages can cause binary corruption, race conditions with running daemons, or permission failures.

**Trade-offs:** Requires one manual step from the user instead of fully autonomous self-update; guarantees zero runtime process corruption.

**Example:**
```python
# notion_brain/updater.py
def detect_installation_type(pkg_dir: Path) -> str:
    if (pkg_dir / ".git").is_dir():
        return "git_clone"
    if os.environ.get("VIRTUAL_ENV"):
        if (Path(os.environ["VIRTUAL_ENV"]) / "bin" / "uv").is_file():
            return "uv"
        return "venv_pip"
    return "pip_user"


def get_upgrade_command(install_type: str, pkg_dir: Path) -> str:
    if install_type == "git_clone":
        return f"cd {pkg_dir} && git pull --rebase && pip install -e ."
    if install_type == "uv":
        return "uv pip install --upgrade hermes-brain"
    return "pip install --upgrade hermes-brain"
```

---

### Pattern 4: OIDC Trusted Publishing without Long-Lived Credentials

**What:** Continuous deployment pipeline exchanges short-lived, cryptographically signed GitHub Actions OpenID Connect (OIDC) tokens for ephemeral PyPI upload tokens, removing static API tokens from repository secrets.

**When to use:** PyPI distribution workflow on release tag push.

**Trade-offs:** Requires configuring PyPI Trusted Publisher in pypi.org web interface beforehand; eliminates credential leakage and token expiration maintenance.

**Example:**
```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: read

jobs:
  build-n-publish:
    name: Build distribution and publish to PyPI
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # Mandatory for PyPI Trusted Publishing (OIDC)
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install build tools
        run: python -m pip install --upgrade build twine
      - name: Build wheel and sdist
        run: python -m build
      - name: Verify package metadata
        run: twine check dist/*
      - name: Publish package distributions to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

---

## Data Flow

### Request Flow: CLI Update Subcommand

```
[User invokes: python -m notion_brain update]
    │
    ▼
[notion_brain/__main__.py:_cmd_update()]
    │
    ▼
[notion_brain/updater.py:check_drift(force=True)]
    │
    ├─► Read current version: notion_brain.__version__
    │
    ├─► HTTP GET https://api.github.com/repos/MNDL-27/hermes-brain/releases/latest (timeout=2.5s)
    │     │
    │     ├── (Network Success 200) ──► Extract tag_name (e.g. "v1.1.0"), release URL
    │     └── (Network Failure/Offline) ► Fall back to cached info or git commit drift
    │
    ├─► Compare versions / commits: current vs remote
    │
    ├─► Inspect runtime: detect uv, pip, or git_clone
    │
    ├─► Write result to $HERMES_HOME/.update_cache.json (atomic 0o600)
    │
    ▼
[Format & Output to stdout]
    - Status: "Update available: 1.0.3 -> 1.1.0"
    - Release Notes: "https://github.com/MNDL-27/hermes-brain/releases/tag/v1.1.0"
    - Action: "Run: uv pip install --upgrade hermes-brain"
```

### Background Auto-Update Check Flow

```
[Hermes Agent boots: NotionBrainProvider.initialize()]
    │
    ├─► Step 1: Read $HERMES_HOME/.update_cache.json synchronously (< 1ms)
    │     └── If update_available == true:
    │           logger.info("Hermes Brain update available: %s -> %s", cur, latest)
    │
    ├─► Step 2: Check cache age: (now - last_checked_at) > 86400s?
    │     │
    │     ├── NO (Cache Fresh): Continue immediate startup. Zero network I/O.
    │     │
    │     └── YES (Cache Stale / Missing):
    │           Put task (updater.refresh_update_cache) onto self._sync_queue
    │
    ▼ [Provider initialization completes in < 5ms]
[Agent processes user prompts normally]
    │
    ▼ [Asynchronously in daemon thread: notion-brain-sync-worker]
[Worker dequeues refresh task]
    ├─► requests.get GitHub releases API (timeout=2.5s)
    ├─► Atomic write to $HERMES_HOME/.update_cache.json
    └─► Completes silently without interrupting agent loop
```

### State Management: `$HERMES_HOME/.update_cache.json`

The update cache stores the following JSON schema:

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

---

## Cache File Storage Decision: Separate File vs `notion_brain.json`

### Evaluation Matrix

| Criterion | Option A: In `$HERMES_HOME/notion_brain.json` | Option B: Separate `$HERMES_HOME/.update_cache.json` [CHOSEN] |
|-----------|------------------------------------------------|---------------------------------------------------------------|
| **Domain Coupling** | **High (Bad):** Conflates remote package distribution metadata with remote Notion workspace IDs | **Zero (Good):** Update tracking is independent of Notion workspace configuration |
| **Pre-Bootstrap Usability** | **Fails:** If user runs `python -m notion_brain update` before setting `NOTION_API_KEY`, `notion_brain.json` does not exist | **Passes:** Operates seamlessly even if Notion is completely unconfigured |
| **Write Concurrency** | **Unsafe:** Background sync worker writing disk sync hashes can race against CLI or background thread updating check TTL | **Safe:** Dedicated file updated independently; zero contention with workspace DB ID rebinding |
| **Lifecycle & Reset** | **Coupled:** Running `notion_brain reset --force` or wiping databases would destroy update check TTLs | **Decoupled:** Workspace resets leave package update cache intact |
| **File Permissions** | `0o600` via existing `_save_cache` | `0o600` via dedicated atomic write helper |

**Decision:** Option B. Update cache MUST live in `$HERMES_HOME/.update_cache.json`.

---

## Offline Testing Strategy

To adhere to the ironclad constraint ("CI Reliability: Unit tests must run offline without requiring live Notion API credentials or a live Hermes daemon"):

1. **No External Network Calls:** `notion_brain/updater.py` network operations MUST use standard `requests.get`. Tests mock this via `pytest`'s `monkeypatch` fixture, following the exact precedent in `tests/test_store.py:205`.
2. **Mock Factory Helper:**
   ```python
   # tests/test_updater.py
   class MockResponse:
       def __init__(self, json_data: Any, status_code: int = 200, ok: bool = True):
           self._json = json_data
           self.status_code = status_code
           self.ok = ok
           self.reason = "OK" if ok else "Error"

       def json(self):
           return self._json

   def test_update_check_detects_newer_version(monkeypatch, tmp_path):
       monkeypatch.setattr(
           "requests.get",
           lambda *a, **k: MockResponse([{"name": "v1.1.0", "target_commitish": "main"}])
       )
       info = updater.get_update_info(home=tmp_path, force=True)
       assert info["update_available"] is True
       assert info["latest_version"] == "1.1.0"
   ```
3. **Failure Scenarios to Validate Offline:**
   - HTTP 403 (GitHub API rate limit exceeded): gracefully returns `None` or cached info without crashing.
   - `requests.Timeout` / `requests.ConnectionError`: catches exception, logs debug, returns cached state.
   - Corrupt JSON in `$HERMES_HOME/.update_cache.json`: safely ignores and treats as cache miss.
   - Read-only filesystem for cache path: catches `OSError` without raising to caller.

---

## Anti-Patterns

### Anti-Pattern 1: In-Place Virtualenv Self-Modification (`subprocess pip install`)

**What people do:** The `update` CLI runs `subprocess.run(["pip", "install", "--upgrade", "hermes-brain"])` or `git pull && pip install -e .` directly inside the running process.
**Why it's wrong:**
1. Modifying `.pyc` and `.so` files in an active `sys.path` while Python modules are loaded causes `ImportError`, partially executed state, and crashes on Linux/WSL2.
2. If the user installed via `uv tool`, `pipx`, or system apt/dnf, running `pip` corrupts the wrapper environment or triggers PEP 668 externally-managed-environment errors.
3. Violates project requirements ("Out of Scope: Silent automatic self-modification in `notion_brain update`").
**Do this instead:** Detect host environment type and print the exact upgrade command with clear visual formatting.

### Anti-Pattern 2: Synchronous Network Calls on Agent Startup / Provider `initialize()`

**What people do:** Issuing `requests.get("https://api.github.com/...")` inside `NotionBrainProvider.__init__()` or `initialize()`.
**Why it's wrong:** Adds 200ms–2500ms of startup latency to every Hermes CLI command or turn, stalling agent conversational responsiveness and failing abruptly when offline.
**Do this instead:** Synchronously read the local cache file (`< 1ms`). If expired or missing, dispatch the HTTP request to the background daemon worker thread (`notion-brain-sync-worker`).

### Anti-Pattern 3: Coupling Remote Update HTTP to `store.py`

**What people do:** Reusing `store._request()` for GitHub API calls.
**Why it's wrong:** `store.py` is hardcoded with `BASE_URL = "https://api.notion.com/v1"`, injects `Authorization: Bearer NOTION_API_KEY`, and throws `RuntimeError("NOTION_API_KEY not set")` if unconfigured. GitHub API is unauthenticated public REST.
**Do this instead:** `updater.py` contains its own isolated HTTP helper using standard `requests.get()` with explicit User-Agent (`hermes-brain/<version>`), tight timeout (2.5s), and secret sanitization.

### Anti-Pattern 4: Hardcoded PyPI API Tokens in CI Secrets

**What people do:** Generating a permanent PyPI API token and storing it in GitHub Secrets (`PYPI_TOKEN`).
**Why it's wrong:** Tokens can leak, do not expire automatically, and fail security audits.
**Do this instead:** PyPA Trusted Publishing via GitHub Actions OIDC (`pypa/gh-action-pypi-publish@release/v1` with `id-token: write`).

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **GitHub Releases API** (`api.github.com/repos/MNDL-27/hermes-brain/releases/latest`) | Public HTTP GET via `requests` | Timeout 2.5s; unauthenticated rate limit is 60 req/hr/IP. Mitigated by 24h TTL cache and fallback to `/tags` |
| **PyPI Registry** (`pypi.org`) | Automated OIDC release upload in GitHub Actions | Requires configuring Trusted Publisher in PyPI repository management pointing to `MNDL-27/hermes-brain` and `.github/workflows/publish.yml` |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `__main__.py` ↔ `updater.py` | Direct module function calls (`updater.get_update_info(force=True)`) | Passes `--home` and `--check` CLI arguments; exits 0 (up-to-date), 2 (update available), or 1 (error) |
| `provider.py` ↔ `updater.py` | Producer-consumer via `self._sync_queue` | Background worker executes refresh task; main thread only performs non-blocking reads |
| `bootstrap.py` ↔ `updater.py` | Delegation | `health_report()` calls `updater.get_cached_update_banner()` instead of internal urllib call |

---

## Scaling & Boundary Considerations

| Scale / Scope | Architecture Adjustments |
|---------------|--------------------------|
| **Single user CLI** | Read cache directly; immediate feedback with 24-hour TTL |
| **Frequent Agent Turns** | Zero-latency in-memory / worker thread dispatch; no repeated GitHub API calls |
| **GitHub Rate Limiting** | GitHub allows 60 unauthenticated requests/hour per IP. 24h TTL cache reduces volume to 1 request/day per user. On HTTP 403, updater silently falls back to cached data |
| **Offline Environments** | If network fails or DNS times out, updater catches `requests.exceptions.RequestException`, suppresses stack traces, and logs debug message |

---

## Suggested Build Order (Milestone v1.1)

1. **Phase 1: Build Modernization & PyPI Publishing Workflow**
   - Update `pyproject.toml` to migrate `license = { text = "MIT" }` to SPDX `license = "MIT"`.
   - Create `.github/workflows/publish.yml` configuring OIDC trusted publishing on `push: tags: ['v*']`.
   - Validate with `uv run python -m build` and `twine check dist/*`.
   - Document manual twine fallback runbook in repository documentation.

2. **Phase 2: Core Drift Engine & Cache Layer (`notion_brain/updater.py`)**
   - Implement `updater.py` with GitHub API querying, version parsing, install environment detection, and atomic cache storage (`$HERMES_HOME/.update_cache.json`).
   - Implement `tests/test_updater.py` with 100% offline coverage for cache hits, cache misses, TTL expiration, network failures, and command formatting.
   - Refactor `bootstrap.py` update methods (`_find_latest_tag`, `_check_for_update`) to delegate to `updater.py`.

3. **Phase 3: CLI Subcommand Overhaul (`notion_brain/__main__.py`)**
   - Replace legacy git self-mutation code in `_cmd_update` with `updater.py` integration.
   - Implement clean formatted output showing version diff, release URL, and exact upgrade command.
   - Support `--check` (exit 2 on update available) and `--json` flags.
   - Update characterization CLI contract tests.

4. **Phase 4: Non-Blocking Background Runtime Integration (`notion_brain/provider.py`)**
   - Wire cached update banner check into `NotionBrainProvider.initialize()` (zero network delay).
   - Enqueue stale cache refresh onto `notion-brain-sync-worker` queue.
   - Add integration test verifying provider boots without network round-trips.

---

## Sources

- PyPA Trusted Publishing Specification: https://docs.pypi.org/trusted-publishers/using-a-publisher
- GitHub Actions OIDC Token Documentation: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
- PEP 639 – Improving License Expression in pyproject.toml: https://peps.python.org/pep-0639/
- Existing hermes-brain implementations: `notion_brain/store.py`, `notion_brain/provider.py`, `notion_brain/bootstrap.py`, `notion_brain/__main__.py`
