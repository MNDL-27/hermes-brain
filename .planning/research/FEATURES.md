# Feature Research

**Domain:** Developer Experience, Contributor Tooling & Release Polish (Python / Hermes Plugin)
**Researched:** 2026-09-20
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features contributors and end users assume exist. Missing these results in broken onboarding, failed git commits, CI mismatches, or terminal crashes.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Working `.pre-commit-config.yaml` | `CONTRIBUTING.md` instructs contributors to run `pre-commit install`. Without config, command fails or creates no hooks. | LOW | Must wire `ruff-check` (`--fix`), `ruff-format` (via `astral-sh/ruff-pre-commit`), `mirrors-mypy`, and standard file hygiene (`trailing-whitespace`, `end-of-file-fixer`). |
| Pre-commit alignment with CI quality gates | Contributors expect local `git commit` checks to match GitHub Actions CI (`.github/workflows/ci.yml`). Differences cause surprise CI rejections. | LOW | Target versions in `.pre-commit-config.yaml` must match `pyproject.toml` pins (`ruff 0.16.0`, `mypy 2.3.0`, `target-version = py311`). |
| Pure unit test coverage for `config_schema.py` (#51) | Declarative schema defining Desktop panel UI surface requires regression testing so field changes do not break Desktop panel. | LOW | Test in `tests/test_config_schema.py`. Must test schema name, storage, field types, required fields (`notionApiKey`), optional fields with defaults (`hermesHome`), and secret markers. |
| Test runtime isolation / host stubbing | `notion_brain/config_schema.py` imports `plugins.memory.config_schema`. In standalone test environments, `plugins` is uninstalled. | LOW | Extend `tests/conftest.py` stubs or create test-time stub classes for `ProviderConfigSchema` and `ProviderField` so `pytest` runs offline without `ModuleNotFoundError`. |
| Darwin (macOS) detection in `scripts/install.sh` (#53) | macOS is common Hermes dev OS. Script claims Linux support but lacks `uname` check, causing confusing package-manager failure cascades. | LOW | Add `uname -s` detection at top of system detection. If `Darwin`, output clear friendly guidance pointing to README Quickstart Step 2 and exit 0 cleanly. |
| Linux distro installer preservation | Existing Linux users rely on automated setup across Ubuntu, Debian, Fedora, RHEL, Rocky, Alma, and Arch (`pacman`). | LOW | Ensure Darwin guard branches cleanly before package manager detection; Linux paths remain 100% untouched. |
| Declared `pre-commit` dev dependency | Running `pip install -e ".[dev]"` as instructed in `CONTRIBUTING.md` must install the `pre-commit` CLI executable. | LOW | Add `pre-commit` to `[project.optional-dependencies] dev` in `pyproject.toml`. |
| README & CONTRIBUTING docs sync | Documentation must accurately state macOS manual status and pre-commit workflow. | LOW | Update README installer note regarding macOS; verify `CONTRIBUTING.md` instructions match actual `.pre-commit-config.yaml` behavior. |

### Differentiators (Competitive Advantage)

Features that create exceptionally smooth DX and set this repository apart from standard plugin projects. Not strictly required, but high value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Fast local pre-commit turnaround (<1.5s) | Keeps developer velocity high. Developers do not bypass hooks with `--no-verify` when checks complete almost instantly. | MEDIUM | Utilize `astral-sh/ruff-pre-commit` (Rust binary) for combined lint and format; scope `mypy` to changed files or package boundaries. |
| Actionable terminal copy-paste for macOS | Rather than merely saying "unsupported", provide the exact 3 shell commands needed to complete manual installation directly in terminal output. | LOW | Output `python3 -m venv ~/.hermes/venv`, `pip install ...`, and `ln -s ... ~/.hermes/plugins/notion_brain` in formatted cyan/green boxes. |
| Schema immutability & contract assertions | Prevents accidental modification of Desktop config keys (`notionApiKey`, `hermesHome`) that would corrupt existing user profiles. | LOW | Assert that schema fields are tuples (immutable), keys use camelCase matching Desktop conventions, and secret fields never have plaintext defaults. |
| Centralized lint/type configs (No duplicate flags) | Hook definitions defer rule sets to `pyproject.toml` and `mypy.ini` rather than hardcoding CLI flags in `.pre-commit-config.yaml`. | LOW | Prevents configuration drift between pre-commit, local CLI runs, and GitHub Actions CI. |
| Non-destructive preflight diagnostics in installer | Warns user immediately if prerequisites (Python 3.11+ or Hermes agent directory) are missing before cloning or writing files. | LOW | Already implemented in `scripts/install.sh`; Darwin detection builds on this clean diagnostic pattern. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem appealing on the surface but introduce fragility, maintenance debt, or violate project scope constraints.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full Homebrew automation in `install.sh` | Users want single-command `curl \| bash` to install Python 3.11 and Hermes agent via `brew install`. | Homebrew environments vary wildly (Apple Silicon `/opt/homebrew` vs Intel `/usr/local`, Xcode Command Line Tools prompts, sudo requirement changes, permission failures, brew update hangs). Fragile and out of milestone scope. | Detect Darwin, print clear manual installation steps pointing to README Quickstart Step 2, and exit 0. |
| Running full `pytest` suite in pre-commit hook | Ensures no test breaks before git commit is accepted. | Unit test execution takes 5–30+ seconds. Developers get frustrated by commit latency and routinely bypass hooks using `git commit --no-verify`, eliminating all lint/format protections. | Run fast static checks (Ruff, Mypy, whitespace) in pre-commit; reserve `pytest` for CI and optional pre-push hooks. |
| Network calls / live Notion API mocks in `config_schema` tests | Test actual connection validation using config schema keys. | `config_schema.py` is pure metadata declaration for Desktop UI rendering. Adding network mocks or Notion API dependencies adds coupling, slows test runs, and risks credential leaks. | Pure unit assertions on schema structure, types, and values without network fixtures or mocks. |
| Auto-installing `pre-commit` inside `install.sh` | Sets up contributor tooling for anyone installing the package. | `install.sh` is an end-user installer for agent users, not a contributor setup script. End users do not need git hooks or development dependencies. | Keep `pre-commit` restricted to `pyproject.toml [project.optional-dependencies] dev` and `CONTRIBUTING.md`. |
| Windows native CMD/PowerShell installer within `install.sh` | Windows users want automated one-click install script. | `scripts/install.sh` is a POSIX Bash script. Running bash scripts on native Windows requires WSL or Git Bash, causing syntax and path mangling. | Instruct Windows users to use WSL2 or manual `pip install` as documented in README. |
| Auto-committing fixed files in pre-commit | Automatically stages changes made by `ruff --fix` or `ruff format`. | Auto-staging can silently commit unexpected changes or mask linting side-effects without developer review. | Let hooks fail and modify working tree files; require developer to review diff and stage intentionally. |

---

## Feature Dependencies

```
[pyproject.toml [dev] pre-commit pin]
    └──requires──> [.pre-commit-config.yaml]
                       └──wires──> [astral-sh/ruff-pre-commit (lint & format)]
                       └──wires──> [mirrors-mypy (type checking)]
                       └──wires──> [pre-commit-hooks (whitespace, eof)]

[tests/conftest.py host runtime stubs]
    └──enables──> [tests/test_config_schema.py]
                      └──verifies──> [notion_brain/config_schema.py]

[uname -s Darwin detection]
    └──enables──> [Friendly macOS guidance & clean exit 0]
    └──bypasses──> [Linux package manager detection (apt/dnf/yum/pacman)]

[.pre-commit-config.yaml] ──syncs_with──> [.github/workflows/ci.yml]
[.pre-commit-config.yaml] ──satisfies──> [CONTRIBUTING.md setup guide]
[scripts/install.sh Darwin guidance] ──references──> [README.md Quickstart Step 2]
```

### Dependency Notes

- **`tests/conftest.py` host runtime stubs enable `tests/test_config_schema.py`:** Because `notion_brain/config_schema.py` imports `plugins.memory.config_schema`, which is part of the external Hermes desktop host environment, tests cannot import `notion_brain.config_schema` without stubbing `plugins.memory.config_schema` in `tests/conftest.py`.
- **`pyproject.toml` dev dependencies enable `.pre-commit-config.yaml`:** Contributors following `CONTRIBUTING.md` run `pip install -e ".[dev]"` followed by `pre-commit install`. If `pre-commit` is missing from `pyproject.toml` dev dependencies, `pre-commit install` fails with command not found.
- **Darwin detection bypasses Linux package managers:** `uname -s` must execute before any Linux package manager checks (`apt-get`, `dnf`, `yum`, `pacman`) to prevent false-positive error exits or unexpected sudo prompts on macOS.
- **Pre-commit configuration syncs with CI workflow:** Hooks in `.pre-commit-config.yaml` must align with `ci.yml` (`quality-debt` job running ruff and mypy). If versions or rules diverge, code passing locally will fail on GitHub Actions.

---

## MVP Definition

### Launch With (v1 / Milestone Release Polish)

Minimum viable feature set required to resolve issues #51, #52, and #53, unblocking contributors and macOS users.

- [ ] **`tests/test_config_schema.py` suite (#51)** — Full test coverage of `notion_brain/config_schema.py` verifying schema identity, fields, keys, types, defaults, required vs optional, and secret flags.
- [ ] **`tests/conftest.py` stub extension (#51)** — Provide lightweight in-memory stubs for `plugins.memory.config_schema` to allow offline test execution.
- [ ] **`.pre-commit-config.yaml` configuration (#52)** — Pre-commit hook definition wiring Ruff check (`--fix`), Ruff format, Mypy type-checking, and file hygiene hooks.
- [ ] **`pyproject.toml` dev dependency update (#52)** — Add `pre-commit` to `[project.optional-dependencies] dev`.
- [ ] **Darwin OS detection in `scripts/install.sh` (#53)** — Detect `Darwin` via `uname -s` before package manager inspection, print clear guidance pointing to README Quickstart, and exit with code 0.
- [ ] **Documentation alignment (#52, #53)** — Ensure README Quickstart and CONTRIBUTING accurately reflect the macOS manual path and pre-commit setup.

### Add After Validation (v1.x)

Features to add once core contributor and installation workflows are stable.

- [ ] **Pre-push hook configuration** — Optional `pre-push` hook running `pytest -q` so fast tests run before remote push without penalizing local commits.
- [ ] **Automated hook auto-update action** — GitHub Action to periodically run `pre-commit autoupdate` via PR.
- [ ] **Interactive installer mode check** — Detect whether `install.sh` is running interactively or piped (`curl | bash`), optimizing terminal output accordingly.

### Future Consideration (v2+)

Features deferred until broader multi-platform distribution milestones.

- [ ] **Automated macOS Homebrew installer** — Dedicated brew formula or brew-based automated dependency resolution (if Hermes ecosystem adopts Homebrew).
- [ ] **Windows native installer** — PowerShell script (`install.ps1`) for native Windows developer setups.
- [ ] **Unified plugin test harness** — Shared testing utility distributed by Hermes core for validating plugin config schemas across all providers.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Unit tests for `config_schema.py` (#51) | HIGH | LOW | P1 |
| Stub `plugins.memory.config_schema` in tests (#51) | HIGH | LOW | P1 |
| Create `.pre-commit-config.yaml` matching CI (#52) | HIGH | LOW | P1 |
| Add `pre-commit` to `pyproject.toml` dev extra (#52) | HIGH | LOW | P1 |
| macOS detection & clean exit 0 in `install.sh` (#53) | HIGH | LOW | P1 |
| Manual install instructions in macOS installer output (#53) | HIGH | LOW | P1 |
| Documentation updates (README / CONTRIBUTING) | MEDIUM | LOW | P1 |
| Optional pre-push test hook | MEDIUM | LOW | P2 |
| Hook auto-update CI workflow | LOW | LOW | P3 |
| Automated Homebrew bootstrap on macOS | MEDIUM | HIGH | P3 (Anti-feature for now) |

**Priority key:**
- **P1:** Must have for milestone completion (Issues #51, #52, #53)
- **P2:** Should have, add if time permits
- **P3:** Defer to future milestone / Out of scope

---

## Competitor Feature Analysis

Comparison with standard practices in modern Python CLI and agent plugin ecosystems (e.g., Astral tools, LangChain community plugins, Anthropic SDK plugins).

| Feature | Standard Python Tooling | Common Agent Plugins | hermes-brain Release Polish Approach |
|---------|-------------------------|----------------------|--------------------------------------|
| Git Pre-Commit Hooks | Often bloated with 10+ slow hooks, causing developers to skip with `--no-verify`. | Missing entirely; relies solely on CI checks failing on PR. | Focused, ultra-fast hooks: Ruff (lint+format in <100ms), scoped Mypy, and basic whitespace. Matches CI exactly. |
| Config Schema Testing | Tested only via end-to-end integration or not tested (0% coverage). | Often unvalidated or crashes when imported outside host agent daemon. | Pure unit testing in `tests/test_config_schema.py` with mock-free host stubs; asserts contract, defaults, and secrets. |
| Cross-Platform Installer Scripts | Fails with cryptic errors on unsupported OSs (e.g., `apt-get: command not found`). | Prompts user to install unmaintained third-party dependencies or breaks system Python. | Immediate OS detection (`uname -s`); graceful exit 0 on Darwin with exact manual copy-paste instructions pointing to README. |
| Test Environment Isolation | Requires full runtime environment installed or network access. | Requires live API keys (`NOTION_API_KEY`) to run test suite. | 100% offline unit testing; host stubs in `conftest.py` ensure `pytest` runs in any standard Python 3.11–3.13 venv. |

---

## Sources

- GitHub Issues #51, #52, #53 in `MNDL-27/hermes-brain` repository
- `notion_brain/config_schema.py` and `scripts/install.sh` source files
- `.github/workflows/ci.yml` and `pyproject.toml` quality gate definitions
- Official Ruff Pre-Commit Integration Documentation (`https://github.com/astral-sh/ruff-pre-commit`)
- Official Mypy Pre-Commit Mirror Documentation (`https://github.com/pre-commit/mirrors-mypy`)
- `.planning/PROJECT.md` milestones and constraints

---
*Feature research for: Developer Experience, Contributor Tooling & Release Polish*
*Researched: 2026-09-20*
