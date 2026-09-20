# Project Research Summary

**Project:** hermes-brain
**Domain:** Agent Memory Plugin, Developer Experience & Release Polish (Python / Hermes Plugin)
**Researched:** 2026-09-20
**Confidence:** HIGH

## Executive Summary

hermes-brain is a persistent memory provider plugin for the Hermes AI agent ecosystem (`hermes-agent`), replacing unstructured flat-file memory with a structured, multi-database Notion workspace under a single **Hermes Brain** parent page. The core runtime architecture is already battle-tested across 296+ passing unit and integration tests, featuring heuristic and LLM-assisted conversation extraction, a non-blocking background queue for asynchronous Notion sync, automated schema repair, and strict secret redaction across all external boundaries. This milestone focuses on developer experience (DX), contributor quality gates, and release polish across three active GitHub issues: establishing offline test coverage for the declarative Desktop UI configuration schema (#51), configuring local pre-commit hooks that strictly mirror CI quality gates (#52), and implementing portable Darwin/macOS platform detection in the installer script (#53).

The recommended implementation strategy follows a strict dependency ladder: test isolation first, local git quality gates second, and user-facing installation guards third. In Phase 1, `notion_brain/config_schema.py` is decoupled from external host application imports (`plugins.memory.config_schema`) using lightweight in-memory stubs in `tests/conftest.py` and optional class fallbacks, enabling pure unit tests to validate the Desktop UI contract offline without external agent dependencies. In Phase 2, `.pre-commit-config.yaml` is introduced with tool pins matching CI exactly (`ruff==0.16.0`, `mypy==2.3.0`, `pre-commit>=4.1.0`), enforcing fast (<1.5s) local linting, formatting, and static typing to eliminate PR rework. In Phase 3, `scripts/install.sh` is updated with a non-destructive POSIX `uname -s` guard that intercepts macOS hosts, presents actionable manual installation commands pointing to the README Quickstart, and exits cleanly with status code `0`.

The primary technical risks include host-framework import crashes during isolated test execution, pre-commit virtual environment isolation causing false-positive missing-import errors in Mypy, formatting drift between local tools and GitHub Actions CI, and improper non-zero exit codes breaking macOS shell automation. These risks are mitigated by registering minimal Python standard-library stubs in `tests/conftest.py` before test discovery, configuring pre-commit's Mypy hook with explicit package targets and dependency stubs, pinning all git hook tags to identical `pyproject.toml` versions, and placing the shell OS detection block as Step 0 before any package manager lookups.

## Key Findings

### Recommended Stack

The recommended stack introduces no runtime dependencies and relies on established standard tools pinned to match existing project configurations. Local git hook automation is handled by `pre-commit` (`^4.1.0`), added as a dev dependency in `pyproject.toml`. Git hooks utilize `astral-sh/ruff-pre-commit` pinned to `v0.16.0` (executing `ruff --fix` and `ruff-format` across `notion_brain/` and `tests/`) and `pre-commit/mirrors-mypy` pinned to `v2.3.0` (enforcing static typing aligned with `mypy.ini`). Standard file sanitizers from `pre-commit/pre-commit-hooks` `v5.0.0` prevent trailing whitespace, missing end-of-file newlines, and unparsed YAML/TOML errors.

Test execution continues on `pytest` `9.1.1` and `pytest-cov` `7.1.0`. Declarative schema assertions are written using native Python dataclass and tuple assertions without introducing heavy dependencies like Pydantic or jsonschema. Shell installation platform detection uses standard POSIX `uname -s` inside a Bash 3.2-compatible `case` statement, ensuring portable execution across both macOS (Darwin) and Linux distributions.

**Core technologies:**
- `pre-commit` (`^4.1.0`): Multi-language Git pre-commit framework — enforces CONTRIBUTING.md standards locally before pushing to CI.
- `astral-sh/ruff-pre-commit` (`v0.16.0`): Linter and code formatter hook — matches `ruff==0.16.0` in `pyproject.toml` with sub-100ms execution.
- `pre-commit/mirrors-mypy` (`v2.3.0`): Static type check hook — matches `mypy==2.3.0` in `pyproject.toml` with `mypy.ini` discovery.
- `pytest` (`9.1.1`): Unit test framework and assertion runner — zero-dependency testing of declarative UI configuration contracts.
- POSIX `uname -s` / Bash 3.2+: Operating system detection — portable, zero-dependency detection across macOS and Linux environments.

### Expected Features

The feature landscape balances immediate contributor/user friction reduction against long-term maintenance overhead.

**Must have (table stakes):**
- Unit test suite for `config_schema.py` (#51) — comprehensive coverage of `CONFIG_SCHEMA` keys (`notionApiKey`, `hermesHome`), kinds (`KIND_SECRET`, `KIND_TEXT`), env keys, defaults, and immutability.
- Test runtime isolation / host stubbing (#51) — stub `plugins.memory.config_schema` in `tests/conftest.py` or fallback classes in `config_schema.py` so tests run offline in clean checkouts.
- `.pre-commit-config.yaml` configuration (#52) — wires `ruff`, `ruff-format`, `mypy`, and file sanitizers to satisfy `CONTRIBUTING.md`.
- Tool version & rule alignment (#52) — hooks locked to `pyproject.toml` pins (`ruff 0.16.0`, `mypy 2.3.0`) and scoped to `^(notion_brain|tests)/`.
- `pyproject.toml` dev dependency update (#52) — add `pre-commit>=4.1.0` to dev extras so `pip install -e ".[dev]"` installs hook binaries.
- Darwin OS detection in `scripts/install.sh` (#53) — detect `Darwin` via `uname -s` before package manager checks, output cyan/yellow Quickstart guidance, and exit 0.
- Documentation sync (#52, #53) — align README Quickstart and CONTRIBUTING.md with macOS manual steps and pre-commit workflow.

**Should have (competitive):**
- Fast local pre-commit turnaround (<1.5s) — avoid developer `--no-verify` bypassing by scoping hooks and leveraging Rust binaries.
- Formatted copy-paste commands for macOS — display exact `pip install` and `ln -s` commands in installer terminal output.
- Schema contract invariant testing — assert schema field immutability (tuples), camelCase Desktop keys, and secret field redaction/default rules.

**Defer (v2+):**
- Automated macOS Homebrew formula (`brew install hermes-brain`) — high maintenance overhead across Intel/Apple Silicon; manual venv setup is sufficient.
- Full pytest suite in git pre-commit hook — test run latency induces hook bypassing; reserve full tests for pre-push or CI.
- Windows native PowerShell installer (`install.ps1`) — out of scope; documented manual pip install suffices.

### Architecture Approach

The architecture isolates developer tooling, CI pipelines, and runtime boundaries into decoupled layers. Host framework dependencies (`plugins.memory.config_schema`, `agent`, `tools`) are decoupled at test time using Python `types.ModuleType` injection in `tests/conftest.py` and optional fallback class patterns, guaranteeing standalone pytest execution without host installations. Local git hooks mirror remote GitHub Actions workflows (`.github/workflows/ci.yml`) by delegating formatting, linting, and type checking to authoritative config files (`pyproject.toml`, `mypy.ini`). The installer shell architecture introduces a non-destructive early guard clause at Step 0, evaluating the OS kernel prior to root checks, agent checks, or package manager lookups.

**Major components:**
1. `tests/test_config_schema.py` & `conftest.py` stubs — Validates declarative Desktop UI configuration contract (`CONFIG_SCHEMA`) in total isolation from host agent runtimes.
2. `.pre-commit-config.yaml` & `pyproject.toml` — Local pre-commit quality gate enforcing code hygiene, Ruff formatting/linting, and Mypy typing aligned with CI.
3. `scripts/install.sh` Platform Guard — Early POSIX OS detector providing graceful informational exit for Darwin hosts while preserving automated Linux workflows.

### Critical Pitfalls

1. **Host-Framework Import Crash in Standalone Tests:** `notion_brain/config_schema.py` fails on `from plugins.memory.config_schema import ...` when host is missing. Avoid by defining runtime stubs in `tests/conftest.py` and fallback classes in `config_schema.py`.
2. **Pre-Commit Mypy Environment Isolation & Missing Stubs:** Pre-commit runs in isolated virtual environments lacking project dependencies or receives individual filenames that break module resolution. Avoid by configuring `additional_dependencies: [types-requests, pytest]`, passing explicit target directories (`notion_brain`, `tests`), and specifying `--config-file=mypy.ini`.
3. **Pre-Commit vs CI Tooling Drift:** Local hooks passing while remote CI fails due to mismatched tool versions. Avoid by pinning pre-commit repository revisions (`v0.16.0`, `v2.3.0`) exactly to `pyproject.toml` pins and running identical command flags.
4. **Platform Detection Sequencing in `install.sh`:** Running Hermes agent checks or Linux package manager checks before OS detection results in `✗ Hermes agent not detected` or `✗ Unknown package manager` on macOS. Avoid by placing the `uname -s` platform check at Step 0 before any environment or package manager evaluations.
5. **Non-Zero Exit Code on Graceful Termination:** Exiting `1` when Darwin is detected breaks script automation and confuses users. Avoid by printing clear manual steps pointing to README Step 2 and exiting cleanly with `exit 0`.

## Implications for Roadmap

Based on combined research, suggested 3-phase execution structure:

### Phase 1: Config Schema Test Infrastructure (#51)
**Rationale:** The declarative config schema exists in production code but has zero automated test coverage. Validating this contract and establishing host module stubbing unblocks clean test collection and type checking before enforcing git hooks.
**Delivers:** Standalone test suite `tests/test_config_schema.py`, isolated runtime stubs in `tests/conftest.py`, and 100% branch/statement coverage on `config_schema.py`.
**Addresses:** Issue #51; table-stakes schema validation (keys, kinds, defaults, secret flags).
**Avoids:** Pitfall 1 (Host import crash), Pitfall 7 (Shallow schema testing).

### Phase 2: Pre-Commit Hook Infrastructure & Tooling Parity (#52)
**Rationale:** Local git hooks should be introduced only when tests, linters, and type checkers are demonstrably green across the workspace. Establishing `.pre-commit-config.yaml` synchronized with CI locks quality gates for all future commits.
**Delivers:** Working `.pre-commit-config.yaml`, `pre-commit>=4.1.0` added to `pyproject.toml` dev extras, scoped Ruff and Mypy hooks, and verified hook installation workflow.
**Uses:** `pre-commit`, `astral-sh/ruff-pre-commit` (`v0.16.0`), `pre-commit/mirrors-mypy` (`v2.3.0`), `pre-commit-hooks` (`v5.0.0`).
**Implements:** Tooling parity mirror between local dev and CI.
**Avoids:** Pitfall 2 (Mypy pre-commit isolation), Pitfall 3 (Pre-commit vs CI version drift), Pitfall 8 (Formatter loops).

### Phase 3: Installer Platform Guard (#53)
**Rationale:** Shell installer modifications are completely decoupled from Python test suites and git hooks. Updating `scripts/install.sh` acts as the final release-polish boundary gate for end-user onboarding.
**Delivers:** Early Darwin OS detection guard in `scripts/install.sh`, formatted terminal manual installation instructions, clean `exit 0`, and updated README/CONTRIBUTING documentation.
**Uses:** POSIX `uname -s`, Bash 3.2-compatible syntax, README Quickstart Step 2 references.
**Implements:** Non-destructive platform guard pattern.
**Avoids:** Pitfall 4 (Detection sequencing), Pitfall 5 (Non-zero exit code), Pitfall 6 (Bash 4 portability traps).

### Phase Ordering Rationale

- **Dependency chain:** Phase 1 fixes test collection and ensures `uv run mypy` and `uv run pytest` pass cleanly across the codebase. Phase 2 introduces pre-commit hooks that immediately run `mypy` and `ruff` on commit; if Phase 1 were deferred, pre-commit installation would fail or report unstubbed type errors on untouched code. Phase 3 operates purely on shell scripts and user documentation, cleanly finishing release readiness.
- **Architectural grouping:** Python code and test suites belong together in Phase 1; developer workflow configuration belongs in Phase 2; end-user deployment and onboarding scripts belong in Phase 3.
- **Risk avoidance:** Order prevents contributor churn by ensuring test harnesses exist before git commit gates are locked.

### Research Flags

Phases likely needing deeper research during planning:
- *None.* All three phases have well-defined boundaries, pinned dependencies, existing file baselines, and exact GitHub issue specifications.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Config Schema Tests):** Standard pytest fixture and `types.ModuleType` mocking patterns. Skip research-phase.
- **Phase 2 (Pre-Commit Infrastructure):** Standard pre-commit YAML configuration aligned with existing `pyproject.toml`. Skip research-phase.
- **Phase 3 (Installer Platform Guard):** Standard POSIX `uname -s` guard with echo instructions. Skip research-phase.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Exact versions validated against PyPI, GitHub API tags, and existing `pyproject.toml` pins. |
| Features | HIGH | Requirements directly bounded by active GitHub issues #51, #52, and #53. |
| Architecture | HIGH | Established Python plugin patterns and shell scripting standards; clear decoupling boundaries. |
| Pitfalls | HIGH | Specific edge cases identified (host imports, mypy isolation, Darwin exit codes, Bash 3.2 compatibility). |

**Overall confidence:** HIGH

### Gaps to Address

- **Mypy hook invocation mechanism in pre-commit:** Validate whether using `pre-commit/mirrors-mypy` with `additional_dependencies` or `repo: local` with `entry: uv run --no-sync mypy` provides faster, more reliable execution in developer environments. Test both during Phase 2 planning/execution.
- **Desktop Schema Fallback vs Conftest Stub:** Confirm whether `notion_brain/config_schema.py` should include inline fallback classes or rely entirely on `tests/conftest.py` stubs. Both approaches eliminate Pitfall 1; conftest keeps production code cleaner.

## Sources

### Primary (HIGH confidence)
- `/pre-commit/pre-commit` (Context7) — Pre-commit hook configuration and lifecycle
- `/astral-sh/ruff` (Context7) — `ruff-pre-commit` hook specifications and version alignment
- `/pre-commit/pre-commit-hooks` (Context7) — Core pre-commit hooks configuration
- `/python/mypy` (Context7) — Pre-commit integration and config discovery
- `https://api.github.com/repos/pre-commit/mirrors-mypy/tags` (WebFetch) — Verified tag `v2.3.0` exists
- `https://api.github.com/repos/astral-sh/ruff-pre-commit/tags` (WebFetch) — Verified tag `v0.16.0` exists
- `https://api.github.com/repos/pre-commit/pre-commit-hooks/tags` (WebFetch) — Verified tag `v5.0.0` exists
- GitHub Issues #51, #52, #53 in `MNDL-27/hermes-brain` repository
- `pyproject.toml`, `mypy.ini`, and `.github/workflows/ci.yml` in repository root

### Secondary (MEDIUM confidence)
- POSIX IEEE Std 1003.1 — Portable OS discovery via `uname -s`
- Apple Open Source macOS Bash 3.2 Compatibility Notes

### Tertiary (LOW confidence)
- None.

---
*Research completed: 2026-09-20*
*Ready for roadmap: yes*
