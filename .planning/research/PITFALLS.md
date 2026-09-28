# Pitfalls Research

**Domain:** Python Package Distribution, CLI Update Drift Detection, and Background Update Checking
**Researched:** 2026-09-21
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: OIDC Trusted Publishing Misconfiguration & Publishing Unverified Builds

**What goes wrong:**
GitHub Actions release workflow fails with `403 Forbidden: Invalid audience` / `token rejected`, or silently publishes broken, unverified wheel packages directly to PyPI.

**Why it happens:**
PyPI Trusted Publishing (OIDC) requires precise token permissions (`permissions: id-token: write, contents: read`) and matching environment configuration (`environment: pypi`). Developers omit `id-token: write`, misconfigure the PyPI environment name, trigger the workflow on general branch pushes rather than verified release tags (`v*`), or combine build and publish steps into a single job without running offline unit tests first.

**How to avoid:**
1. Isolate workflow jobs: `test` (runs pytest offline across Python 3.11, 3.12, 3.13), `build` (builds sdist/wheel and runs `twine check --strict dist/*`), and `publish` (OIDC publish).
2. Configure `publish` job with:
   ```yaml
   permissions:
     id-token: write
     contents: read
   environment:
     name: pypi
     url: https://pypi.org/p/hermes-brain
   ```
3. Gate publish job strictly on release tags: `if: startsWith(github.ref, 'refs/tags/v')`.
4. Use official `pypa/gh-action-pypi-publish@release/v1`. Never store long-lived PyPI API tokens in GitHub Secrets.

**Warning signs:**
GitHub Actions step fails with `HTTPError: 403 Forbidden` from PyPI OIDC minting endpoint, or untagged development commits trigger publishing attempts to PyPI.

**Phase to address:**
Phase 1 (Packaging, Build Metadata & Trusted Publishing)

---

### Pitfall 2: PEP 639 License Expression Floor Mismatch (`setuptools>=77.0.0` vs `setuptools>=68.0`)

**What goes wrong:**
Migrating `pyproject.toml` from deprecated table `license = { text = "MIT" }` to PEP 639 string `license = "MIT"` causes build failures or stripped metadata warnings in build tools and `twine check --strict`.

**Why it happens:**
PEP 639 string license expressions require `setuptools>=77.0.0`. The current `pyproject.toml` declares `[build-system] requires = ["setuptools>=68.0"]`. When `python -m build` runs in an isolated virtual environment with setuptools < 77.0.0, setuptools rejects the string license or falls back to legacy metadata, producing `ConfigurationError: 'project.license' must be a table` or failing `twine check --strict` with `License-Expression field missing or invalid`.

**How to avoid:**
1. Update `[build-system] requires` in `pyproject.toml` to `["setuptools>=77.0.0"]`.
2. Modernize project metadata:
   ```toml
   [project]
   license = "MIT"
   license-files = ["LICENSE"]
   ```
3. Verify builds locally with `python -m build` and `twine check --strict dist/*` across clean venvs.

**Warning signs:**
`build` outputs `ConfigurationError` or `twine check --strict` produces `WARNING: `License-Expression` is not recognized by this version of setuptools`.

**Phase to address:**
Phase 1 (Packaging, Build Metadata & Trusted Publishing)

---

### Pitfall 3: Lexicographical vs Semantic Version Parsing & Pre-release Regex Traps

**What goes wrong:**
Update drift detection misorders versions. Lexicographical string sorting ranks `"1.10.0"` as older than `"1.9.0"`. Naive regex digit parsing (`tuple(int(x) for x in re.findall(r"\d+", v))`) ranks pre-releases like `"1.1.0b1"` as `(1, 1, 0, 1)`, making it appear newer than final release `"1.1.0"` (`(1, 1, 0)`).

**Why it happens:**
Developers avoid adding dependencies and use naive string comparison or integer regex tuples. In `notion_brain/bootstrap.py:652`, `_check_for_update()` currently uses `tuple(int(x) for x in _re.findall(r"\d+", v))`. This naive tuple logic breaks on pre-releases (`b1`, `rc1`), dev releases, and post-releases.

**How to avoid:**
Implement a standard-library SemVer parser in `notion_brain/bootstrap.py` that parses `(major, minor, patch)` as integers and handles pre-release suffixes according to PEP 440 / SemVer rules:
- Final release `1.1.0` must rank higher than pre-release `1.1.0b1`.
- Numeric comparisons `(1, 10, 0) > (1, 9, 0)` must hold.
- Strip leading `v` tags cleanly (`v1.1.0` -> `1.1.0`).
- Test exhaustively in `tests/test_bootstrap_schema.py` with parameter matrices covering pre-releases, patches, and multi-digit minor versions.

**Warning signs:**
Running `hermes-brain update --check` on a stable installation prompts the user to "upgrade" to an older beta or release candidate, or reports `already up to date` when `1.10.0` is available.

**Phase to address:**
Phase 2 (CLI Update Drift Detection)

---

### Pitfall 4: Unauthenticated GitHub API Rate Limiting (60 req/hr) Blocking Startup

**What goes wrong:**
Synchronous GitHub API calls in `bootstrap.py` fail with `HTTP Error 403: rate limit exceeded` or stall agent startup for 2-3 seconds per session.

**Why it happens:**
GitHub restricts unauthenticated REST API requests to 60 requests per hour per egress IP. In multi-user setups, corporate VPNs, WSL2 NAT networks, or CI environments, this quota is shared. Calling `_find_latest_tag()` synchronously during provider initialization or CLI commands exhausts the quota immediately.

**How to avoid:**
1. Never call the network synchronously during `provider.initialize()` or module import.
2. Read exclusively from a local cache file (`$HERMES_HOME/.update_cache.json`).
3. Enforce a 24-hour default TTL (`HERMES_BRAIN_UPDATE_CHECK_INTERVAL_S`, default 86400). If the cache is valid, skip all network calls.
4. Set strict socket timeouts (2.0s maximum) on all network requests.
5. Gracefully catch HTTP 403 / network exceptions without raising or logging noisy tracebacks.

**Warning signs:**
Agent startup delays spike to 2-3 seconds; logs show `HTTPError: 403 Forbidden` from `api.github.com/repos/MNDL-27/hermes-brain/tags`.

**Phase to address:**
Phase 3 (Non-Blocking Cached Auto-Update Check)

---

### Pitfall 5: Cache File Concurrency, Corrupted JSON, & Non-Atomic Disk Writes

**What goes wrong:**
`$HERMES_HOME/.update_cache.json` gets truncated to 0 bytes or corrupted when a process is killed mid-write or when CLI commands and background daemon threads write concurrently, crashing provider startup with `json.decoder.JSONDecodeError`.

**Why it happens:**
Using direct `open(cache_path, "w").write(...)` is non-atomic. If the process terminates during flush, or if a background thread and a CLI command write simultaneously, the file is corrupted.

**How to avoid:**
1. Atomic write pattern: Write JSON to a temporary file (`.update_cache.json.tmp.<pid>`) on the same filesystem, flush, `os.fsync`, and atomically rename via `os.replace`.
2. Safe loader: Wrap cache reading in `try...except (json.JSONDecodeError, OSError, ValueError)`. On error, log debug message and return fallback empty cache; never let corrupt cache crash the provider.
3. Ensure parent directory `$HERMES_HOME` exists before writing (`os.makedirs(hermes_home, exist_ok=True)`).

**Warning signs:**
`JSONDecodeError: Expecting value: line 1 column 1 (char 0)` originating from `_load_update_cache` during `ensure_brain` or provider initialization.

**Phase to address:**
Phase 3 (Non-Blocking Cached Auto-Update Check)

---

### Pitfall 6: Package Identity & Installation Mode Mismatch in CLI Instruct Output

**What goes wrong:**
CLI update output instructs the user to run `pip install --upgrade notion_brain` (which fails because the PyPI distribution name is `hermes-brain`), or instructs git pull on a wheel install, or runs `pip install --upgrade hermes-brain` over an editable developer checkout (`pip install -e .`), destroying local development links.

**Why it happens:**
The Python import package name is `notion_brain`, but the PyPI package distribution name is `hermes-brain`. Additionally, users install via multiple methods: PyPI wheel (`pip install hermes-brain`), local git clone (`git checkout` + `pip install -e .`), or `uv`.

**How to avoid:**
1. Distinguish installation mode at runtime:
   - Check if `__file__` is inside a repository with `.git` (editable/dev install).
   - Check `sys.prefix` vs `sys.base_prefix` (virtualenv) and check for `uv` or `pip`.
2. Print tailored instructions:
   - Git checkout: `git pull && pip install -e .` (or prompt user).
   - Standard wheel: `pip install --upgrade hermes-brain` (or `uv pip install --upgrade hermes-brain`).
3. Adhere strictly to project constraint: Detect and instruct only. Never execute silent self-modification or automated package re-installation behind the user's back.

**Warning signs:**
User reports `ERROR: Could not find a version that satisfies the requirement notion_brain`, or local git development edits are wiped out by update commands.

**Phase to address:**
Phase 2 (CLI Update Drift Detection)

---

### Pitfall 7: Background Worker Queue Congestion & Shutdown Delays

**What goes wrong:**
Enqueuing background update checks onto the existing `notion-brain-sync-worker` queue stalls memory persistence tasks or causes agent shutdown (`join(timeout=5.0)`) to hang.

**Why it happens:**
`NotionBrainProvider` uses a single daemon thread running `_worker_loop()` with FIFO `queue.Queue`. If an update network check taking 2 seconds is placed ahead of memory sync tasks, conversation turns wait on GitHub API latency. If agent shutdown occurs while the thread is blocked in `urlopen`, shutdown exceeds the 5-second budget.

**How to avoid:**
1. Check cache TTL before enqueuing any background task. If cache is fresh, do not enqueue anything.
2. Ensure network socket timeout is strictly capped (e.g. 2.0s).
3. If using `_sync_queue`, enqueue update checks with lower priority or only when queue is empty, or run as a fire-and-forget daemon thread that updates the cache file independently.
4. Catch all exceptions inside the worker task and pass error messages through `S.redact_secrets()`.

**Warning signs:**
Memory extraction latency increases after startup; daemon shutdown logs show worker thread join timeout.

**Phase to address:**
Phase 3 (Non-Blocking Cached Auto-Update Check)

---

### Pitfall 8: Offline Test Suite Leakage & Network Calls in Unit Tests

**What goes wrong:**
Running `pytest` makes live outbound network requests to `api.github.com` or `pypi.org`, causing flaky tests or complete failure in offline CI runners and disconnected development machines.

**Why it happens:**
New unit tests for update drift detection, cache expiration, and CLI subcommands call `bootstrap._check_for_update()` or `bootstrap._find_latest_tag()` without monkeypatching `urllib.request.urlopen` or store functions.

**How to avoid:**
1. Enforce zero live network calls across all 303+ tests.
2. In all test cases, monkeypatch `urlopen` with fake response mocks (`read()`, `__enter__()`).
3. Use `tmp_path` fixture for all `$HERMES_HOME` cache file tests.
4. Add a test in `tests/test_bootstrap_schema.py` verifying that network failures and socket timeouts fail silently without crashing.

**Warning signs:**
`pytest` runtime exceeds 1 second for the unit test suite, or tests fail with `socket.gaierror` / `urllib.error.URLError` when network is disabled.

**Phase to address:**
Cross-cutting / Tested in all phases

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reusing `tuple(int, ...)` regex for SemVer | Zero lines of new parser code | Breaks on pre-releases (`1.1.0b1`), build metadata, and post-releases | Never. Implement standard SemVer 3-tuple parser with pre-release ranking. |
| Synchronous GitHub API call in `initialize()` | Easy to write, no thread synchronization | Blocks agent startup by 2-3s on every session; burns 60 req/hr rate limit | Never. Read disk cache only; refresh asynchronously. |
| Direct `open("w")` for cache JSON | 2 lines of Python code | File corruption on abrupt exit (0-byte file), causing `JSONDecodeError` | Never. Use atomic write via tempfile and `os.replace`. |
| Hardcoding `pip install --upgrade notion_brain` | Quick CLI message | Points to non-existent PyPI package; confuses users | Never. Package is `hermes-brain`. |
| Silent self-update (`git pull` / `pip install`) | One-click convenience | Corrupts running virtual environments, breaks active processes, destroys git branches | Never. Detect + instruct only. |
| Calling PyPI JSON API instead of GitHub API | PyPI gives wheel info directly | Git-based users miss updates; PyPI cache index lags behind releases | Acceptable as secondary fallback; GitHub tags remain primary for git+wheel parity. |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GitHub REST API | Querying unauthenticated without `User-Agent` | Send `User-Agent: hermes-brain/<version>` and `Accept: application/vnd.github+json`. Set 2.0s timeout. |
| GitHub REST API | Assuming API response is always a list of tag objects | Check `isinstance(data, list)` before indexing; GitHub error responses are dicts (`{"message": "..."}`). |
| PyPI OIDC Publishing | Missing `id-token: write` permission in job | Declare `permissions: id-token: write, contents: read` on the publishing job. |
| PyPI OIDC Publishing | Mismatched PyPI Environment name | Ensure GitHub Actions `environment.name` exactly matches the environment configured in PyPI Trusted Publisher settings (`pypi`). |
| Setuptools PEP 639 | Using string `license = "MIT"` with `setuptools<77.0.0` | Pin `setuptools>=77.0.0` in `[build-system] requires` in `pyproject.toml`. |
| Local Disk Cache | Writing to `~/.hermes/.update_cache.json` without creating parent directory | Call `os.makedirs(hermes_home, exist_ok=True)` before file creation. |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous HTTP check at startup | Agent boot delay (1-3s), CLI lag | Read cached tag from disk; never do network I/O in main thread startup | Immediate in slow network or high-latency environments |
| Zero-TTL API polling | HTTP 403 Rate Limit Exceeded | 24-hour cache TTL in `$HERMES_HOME/.update_cache.json` | Breaks at >60 restarts/checks per hour per public IP |
| Heavy background queue tasks | Memory sync delayed behind update check | Strict 2.0s socket timeout; check TTL before queueing; separate or low-priority execution | When network latency spikes to GitHub |
| Re-reading cache on every tool invocation | Unnecessary disk I/O on hot paths | Cache version check in memory after first load during session lifecycle | When agent executes dozens of turns per session |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Silent automated package update | Code execution vulnerability; remote supply-chain compromise without human audit | Strictly enforce "Detect and Instruct" only. Print upgrade command; never execute `pip install` automatically. |
| Unsanitized GitHub error logging | Leaking environment tokens or private proxy URLs in error messages | Run all exceptions through `notion_brain.schema.redact_secrets()` before logging. |
| Long-lived PyPI API tokens in GitHub Secrets | Token leak via compromised CI actions or logs | Use PyPI Trusted Publishing (OIDC token exchange) with zero persistent secrets. |
| Publishing from untrusted pull requests | Untrusted fork code publishing malicious wheels | Restrict publish workflow strictly to repository owner tag pushes (`refs/tags/v*`). Do not trigger on `pull_request`. |
| Insecure temporary file creation | Symlink attacks or race conditions in `/tmp` | Place atomic temp files inside `$HERMES_HOME` with process PID, not in global `/tmp`. |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Telling editable/dev users to `pip install` | Overwrites local development repository with PyPI wheel, breaking working trees | Detect git repo checkout (`(pkg_dir / ".git").is_dir()`) and instruct `git pull` + `pip install -e .`. |
| Telling wheel users to `git pull` | Fails with `not a git repository` error | Detect site-packages install and instruct `pip install --upgrade hermes-brain`. |
| Noisy update warnings on every command | Annoying alert fatigue during routine CLI usage | Show update notice only in `health` report and explicit `update` subcommand, not on every memory search/remember tool call. |
| Vague update instructions | User does not know which command to copy-paste | Print exact command block formatted for their environment (`pip install --upgrade hermes-brain`). |
| Misleading "up to date" message during rate-limit failure | User thinks they have latest version when check actually failed | Distinguish between "up to date" and "unable to check remote version (rate limit or offline)". |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **PyPI Publishing Workflow:** Often missing `id-token: write` permission — verify workflow passes PyPI OIDC verification on TestPyPI or production.
- [ ] **SPDX License Migration:** Often changes `license = "MIT"` without bumping `[build-system] requires` — verify `setuptools>=77.0.0` is pinned in `pyproject.toml` and `twine check --strict dist/*` passes with zero warnings.
- [ ] **SemVer Comparison:** Often fails on pre-release tags (`1.1.0b1` vs `1.1.0`) — verify test matrix with pre-releases and multi-digit minor versions (`1.10.0` vs `1.9.0`).
- [ ] **Cache Atomicity:** Often uses standard `open("w")` — verify atomic write using `.tmp` file and `os.replace` with `try...except JSONDecodeError` guard.
- [ ] **Distribution Name Accuracy:** Often prints `pip install notion_brain` — verify instruct command outputs `hermes-brain`.
- [ ] **Offline Tests:** Often forgets to mock update checks in new tests — verify `pytest` passes with network disabled (`unshare -n pytest` or offline sandbox).
- [ ] **Rate Limit Handling:** Often crashes when GitHub returns dict `{"message": "rate limit..."}` — verify handling when `data` is not a list.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| PyPI publish rejected (OIDC error) | LOW | Check GitHub Actions run log for OIDC error. Update `environment: pypi` or add `permissions: id-token: write`. Re-run or re-tag. |
| Broken wheel published to PyPI | HIGH | PyPI does not allow re-uploading the same version. Bump version (`1.1.1`), fix build metadata, and publish new tag. Yank broken release on PyPI. |
| Corrupt `.update_cache.json` crashes app | LOW | Catch `JSONDecodeError` and remove/overwrite file. User recovery: `rm ~/.hermes/.update_cache.json`. |
| Editable install overwritten by pip upgrade | MEDIUM | Run `pip uninstall hermes-brain` followed by `pip install -e .` from local git checkout. |
| GitHub API 403 Rate Limit | LOW | Fall back to cached tag or skip check. Wait for 1-hour quota reset. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| OIDC publishing misconfig & unverified builds | Phase 1 (PyPI Packaging & OIDC) | Dry-run on TestPyPI or verify workflow permissions, build isolation, and `twine check --strict`. |
| PEP 639 setuptools floor mismatch | Phase 1 (PyPI Packaging & OIDC) | Run `python -m build` in clean venv with setuptools>=77.0.0; verify `twine check --strict`. |
| SemVer parsing & pre-release traps | Phase 2 (CLI Drift Detection) | Unit tests in `tests/test_bootstrap_schema.py` verifying `1.10.0 > 1.9.0` and `1.1.0 > 1.1.0b1`. |
| Package name mismatch in instruct output | Phase 2 (CLI Drift Detection) | Test verifying CLI output contains `hermes-brain` and adapts to git vs wheel install. |
| Startup blocking & 60 req/hr rate limits | Phase 3 (Cached Auto-Update) | Benchmark `provider.initialize()` latency; verify no network calls occur when cache is warm. |
| Cache corruption & non-atomic writes | Phase 3 (Cached Auto-Update) | Test atomic write and verify graceful recovery from 0-byte and corrupted `.update_cache.json`. |
| Worker thread congestion | Phase 3 (Cached Auto-Update) | Test verifying sync queue processes memory turns without delay; strict 2.0s network timeout. |
| Offline test suite leakage | Cross-cutting (All Phases) | Run full test suite with mocked network calls; zero socket connections allowed. |

## Sources

- [PyPI Trusted Publishing Documentation](https://docs.pypi.org/trusted-publishers/) (Confidence: HIGH)
- [Python Packaging User Guide: Publishing with GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/) (Confidence: HIGH)
- [Setuptools PEP 639 License Migration Guide](https://github.com/pypa/setuptools/blob/main/docs/userguide/license_migration.rst) (Confidence: HIGH)
- [GitHub REST API Rate Limiting Documentation](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) (Confidence: HIGH)
- [PEP 440 – Version Identification and Specification](https://peps.python.org/pep-0440/) (Confidence: HIGH)

---
*Pitfalls research for: hermes-brain v1.1 Distribution & Updates*
*Researched: 2026-09-21*
