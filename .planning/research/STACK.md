# Technology Stack

**Domain:** hermes-brain Release Polish (Config Schema Testing, Pre-commit Hook Integration, macOS Platform Detection)
**Researched:** 2026-09-20
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `pre-commit` | `^4.1.0` | Multi-language Git pre-commit hook framework | Industry standard for Python repositories. Native support for Python 3.11–3.13, virtualenv isolation, deterministic hook execution. Enforces CONTRIBUTING.md requirements locally before CI push. |
| `pytest` | `9.1.1` | Unit test execution runner and assertion framework | Already pinned in `pyproject.toml` and CI. Native Python assertions, zero runtime overhead, rich failure introspection for testing declarative schema structures without external libraries. |
| POSIX `uname -s` / Bash 4+ | POSIX standard | Operating system detection in `scripts/install.sh` | Portable, zero-dependency POSIX detection across all Darwin/Linux environments. Replaces brittle Bash-only `$OSTYPE` and Linux-specific `/etc/os-release`. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `astral-sh/ruff-pre-commit` | `v0.16.0` | Git hook repository running Ruff linter and formatter | Run on every git commit. Matches `ruff==0.16.0` in `pyproject.toml`. Executes `ruff` with `--fix` and `ruff-format`. |
| `pre-commit/mirrors-mypy` | `v2.3.0` | Git hook repository running Mypy static type checker | Run on git commit before push. Matches `mypy==2.3.0` in `pyproject.toml`. Scoped to `^(notion_brain\|tests)/` with `--config-file=mypy.ini`. |
| `pre-commit/pre-commit-hooks` | `v5.0.0` | Core sanity checks (whitespace, EOF, YAML, TOML, conflict markers) | Run on every git commit. Prevents trailing whitespace, broken TOML/YAML syntax, committed merge conflicts, and accidental large file check-ins. |
| `pytest-cov` | `7.1.0` | Branch coverage measurement and reporting | Run during test execution (`--cov=notion_brain`) to verify branch and line coverage for `config_schema.py`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Package and virtualenv manager | Fast resolution and syncing (`uv sync --extra dev`). Used in CI and local workflows. |
| `ruff` (`0.16.0`) | Linter and code formatter | Configured in `pyproject.toml` (`target-version = "py311"`, `select = ["E", "F", "W", "I"]`, `ignore = ["E501"]`). |
| `mypy` (`2.3.0`) | Static type checker | Configured via `mypy.ini` (ignoring missing imports for unstubbed `requests.*`, `agent.*`, `tools.*`, `plugins.*`) and `pyproject.toml`. |

## Installation

```bash
# Add pre-commit to pyproject.toml [project.optional-dependencies] dev:
# "pre-commit>=4.1.0",

# Sync development environment using uv:
uv sync --extra dev

# Install git hook scripts into .git/hooks:
uv run pre-commit install
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `pre-commit` framework | `lefthook` | Use when multi-language repository requires ultra-fast Go binary without Python dependency. Not needed here since project is 100% Python and contributor doc already specifies `pre-commit install`. |
| `pre-commit` framework | Raw `.git/hooks/pre-commit` bash script | Use for single-developer zero-dependency repos. Brittle across cross-platform teams; lacks automatic virtualenv sandboxing and hook auto-updating. |
| `astral-sh/ruff-pre-commit` | `repo: local` running `uv run ruff` | Use if developers must guarantee exact local venv interpreter. Git repo hook `astral-sh/ruff-pre-commit` provides isolated pre-built binaries that do not require an active venv. |
| Pure `pytest` unit tests for `config_schema.py` | `pydantic` / `jsonschema` | Use if desktop schema required runtime schema validation against JSON schemas. `config_schema.py` is an internal static tuple definition; standard pytest assertions test field types and defaults with zero extra dependencies. |
| `uname -s` detection | `$OSTYPE` inspection | Use if script is guaranteed to execute exclusively in Bash. `$OSTYPE` is undefined in pure POSIX `/bin/sh` or alternate shells. `uname -s` is universally available. |
| `uname -s` detection | `/etc/os-release` parsing | Use for Linux distribution discrimination (Debian vs RHEL). `/etc/os-release` does not exist on macOS (Darwin). |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `pydantic` or `jsonschema` validation dependencies | Adds unnecessary heavy dependencies and build overhead for a 38-line declarative configuration schema. Hermes desktop interface uses simple dataclass/tuple semantics. | Native Python assertions in `tests/test_config_schema.py` with mock/stub fixtures for `plugins.memory.config_schema`. |
| Mismatched hook revisions (e.g. `ruff-pre-commit` `v0.9.x` or latest `v0.17+`) | Causes formatting drift and rule discrepancies between local commits and CI (`ruff==0.16.0` in `pyproject.toml`). | Pin `rev: v0.16.0` in `.pre-commit-config.yaml` to match `pyproject.toml` dev dependency. |
| Mismatched `mirrors-mypy` revision (e.g. `v1.x` or unpinned `master`) | Mypy 1.x and 2.x have different type-inference semantics and flags. Divergence leads to local commits passing while CI fails, or vice-versa. | Pin `rev: v2.3.0` in `.pre-commit-config.yaml` to match `pyproject.toml` dev dependency. |
| `exit 1` on macOS Darwin detection in `scripts/install.sh` | Fails the curl-pipe-bash script abruptly, giving users an impression of crash or installation error. Violates key project decision for issue #53. | Print clear manual guidance pointing to README Quickstart and exit with status code `0`. |
| Automated Homebrew package bootstrap (`brew install ...`) in `scripts/install.sh` | Out of scope for release polish (PROJECT.md). High maintenance burden, permission variations, Homebrew path differences across Apple Silicon and Intel. | Clean guidance directing user to manual `pip install` or venv symlink steps. |
| Bash-specific `[[ "$OSTYPE" == "darwin"* ]]` in POSIX scripts | Non-portable across minimal shell interpreters or `/bin/sh` symlinks. | Standard POSIX `case "$(uname -s)" in Darwin) ... ;; esac`. |

## Stack Patterns by Variant

**If running local development with Git:**
- Run `uv run pre-commit install` once after cloning.
- Pre-commit executes `ruff --fix`, `ruff-format`, `mirrors-mypy`, and file sanitation on staged files before commit.
- Catches lint and type errors in milliseconds before pushing.

**If executing in GitHub Actions CI:**
- Pre-commit does not need to duplicate CI steps.
- CI runs `uv run --no-sync ruff check` and `uv run --no-sync mypy` across the entire workspace in `quality-debt` job.
- Pre-commit configuration guarantees contributors locally adhere to CI expectations.

**If running `scripts/install.sh` on macOS (Darwin):**
- Early detection branch:
  ```bash
  OS="$(uname -s)"
  case "$OS" in
      Darwin)
          info "macOS detected."
          echo ""
          echo "  Automated installer currently supports Linux (Ubuntu, Debian, Fedora, RHEL)."
          echo "  For macOS, follow the manual installation guide in README.md:"
          echo "    https://github.com/MNDL-27/hermes-brain#quickstart"
          echo ""
          exit 0
          ;;
  esac
  ```
- Exits cleanly with code 0. Prevents Linux package manager (`apt-get`, `dnf`, `pacman`) execution failure.

## Version Compatibility

| Package / Tool | Compatible With | Notes |
|----------------|-----------------|-------|
| `pre-commit` `4.1.0` | Python 3.11, 3.12, 3.13 | Full support for modern Python versions; manages isolated virtualenvs cleanly. |
| `astral-sh/ruff-pre-commit` `v0.16.0` | `ruff==0.16.0` | Identical rule set (`E`, `F`, `W`, `I`, ignore `E501`) and format outputs. |
| `pre-commit/mirrors-mypy` `v2.3.0` | `mypy==2.3.0` | Reads `mypy.ini` in workspace root. Matches CI typecheck behavior. |
| `pre-commit/pre-commit-hooks` `v5.0.0` | Git 2.25+ | Stable baseline for standard whitespace, line endings, and file syntax sanity. |
| `pytest` `9.1.1` | Python 3.11, 3.12, 3.13 | Supports `unittest.mock`, `types.ModuleType` stubbing, and strict test markers. |

## Recommended `.pre-commit-config.yaml` Specification

```yaml
default_language_version:
  python: python3.11

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        args: [--markdown-linebreak-ext=md]
      - id: end-of-file-fixer
      - id: check-yaml
        args: [--unsafe]
      - id: check-toml
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: mixed-line-ending
        args: [--fix=lf]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v2.3.0
    hooks:
      - id: mypy
        files: ^(notion_brain|tests)/
        args: [--config-file=mypy.ini]
```

## Sources

- `/pre-commit/pre-commit` (Context7) — Pre-commit hook configuration and lifecycle
- `/astral-sh/ruff` (Context7) — `ruff-pre-commit` hook specifications and version alignment
- `/pre-commit/pre-commit-hooks` (Context7) — Core pre-commit hooks configuration
- `/python/mypy` (Context7) — Pre-commit integration and config discovery
- `https://api.github.com/repos/pre-commit/mirrors-mypy/tags` (WebFetch) — Verified tag `v2.3.0` exists
- `https://api.github.com/repos/astral-sh/ruff-pre-commit/tags` (WebFetch) — Verified tag `v0.16.0` exists
- `https://api.github.com/repos/pre-commit/pre-commit-hooks/tags` (WebFetch) — Verified tag `v5.0.0` exists
- POSIX IEEE Std 1003.1 — Portable OS discovery via `uname -s`

---
*Stack research for: hermes-brain release polish*
*Researched: 2026-09-20*
