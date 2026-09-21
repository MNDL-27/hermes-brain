# Project Research Summary

**Project:** hermes-brain
**Domain:** Python Package Distribution, Release Automation & CLI Drift Detection
**Researched:** 2026-09-21
**Confidence:** HIGH

## Executive Summary

hermes-brain is a Python 3.11–3.13 memory provider plugin for the Hermes AI agent ecosystem, transforming Notion into a structured, persistent brain. The core runtime is established with 296+ passing unit and integration tests, robust Notion schema bootstrapping, and asynchronous sync daemon threads. Milestone v1.1 ("Distribution & Updates") expands the project lifecycle to production package distribution and release drift detection across four primary goals: automated PyPI publishing on git tags via GitHub Actions OIDC Trusted Publishing, pyproject.toml license modernization to PEP 639 SPDX format (`license = "MIT"`), an overhauled `notion_brain update` CLI command implementing a safe "Detect + Instruct" pattern, and zero-latency non-blocking cached update checks during agent startup.

The recommended implementation approach introduces zero new runtime dependencies, relying exclusively on Python standard library modules (`json`, `pathlib`, `re`, `os`) and the existing locked `requests` client. Automated distribution uses `pypa/gh-action-pypi-publish@release/v1` with scoped `id-token: write` permissions, eliminating static API secrets, complemented by a documented manual `twine` emergency runbook. Update drift detection is centralized in a new dedicated engine (`notion_brain/updater.py`), which inspects host environment attributes (uv virtualenv, pip venv, pip user, or editable git clone) and presents tailored, copy-pasteable upgrade instructions. Startup latency is held strictly to `< 1ms` via a stale-while-revalidate pattern backed by an isolated local cache (`$HERMES_HOME/.update_cache.json`, mode `0o600`), delegating network refreshes to the existing `notion-brain-sync-worker` background thread queue.

The primary technical risks include build failures from setuptools floor mismatches when adopting PEP 639, OIDC publisher authentication failures, pre-release version sorting bugs in naive regex SemVer comparisons, unauthenticated GitHub API rate limit exhaustion (60 requests/hr) stalling agent boot, cache file corruption on abnormal process exit, package name confusion (`notion_brain` import name vs `hermes-brain` PyPI distribution name), and background worker queue contention. These risks are mitigated by bumping the build system floor to `setuptools>=77.0.3`, isolating publishing jobs gated strictly on `refs/tags/v*`, implementing integer 3-tuple SemVer comparison with pre-release ranking, enforcing a 24-hour cache TTL with tight 2.5s network timeouts, using atomic temporary file replacement (`os.replace`), and maintaining 100% offline test reliability via pytest monkeypatching.

## Key Findings

### Recommended Stack

The recommended stack maintains zero runtime dependency growth while modernizing build infrastructure and continuous deployment pipelines. Packaging adheres to modern PEP 621 and PEP 639 standards, with build backend requirements bumped from `setuptools>=68.0` to `setuptools>=77.0.3` to natively support string-based SPDX license declarations without deprecation warnings. Automated publishing is handled by official PyPA GitHub Actions utilizing OpenID Connect (OIDC) token exchange, removing long-lived secrets from CI.

Local drift detection and caching leverage the Python standard library for version parsing, atomic file persistence, and environment inspection, backed by `requests` for unauthenticated GitHub Releases API communication. Development and release validation continue on pinned tools: `build` (`1.5.0`), `twine` (`6.2.0`), `pytest` (`9.1.1`), `ruff` (`0.16.0`), and `mypy` (`2.3.0`).

**Core technologies:**
- Python Standard Library (`json`, `pathlib`, `re`, `os`): Cache storage, atomic file persistence, SemVer tuple comparison, environment detection — zero runtime dependencies.
- `requests` (`>=2.28`, locked `2.34.2`): GitHub REST API querying for latest releases/tags with custom User-Agent, tight timeouts (2.5s), and secret sanitization.
- GitHub Actions OIDC (`id-token: write`): Cryptographic identity exchange between GitHub Actions and PyPI — eliminates long-lived PyPI API tokens in repository secrets.
- `pypa/gh-action-pypi-publish` (`release/v1`): Official PyPA GitHub Action for PyPI uploads via Trusted Publishing — uploads wheels/sdists and generates Sigstore digital attestations.
- `setuptools` (`>=77.0.3`): Build backend supporting PEP 639 SPDX license expressions — enables clean `license = "MIT"` declaration in `pyproject.toml`.
- `twine` (`6.2.0`): Package distribution metadata validator (`twine check --strict`) and manual release fallback upload tool.

### Expected Features

Milestone v1.1 focuses on making hermes-brain effortlessly installable, verifiable, and maintainable across all deployment modalities.

**Must have (table stakes):**
- Automated PyPI Publishing — Triggered on `v*` tag push via GitHub Actions OIDC Trusted Publishing (`.github/workflows/publish.yml`).
- PEP 639 SPDX License Modernization — Migrate `pyproject.toml` from `license = { text = "MIT" }` to `license = "MIT"`.
- Manual Twine Fallback Runbook — Documented emergency step-by-step release instructions for offline or credentialed fallback.
- CLI `update` Drift Detection Subcommand — Checks for newer remote versions and displays actionable upgrade instructions.
- Explicit Host Environment Detection — Accurately detects uv, standard venv, pip user, or editable git clones and formats exact shell commands.
- Zero-Latency Agent Startup (<1ms) — Provider initialization synchronously reads local cache and never performs blocking network requests on the main thread.
- Machine-Readable CLI Flags (`--check`, `--json`) — Supports `--check` (exit code 2 on drift, 0 when up-to-date) and `--json` structured outputs for scripting and CI.

**Should have (differentiators):**
- Dual Release Source Drift Tracking — Detects formal tagged releases from GitHub Releases API, falling back to git commit drift for developer git clones.
- Safe "Detect + Instruct" UX Pattern — Eliminates dangerous in-place self-mutation in favor of clear, copy-pasteable instructions tailored to the user's environment.
- Non-Blocking Background Worker Refresh — Provider initialization enqueues stale cache refreshes into the existing `notion-brain-sync-worker` daemon queue.
- Isolated, Secure Local Cache (`$HERMES_HOME/.update_cache.json`) — Mode `0o600` atomic file storage decoupled from Notion workspace configuration.
- Direct Release Notes URL Banners — Directly links to `https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z` for change review prior to upgrading.

**Defer (v2+):**
- Pre-push Git Hook for Quick Test Execution (TOOL-01) — Defer local git test runner to future developer tooling phase.
- Scheduled Pre-Commit Autoupdate GitHub Action (TOOL-02) — Defer weekly dependency bump workflows to maintenance milestone.
- PyPI JSON API Fallback Client — Secondary fallback if GitHub API is degraded; GitHub Releases remain primary for git and wheel release parity.

### Architecture Approach

The architecture decouples package update management from both the Notion API network store (`notion_brain/store.py`) and Notion workspace hierarchy provisioning (`notion_brain/bootstrap.py`), establishing a focused drift engine in `notion_brain/updater.py`. The local update cache lives in an isolated `$HERMES_HOME/.update_cache.json` file to guarantee that update checking operates before Notion is configured and survives database resets.

The runtime utilizes a stale-while-revalidate pattern: `NotionBrainProvider.initialize()` synchronously inspects the cache file (<1ms). If the cache is fresh (age < 24h TTL), initialization proceeds immediately with zero network I/O. If missing or expired, a refresh task is enqueued onto `self._sync_queue` and processed asynchronously by the background daemon worker (`notion-brain-sync-worker`), ensuring user conversational responsiveness is never impacted by network latency or rate limits.

**Major components:**
1. `notion_brain/updater.py` (NEW): Core drift engine responsible for GitHub API queries, SemVer version comparisons, install environment detection, and atomic cache persistence (`0o600`).
2. `.github/workflows/publish.yml` (NEW): GitHub Actions release pipeline building distributions, running `twine check --strict`, and executing PyPI Trusted Publishing with `id-token: write`.
3. `notion_brain/__main__.py` (MODIFIED): CLI entry point overhauling the `update` subcommand to use "Detect + Instruct" output formatting with `--check` and `--json` support.
4. `notion_brain/provider.py` (MODIFIED): Runtime facade integrating non-blocking update checks and enqueuing background cache refreshes on stale TTL.
5. `notion_brain/bootstrap.py` (MODIFIED): Deprecates internal update helpers (`_find_latest_tag`, `_check_for_update`) and delegates `health_report()` update status to `updater.py`.
6. `tests/test_updater.py` (NEW): Offline unit test suite providing 100% mocked coverage for version comparison, cache TTL, rate limit handling, and CLI formatting.

### Critical Pitfalls

1. **OIDC Trusted Publishing Misconfiguration & Publishing Unverified Builds** — Omitting `id-token: write`, misconfiguring PyPI environment names, or publishing untagged/failing code. Avoid by separating `test`, `build`, and `publish` jobs, gating publication strictly on `refs/tags/v*`, requiring `environment: pypi`, and using official `pypa/gh-action-pypi-publish@release/v1`.
2. **PEP 639 License Expression Floor Mismatch (`setuptools>=77.0.3`)** — Declaring `license = "MIT"` while `pyproject.toml` requires `setuptools>=68.0` causes build failures or invalid metadata in isolated environments. Avoid by updating `[build-system] requires = ["setuptools>=77.0.3"]` and verifying with `twine check --strict dist/*`.
3. **Lexicographical vs Semantic Version Parsing & Pre-release Regex Traps** — Naive integer regex tuple parsing ranks pre-release `1.1.0b1` (`1, 1, 0, 1`) over final release `1.1.0` (`1, 1, 0`), or misorders `1.10.0` vs `1.9.0`. Avoid by implementing standard integer 3-tuple SemVer comparison with pre-release suffix ranking, tested exhaustively across version matrices.
4. **Unauthenticated GitHub API Rate Limiting (60 req/hr) Blocking Startup** — Issuing synchronous network requests during provider boot or turn sync triggers HTTP 403 and adds 2-3s startup lag. Avoid by reading exclusively from `$HERMES_HOME/.update_cache.json` on the main thread, enforcing 24h TTL, and delegating refreshes to the background worker with tight 2.5s timeouts.
5. **Cache Concurrency, Corruption & Non-Atomic Disk Writes** — Using non-atomic `open("w")` leaves truncated 0-byte files on process termination, crashing startup with `JSONDecodeError`. Avoid by writing to a temporary file (`.update_cache.json.tmp`), applying `0o600` permissions, and atomically replacing via `os.replace`, with safe fallback on decode errors.
6. **Package Distribution Name Mismatch in Instruct Output** — Instructing users to run `pip install --upgrade notion_brain` fails because the PyPI package is `hermes-brain`. Avoid by ensuring command formatting explicitly uses `hermes-brain` for wheel/pip installs and adapts to git checkouts.

## Implications for Roadmap

Based on the synthesized research, the milestone work should be executed across 4 sequential phases:

### Phase 1: Build Modernization & PyPI Trusted Publishing
**Rationale:** Establishing modern packaging standards and automated distribution pipelines provides the foundation for release artifacts before downstream update detection mechanisms consume them.
**Delivers:** Migrated `pyproject.toml` with `license = "MIT"` and `setuptools>=77.0.3` build floor; `.github/workflows/publish.yml` with OIDC Trusted Publishing (`id-token: write`, `environment: pypi`); verification via `python -m build` and `twine check --strict dist/*`; documented manual twine release fallback runbook in docs.
**Addresses:** PyPI Package Availability, Automated Tag Publishing, PyPI OIDC Trusted Publishing, Manual Twine Runbook, SPDX Modernization.
**Avoids:** Pitfall 1 (OIDC misconfiguration), Pitfall 2 (setuptools floor mismatch).

### Phase 2: Core Drift Engine & Cache Layer (`notion_brain/updater.py`)
**Rationale:** The core logic for version comparison, environment detection, and atomic caching must be built and rigorously tested offline before integrating into the CLI or provider daemon.
**Delivers:** Dedicated `notion_brain/updater.py` module with GitHub API client (2.5s timeout, secret sanitization), integer 3-tuple SemVer comparison supporting pre-release tags, install environment detection (uv, pip venv, pip user, git clone), atomic 0o600 cache read/write at `$HERMES_HOME/.update_cache.json`, delegation shims in `bootstrap.py`, and comprehensive offline unit test suite in `tests/test_updater.py`.
**Addresses:** CLI Update Drift Detection Engine, Explicit Environment Detection, Isolated Local Cache (`0o600`), Dual Release Source Tracking.
**Avoids:** Pitfall 3 (SemVer & pre-release bugs), Pitfall 5 (cache corruption), Pitfall 8 (offline test suite leakage).

### Phase 3: CLI Update Subcommand Overhaul (`notion_brain/__main__.py`)
**Rationale:** With the drift engine in place, user-facing CLI commands can be modernized to replace unsafe git self-mutation with informative "Detect + Instruct" output.
**Delivers:** Overhauled `notion_brain update` command in `notion_brain/__main__.py` displaying version status, release notes URL, and exact copy-paste upgrade commands; `--check` flag (exits 2 on drift, 0 when current); `--json` machine-readable output; `--force` flag for immediate cache bypass; updated characterization tests in `tests/test_cli_contract.py`.
**Addresses:** CLI Update Drift Detection Command, Machine-Friendly Flags (`--check`, `--json`), Tailored Per-Environment Command, Actionable Update Banners.
**Avoids:** Pitfall 6 (distribution name mismatch), Anti-Feature (silent virtualenv self-mutation).

### Phase 4: Non-Blocking Background Runtime Integration (`notion_brain/provider.py`)
**Rationale:** Embedding update checks into the daemon provider must be the final step once the cache and drift engine are fully validated, ensuring zero regression in agent responsiveness.
**Delivers:** Synchronous local cache check (<1ms) in `NotionBrainProvider.initialize()`; background refresh task dispatch to existing `notion-brain-sync-worker` daemon queue (`self._sync_queue`) when cache TTL (24h) is expired; refactored `bootstrap.health_report()` utilizing cached update banner; integration tests validating sub-millisecond boot and zero main-thread network calls.
**Addresses:** Zero-Latency Startup (<1ms), Non-Blocking Daemon Worker Dispatch, Stale-While-Revalidate Lifecycle.
**Avoids:** Pitfall 4 (rate limiting & startup delay), Pitfall 7 (worker thread congestion).

### Phase Ordering Rationale

- **Dependency Sequencing:** Build configuration and release automation (Phase 1) define the canonical package identity and distribution channel. The drift engine (Phase 2) implements the core version evaluation and persistence logic. The CLI overhaul (Phase 3) exposes this functionality directly to users. The provider integration (Phase 4) embeds it safely into long-running background agent workflows.
- **Architectural Isolation:** Extracting `updater.py` in Phase 2 decouples update logic from Notion workspace bootstrapping (`bootstrap.py`) and Notion REST operations (`store.py`), preventing domain entanglement.
- **Risk Mitigation:** Testing version comparison and atomic file writes in Phase 2 guarantees correctness before background threads and multi-process access are introduced in Phase 4.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Core Drift Engine):** Research edge cases in installation environment detection (differentiating uv vs standard pip in complex virtual environments, containerized setups, or system-managed packages) and SemVer pre-release suffix comparison nuances without third-party dependencies.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Build Modernization & OIDC Publishing):** Established PyPA Trusted Publishing standard; configuration and workflow syntax are fully defined.
- **Phase 3 (CLI Update Subcommand):** Standard argparse subcommands, terminal text formatting, and exit code conventions.
- **Phase 4 (Non-Blocking Runtime Integration):** Standard task producer-consumer integration into existing `_sync_queue` and daemon worker thread.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new runtime dependencies; Python stdlib + requests already locked; setuptools>=77.0.3 and PyPA OIDC verified against official documentation. |
| Features | HIGH | Clear functional separation between table stakes and differentiators; explicit anti-feature boundaries ("Detect + Instruct" vs self-mutation). |
| Architecture | HIGH | Architectural separation (`updater.py`), isolated cache (`.update_cache.json`), and worker thread dispatch are fully mapped to existing codebase patterns. |
| Pitfalls | HIGH | Specific edge cases identified (setuptools floor, SemVer pre-releases, rate limits, atomic writes, package naming) with concrete prevention patterns. |

**Overall confidence:** HIGH

### Gaps to Address

- **Environment Detection in Atypical Containers:** In some Docker or headless runner environments, `VIRTUAL_ENV` may not be set even though packages are installed in isolated user paths. Address during Phase 2 by establishing robust fallback command recommendations.
- **PyPI Pending Publisher Setup:** PyPI Trusted Publishing requires the repository administrator to register the GitHub owner, repository, workflow name (`publish.yml`), and environment (`pypi`) on pypi.org prior to pushing the first release tag. This one-time manual setup must be prominently documented in the maintainer runbook.

## Sources

### Primary (HIGH confidence)
- `pypa/packaging.python.org` — PEP 639 SPDX license expressions and `setuptools>=77.0.3` build requirements.
- `pypa/gh-action-pypi-publish` Official Repository (`release/v1`) — OIDC Trusted Publishing, `id-token: write` permission, `environment: pypi`.
- PyPI Trusted Publishers Specification (`docs.pypi.org/trusted-publishers/`) — GitHub Actions OIDC configuration and pending publisher registration.
- GitHub REST API Documentation — Releases and tags endpoints, 60 req/hr unauthenticated rate limit, and response schemas.
- PEP 440 & PEP 621 — Version identification specifications and standard pyproject.toml metadata.

### Secondary (MEDIUM confidence)
- Existing hermes-brain codebase: `notion_brain/provider.py`, `notion_brain/bootstrap.py`, `notion_brain/__main__.py`, `tests/test_store.py`.

---
*Research completed: 2026-09-21*
*Ready for roadmap: yes*
