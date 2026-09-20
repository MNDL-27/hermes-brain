# Architecture Research

**Domain:** Agent Memory Plugin, Quality Assurance, & CI/CD Tooling
**Researched:** 2026-09-20
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Developer & Contributor Loop                       │
├──────────────────────────────────────┬──────────────────────────────────────┤
│          Local Git Hooks             │          Test Suite Execution        │
│      `.pre-commit-config.yaml`       │   `pytest tests/test_config_schema`  │
│  (ruff lint/format, mypy, hygiene)   │      (isolated runtime stubs)        │
└──────────────────┬───────────────────┴──────────────────┬───────────────────┘
                   │                                      │
                   ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Continuous Integration (CI)                         │
│                         `.github/workflows/ci.yml`                          │
├──────────────────┬───────────────────┬──────────────────┬───────────────────┤
│  Matrix Tests    │     Coverage      │   Quality Debt   │  Package Build    │
│  Py 3.11–3.13    │   `pytest-cov`    │   `ruff`+`mypy`  │  `build`+`twine`  │
└──────────────────┴───────────────────┴──────────────────┴───────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Package Distribution & Installation                      │
├──────────────────────────────────────┬──────────────────────────────────────┤
│         Linux Distribution           │          macOS / Darwin Host         │
│          `scripts/install.sh`        │          `scripts/install.sh`        │
│   (apt/dnf/pacman + setup wizard)    │   (clean exit 0 + README guidance)   │
└──────────────────────────────────────┴──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Hermes Brain Runtime Architecture                     │
├──────────────────────────────────────┬──────────────────────────────────────┤
│       Desktop Settings Panel         │     Agent Memory Provider Plugin     │
│   `notion_brain/config_schema.py`    │   `notion_brain/provider.py` & store │
│  (introspected `CONFIG_SCHEMA`)      │  (sync turns, tools, Notion API REST)│
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `test_config_schema.py` | Validates declared UI surface, field types, required/optional boundaries, and defaults for Hermes Desktop without network or external runtime dependencies. | `pytest` test module consuming isolated `conftest.py` stubs for `plugins.memory.config_schema`. |
| `tests/conftest.py` | Provides test isolation stubs for undeclared Hermes agent runtime modules (`agent`, `tools`, and `plugins.memory.config_schema`). | Python `types.ModuleType` registration in `sys.modules` before test discovery. |
| `.pre-commit-config.yaml` | Enforces git pre-commit quality gates locally: code hygiene, ruff linting, ruff code formatting, and mypy static type analysis matching CI. | Pre-commit hook definitions pinned to matching `pyproject.toml` tool versions (`ruff v0.16.0`, `mypy 2.3.0`). |
| `.github/workflows/ci.yml` | Validates multi-version compatibility (Python 3.11, 3.12, 3.13), branch test coverage, ruff/mypy quality checks, and sdist/wheel packaging. | GitHub Actions workflow executed on push/PR to `main` using `astral-sh/setup-uv` and locked dependencies. |
| `scripts/install.sh` | Orchestrates onboarding and dependency bootstrap on Linux; intercepts macOS (Darwin) hosts with formatted guidance and non-error exit. | POSIX-compatible Bash script with early `uname -s` OS detection, token validation, and workspace bootstrapping. |
| `notion_brain/config_schema.py` | Declares the schema contract consumed by Hermes Desktop's settings UI to configure Notion credentials and workspace paths. | Python dataclass-like instances (`ProviderConfigSchema`, `ProviderField`) defining fields, kinds, env keys, and defaults. |

## Recommended Project Structure

```
hermes-brain/
├── .github/
│   └── workflows/
│       └── ci.yml                   # Matrix tests (3.11-3.13), coverage, lint, package checks
├── .pre-commit-config.yaml          # Local commit gate: hooks, ruff format/check, mypy
├── notion_brain/
│   ├── __init__.py                  # Plugin export & lazy runtime discovery
│   ├── config_schema.py             # Declarative desktop config surface
│   ├── provider.py                  # Plugin lifecycle & tool dispatch
│   ├── store.py                     # Notion REST client & retries
│   ├── schema.py                    # BrainEntry, domains, secret redaction
│   └── bootstrap.py                 # Workspace setup & repair
├── scripts/
│   └── install.sh                   # Distro bootstrapper with Darwin early exit
├── tests/
│   ├── conftest.py                  # Runtime stubs (agent, tools, plugins.memory)
│   ├── test_config_schema.py        # Schema unit tests (keys, types, defaults, envs)
│   ├── test_provider.py             # Provider lifecycle & tool tests
│   └── test_store.py                # Store API & redaction tests
├── mypy.ini                         # Mypy module ignore rules (plugins.*, agent.*)
└── pyproject.toml                   # Build config, tool settings (ruff, mypy, pytest)
```

### Structure Rationale

- **`tests/conftest.py` stubbing boundary:** Hermes runtime packages (`agent`, `tools`, `plugins.memory`) are external environments provided by the host agent rather than hard project dependencies. Centralizing all stubs in `conftest.py` prevents scattered mock logic across individual test files and keeps tests pure stdlib/pytest.
- **`.pre-commit-config.yaml` at repository root:** Standard git hook discovery location. Must mirror `.github/workflows/ci.yml` so contributors catch lint and type errors before pushing.
- **`scripts/install.sh` shell isolation:** Lives outside the Python package tree. Must execute cleanly in raw `/bin/bash` without requiring prior Python packages to detect unsupported platforms.

## Architectural Patterns

### Pattern 1: Runtime Protocol Stubbing (Decoupled Host Contract)

**What:** In the Hermes plugin ecosystem, host frameworks inject runtime packages (e.g. `plugins.memory.config_schema`, `agent.memory_provider`) into `sys.modules`. In offline testing and CI, these host packages are absent. Rather than adding the entire agent framework as a heavy dev dependency or failing test imports, `tests/conftest.py` installs minimal stub modules into `sys.modules` before test discovery.

**When to use:** Whenever testing plugin packages that consume host runtime protocols or GUI schemas declared outside the plugin's direct dependencies.

**Trade-offs:** Fast offline tests without heavy virtualenv dependencies. Requires keeping stub attribute signatures in sync with upstream Hermes host protocols.

**Example:**
```python
# tests/conftest.py
import sys
import types

# Stub plugins.memory.config_schema for desktop config tests
if "plugins.memory.config_schema" not in sys.modules:
    plugins_mod = types.ModuleType("plugins")
    plugins_mem_mod = types.ModuleType("plugins.memory")
    schema_mod = types.ModuleType("plugins.memory.config_schema")

    # Protocol constants
    schema_mod.KIND_SECRET = "secret"
    schema_mod.KIND_TEXT = "text"
    schema_mod.STORAGE_FLAT_JSON = "flat_json"

    # Schema carrier classes
    class ProviderConfigSchema:
        def __init__(self, name, label, storage, fields):
            self.name = name
            self.label = label
            self.storage = storage
            self.fields = tuple(fields)

    class ProviderField:
        def __init__(self, key, label, kind, description="", default=None,
                     env_key=None, env_fallbacks=(), placeholder="", inline=False, group=""):
            self.key = key
            self.label = label
            self.kind = kind
            self.description = description
            self.default = default
            self.env_key = env_key
            self.env_fallbacks = tuple(env_fallbacks)
            self.placeholder = placeholder
            self.inline = inline
            self.group = group

    schema_mod.ProviderConfigSchema = ProviderConfigSchema
    schema_mod.ProviderField = ProviderField

    sys.modules["plugins"] = plugins_mod
    sys.modules["plugins.memory"] = plugins_mem_mod
    sys.modules["plugins.memory.config_schema"] = schema_mod
```

### Pattern 2: Tooling Parity Mirror (Local Pre-commit ↔ CI Pipeline)

**What:** Align pre-commit hook versions and invocations strictly with `.github/workflows/ci.yml` and `pyproject.toml`. Instead of running arbitrary or unpinned global linters, `.pre-commit-config.yaml` locks tool versions (`ruff==0.16.0`, `mypy==2.3.0`) and targets the same file scopes (`notion_brain`, `tests`).

**When to use:** In open-source repositories where contributors have diverse local operating systems and IDE setups, preventing CI failures on pull requests.

**Trade-offs:** Pre-commit run takes 2–5 seconds on commit, but eliminates frustrating multi-round CI failure cycles.

**Example:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.0
    hooks:
      - id: ruff
        args: [--fix]
        files: ^(notion_brain|tests)/
      - id: ruff-format
        files: ^(notion_brain|tests)/

  - repo: local
    hooks:
      - id: mypy
        name: mypy typecheck
        entry: uv run --no-sync mypy notion_brain tests
        language: system
        types: [python]
        pass_filenames: false
```

### Pattern 3: Non-Destructive Platform Guard (Friendly Early Exit)

**What:** In onboarding or installation shell scripts, detect unsupported operating systems (such as macOS Darwin) immediately after root validation and before attempting package manager invocations (`apt-get`, `dnf`, `yum`, `pacman`). Display styled, actionable manual installation instructions pointing to canonical documentation, and exit with code `0`.

**Why exit 0:** An exit code of `1` signifies a script crash or environment corruption. In automation contexts or pipe-to-shell workflows (`curl | bash`), an unsupported OS warning should cleanly communicate the manual steps rather than dumping a terminal stacktrace or package manager error.

**Trade-offs:** Script completes cleanly without installing packages, requiring the developer to read the displayed manual steps.

**Example:**
```bash
# scripts/install.sh (Early Guard after Step 0)
if [ "$(uname -s)" = "Darwin" ]; then
    echo ""
    info "╔══════════════════════════════════════════════════════════╗"
    info "║           macOS (Darwin) Detected                        ║"
    info "╚══════════════════════════════════════════════════════════╝"
    echo ""
    warn "Automated package-manager installation is not supported on macOS."
    echo ""
    echo "  Follow the Quickstart manual install in README.md (Step 2):"
    echo ""
    echo "    1. Install into Hermes virtual environment:"
    echo "       ~/.hermes/hermes-agent/venv/bin/pip install -e ."
    echo ""
    echo "    2. Or symlink into your Hermes user plugins directory:"
    echo "       mkdir -p ~/.hermes/plugins"
    echo "       ln -s \"\$(pwd)/notion_brain\" ~/.hermes/plugins/notion_brain"
    echo ""
    echo "    3. Symlink companion skill:"
    echo "       mkdir -p ~/.hermes/skills"
    echo "       ln -s \"\$(pwd)/skills/notion-brain\" ~/.hermes/skills/notion-brain"
    echo ""
    info "Refer to README.md for configuration details."
    exit 0
fi
```

## Data Flow

### Invocation & Verification Flow

```
[Contributor / CI Action]
         │
         ├──► 1. Pre-Commit Hook (`.pre-commit-config.yaml`)
         │      ├─ Check file whitespace & syntax
         │      ├─ `ruff check --fix notion_brain tests`
         │      ├─ `ruff format notion_brain tests`
         │      └─ `mypy notion_brain tests`
         │
         ├──► 2. Test Runner (`uv run pytest`)
         │      ├─ `tests/conftest.py` stubs `agent.*`, `tools.*`, `plugins.memory.*`
         │      ├─ `tests/test_config_schema.py` imports `CONFIG_SCHEMA`
         │      │    └─ Validates keys, kinds, env_keys, fallbacks, defaults
         │      └─ Runs 296+ existing provider, store, and extraction tests
         │
         ├──► 3. Packaging & Build (`build` + `twine check`)
         │      ├─ Validates `pyproject.toml` distribution metadata
         │      └─ Packages `notion_brain` wheel including `config_schema.py`
         │
         └──► 4. End-User Installation (`scripts/install.sh`)
                ├─ Linux Host: Detects distro, prompts key, runs `ensure_brain`
                └─ Darwin Host: Emits README Step 2 instructions, exits 0
```

### State Management

```
┌─────────────────────────────────────────────────────────────┐
│                    Static Configuration                     │
│  `notion_brain/config_schema.py` (Immutable Dataclasses)    │
│  - Storage: STORAGE_FLAT_JSON ("flat_json")                 │
│  - Field 1: "notionApiKey" (KIND_SECRET, NOTION_API_KEY)    │
│  - Field 2: "hermesHome" (KIND_TEXT, HERMES_HOME, default)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
            Hermes Desktop App │ Reads schema definition
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Desktop UI Settings Render                  │
│  - Masked password input for NOTION_API_KEY                 │
│  - Text input with ~/.hermes placeholder for HERMES_HOME    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ Writes user credentials
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Persistent Target Storage                   │
│  `~/.hermes/.env` (NOTION_API_KEY=ntn_..., chmod 600)       │
│  `~/.hermes/notion_brain.json` (parent_page_id, db_* IDs)   │
└─────────────────────────────────────────────────────────────┘
```

### Key Invocation Flows

1. **Config Schema Unit Test Flow:**
   `pytest` discovers `tests/test_config_schema.py`. `tests/conftest.py` executes first, registering dummy modules for `plugins.memory.config_schema`. The test imports `notion_brain.config_schema.CONFIG_SCHEMA`, verifying field count (exactly 2), keys (`notionApiKey`, `hermesHome`), kinds (`KIND_SECRET`, `KIND_TEXT`), security flags (inline, group), env variables, and tuple immutability without making any network calls or disk modifications.
2. **Local Commit Quality Gate Flow:**
   Developer invokes `git commit`. Git pre-commit hook triggers `.pre-commit-config.yaml`. Fast file hygiene hooks execute on modified files. `ruff check` and `ruff format` run scoped to `notion_brain/` and `tests/`. `mypy` executes across the source files. If any check fails, the commit is aborted before reaching remote CI.
3. **Continuous Integration Matrix Flow:**
   Code is pushed to GitHub. GitHub Actions executes `.github/workflows/ci.yml`. Python versions 3.11, 3.12, and 3.13 run `pytest` in parallel. Coverage is computed and checked. The `quality-debt` job executes `ruff check` and `mypy` to verify strict typing. The `package` job builds the distribution artifacts and validates metadata.
4. **Installer Darwin Execution Flow:**
   A macOS user executes `curl -fsSL https://raw.../install.sh | bash`. The script detects non-root execution, checks `$(uname -s)`. Matching `Darwin`, it prints an informative notice directing the user to manual pip/symlink workflows from README Step 2, and cleanly exits with status code 0.

## Scaling & Maintainability Considerations

| Area | Small Scale (Single Contributor) | Team Scale (Multiple Contributors) | Release / Ecosystem Scale |
|------|-----------------------------------|-----------------------------------|----------------------------|
| **Git Hooks** | Optional manual runs (`ruff check`, `mypy`). | Enforced via `.pre-commit-config.yaml` to prevent style bike-shedding. | Integrated with CI branch protections and automated bot fixes. |
| **Config Surface** | Flat manual editing of `~/.hermes/.env`. | Tested declarative `CONFIG_SCHEMA` ensuring desktop panel compatibility. | Versioned configuration schema supporting multiple backends. |
| **Installation** | Manual git clone and editable pip install. | `scripts/install.sh` supporting mainstream Linux distributions. | PyPI packages and standalone brew/apt packaging recipes. |

### Scaling & Architecture Priorities

1. **Test Isolation First:** Testing `config_schema.py` must never depend on whether Hermes Agent or Hermes Desktop is installed on the testing machine. Runtime mocking in `conftest.py` isolates unit tests from host ecosystem changes.
2. **CI / Pre-commit Tool Parity:** The local pre-commit hook must use the exact same tool versions as CI (`ruff 0.16.0`, `mypy 2.3.0`). Divergence between local pre-commit and remote CI creates contributor friction.
3. **Platform Safety:** The shell installer must never attempt package manager commands (`apt-get`, `dnf`) on unsupported platforms like macOS or BSD, preventing system package database corruption.

## Anti-Patterns

### Anti-Pattern 1: Leaking External Runtime Stubs into Production Code

**What people do:** Placing conditional import checks or mock classes inside `notion_brain/config_schema.py` (e.g. `try: import plugins ... except ImportError: class ProviderField ...`).
**Why it's wrong:** Pollutes production package code with testing shims. If the host environment has a broken or partial import, fallback shims can mask configuration bugs in production.
**Do this instead:** Keep production code strictly declaring its protocol imports (`from plugins.memory.config_schema import ...`). Place all test stubs inside `tests/conftest.py` so production runtime boundaries remain untainted.

### Anti-Pattern 2: Unscoped Ruff Formatting in Pre-Commit

**What people do:** Configuring `ruff-format` or `ruff check` across the entire repository (`.`) in `.pre-commit-config.yaml` when repository documentation or planning files contain non-standard markdown tables or snippets.
**Why it's wrong:** Causes commits touching documentation (`.planning/`, `README.md`) to fail pre-commit hooks due to unformatted code blocks in markdown, blocking unrelated feature work.
**Do this instead:** Scope ruff hooks in `.pre-commit-config.yaml` strictly to Python codebases: `files: ^(notion_brain|tests)/`.

### Anti-Pattern 3: Hard-Failing Installer on macOS with Exit 1

**What people do:** Emitting an error message and exiting with code `1` when Darwin is detected in `scripts/install.sh`.
**Why it's wrong:** Exit code `1` indicates an abnormal termination or script failure. For developers running evaluation scripts or automation pipelines, this appears as a broken script rather than an intentional redirection to manual setup.
**Do this instead:** Detect Darwin early, display clear manual installation instructions referencing README Step 2, and exit `0`.

### Anti-Pattern 4: Using Mirrors-Mypy without Dependency Alignment

**What people do:** Adding `mirrors-mypy` to `.pre-commit-config.yaml` without installed third-party dependencies (`requests`, `types-requests`).
**Why it's wrong:** Pre-commit runs `mypy` in an isolated virtual environment. Without the project's dependencies and types, `mypy` throws false positive missing import errors that don't occur in CI.
**Do this instead:** Use `language: system` with entry `uv run --no-sync mypy notion_brain tests` or explicitly declare `additional_dependencies: ["requests>=2.28", "types-requests"]` and specify `mypy.ini` configuration path.

## Integration Points

### External Services & Host Frameworks

| Service / Interface | Integration Pattern | Notes |
|---------------------|---------------------|-------|
| **Hermes Desktop** | Introspects `notion_brain.config_schema:CONFIG_SCHEMA` | Renders settings UI based on `ProviderField` definitions (`notionApiKey`, `hermesHome`). |
| **Hermes Agent Runtime** | Entry point discovery via `project.entry-points."hermes_agent.memory_providers"` | Dynamically loads `NotionBrainProvider` on agent startup. |
| **GitHub Actions** | Workflow triggers on `push` and `pull_request` to `main` | Runs matrix test suite, code coverage, ruff lint, mypy typecheck, and twine validation. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `test_config_schema` ↔ `config_schema.py` | Python module import | Direct inspection of `CONFIG_SCHEMA.fields`, ensuring field keys, kinds, env bindings, and defaults conform to specification. |
| `tests/conftest.py` ↔ `sys.modules` | Python runtime module injection | Pre-populates `agent.*`, `tools.*`, and `plugins.memory.config_schema` before test discovery. |
| `.pre-commit-config.yaml` ↔ `pyproject.toml` | Version & rule alignment | Pre-commit runs ruff and mypy using configurations declared in `pyproject.toml` and `mypy.ini`. |
| `scripts/install.sh` ↔ `notion_brain` | Subprocess CLI invocation | Invokes `python3 -m notion_brain health` and `ensure_brain()` on Linux after verifying prerequisites. |

## Suggested Build Order & Dependencies

The three focus areas have specific architectural dependencies that dictate the optimal execution sequence:

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Config Schema Test Infrastructure (#51)           │
│  - Update `tests/conftest.py` with `plugins.memory` stubs   │
│  - Implement `tests/test_config_schema.py`                  │
│  - Verify with `pytest` and `mypy notion_brain tests`       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ Unblocks clean test & type status
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: Pre-Commit Configuration & Tooling Parity (#52)   │
│  - Create `.pre-commit-config.yaml`                         │
│  - Pin ruff (v0.16.0) and mypy (2.3.0)                      │
│  - Scope hooks to `^(notion_brain|tests)/`                  │
│  - Verify `pre-commit run --all-files` passes               │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ Tooling guardrails active
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: Installer Platform Guard (#53)                    │
│  - Add early `Darwin` platform check in `scripts/install.sh`│
│  - Display README Step 2 manual installation instructions   │
│  - Ensure clean `exit 0`                                    │
│  - Validate across simulated subshells                      │
└─────────────────────────────────────────────────────────────┘
```

### Build Order Rationale

1. **Phase 1 First (`tests/test_config_schema.py`):** The config schema already exists in `notion_brain/config_schema.py` but has zero test coverage. Adding `plugins.memory` stubbing to `tests/conftest.py` and creating `test_config_schema.py` ensures the entire test suite and static type analysis are 100% green before introducing pre-commit enforcement.
2. **Phase 2 Second (`.pre-commit-config.yaml`):** Pre-commit hooks should only be enabled once the codebase is known to pass all lint, formatting, and type checks. Enforcing pre-commit prior to Phase 1 would risk hook failures on unstubbed imports or formatting discrepancies.
3. **Phase 3 Third (`scripts/install.sh`):** Modifying the shell installer is completely decoupled from the Python test suite and git hook configurations. It can be implemented and validated independently as the final release-readiness polish step.

## Sources

- `.github/workflows/ci.yml` — Continuous integration configuration and test matrix
- `pyproject.toml` & `mypy.ini` — Package metadata, dependency locks, and lint/type configurations
- `notion_brain/config_schema.py` — Declared desktop configuration surface
- `scripts/install.sh` — Existing distro installation and onboarding script
- `CONTRIBUTING.md` — Contributor workflow and code quality guidelines
- `.planning/PROJECT.md` — Milestone goals, requirements, and constraints

---
*Architecture research for: hermes-brain release polish*
*Researched: 2026-09-20*
