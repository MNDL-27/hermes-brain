# Pitfalls Research

**Domain:** Python Package Developer Experience & Release Tooling (Config Schema Testing, Pre-commit Infrastructure, Shell Installer Portability)
**Researched:** 2026-09-20
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Host-Framework Import Crash in Standalone Schema Tests

**What goes wrong:**
`notion_brain/config_schema.py` imports `from plugins.memory.config_schema import ...`. `plugins` module exists only inside Hermes desktop host application runtime. Running standalone unit tests (`pytest tests/test_config_schema.py`) crashes during module collection with `ModuleNotFoundError: No module named 'plugins'`. Test suite fails completely in clean developer checkouts and CI runners.

**Why it happens:**
Desktop plugin schemas declare UI metadata using host framework base classes. Host package is not published to PyPI and not installable via `pyproject.toml` dependencies. Test author assumes host environment is always present.

**How to avoid:**
Add graceful fallback definitions inside `notion_brain/config_schema.py` using `try...except ImportError`. Define lightweight fallback classes (`ProviderConfigSchema`, `ProviderField`) or namedtuples/dataclasses when `plugins` is unavailable. In `tests/test_config_schema.py`, verify schema exports valid metadata both with and without host framework present. Never require host package installation for offline unit test execution.

**Warning signs:**
`pytest` exits with code 4 or 2 during collection. Stack trace highlights `ModuleNotFoundError: No module named 'plugins'` at top of `notion_brain/config_schema.py`.

**Phase to address:**
Phase 1 (Config Schema Testing & Isolation)

---

### Pitfall 2: Pre-Commit Mypy Environment Isolation & Missing Typeshed Stubs

**What goes wrong:**
Pre-commit hook `mirrors-mypy` fails on local git commits with `Cannot find implementation or library stub for module` (e.g. `requests`, `pytest`, or internal modules), even when `mypy notion_brain tests` passes cleanly in developer virtualenv.

**Why it happens:**
`pre-commit` runs hooks in isolated virtual environments managed in `~/.cache/pre-commit/`. By default, pre-commit environment does not contain dependencies installed in active project `.venv`. Furthermore, `pre-commit` passes staged filenames as positional arguments (`pass_filenames: true` default), bypassing `files = ["notion_brain", "tests"]` setting in `pyproject.toml` and causing mypy to fail relative import resolution.

**How to avoid:**
Configure mypy hook in `.pre-commit-config.yaml` with explicit settings:
1. Pass `additional_dependencies` specifying third-party stubs and dependencies: `[types-requests, pytest>=8.0.0]`.
2. Set `pass_filenames: false` and pass explicit target arguments `args: ["notion_brain", "tests", "--config-file=mypy.ini"]`.
3. Alternatively, use `repo: local` with `entry: uv run --no-sync mypy notion_brain tests` and `language: system` to execute directly inside project environment.

**Warning signs:**
`mypy` succeeds in terminal (`uv run mypy notion_brain tests`), but `git commit` fails with dozen unresolved import errors on staged files.

**Phase to address:**
Phase 2 (Pre-commit Hook Infrastructure)

---

### Pitfall 3: Pre-Commit vs CI Version Drift & Dual Config Divergence

**What goes wrong:**
Code passes pre-commit checks locally but fails GitHub Actions CI (`quality-debt` job), or pre-commit reformats code in way that triggers lint failures on different Python versions.

**Why it happens:**
Version numbers in `.pre-commit-config.yaml` (`rev: v0.x.x`) drift from versions pinned in `pyproject.toml` (`ruff==0.16.0`, `mypy==2.3.0`). Additionally, repo maintains both `pyproject.toml` and `mypy.ini` with conflicting override rules (e.g. `ignore_missing_imports = True` in `mypy.ini` vs strict flags in `pyproject.toml`).

**How to avoid:**
Pin pre-commit revisions to exact versions declared in `pyproject.toml` dev dependencies. Consolidate tool configurations into single authoritative file where possible, or document explicit hierarchy (`mypy.ini` overrides `pyproject.toml`). Run pre-commit validation in CI (`pre-commit run --all-files`) or keep CI commands identical to pre-commit entries.

**Warning signs:**
PR build fails on Ruff or Mypy step immediately after contributor commits with clean pre-commit run. Commit log shows churn between formatter outputs.

**Phase to address:**
Phase 2 (Pre-commit Hook Infrastructure)

---

### Pitfall 4: Platform Detection Sequencing in Shell Installers

**What goes wrong:**
`scripts/install.sh` evaluates prerequisites (Step 0.5 checking `command_exists hermes` or `python3 -c "import agent"`) and package managers (Step 1 checking `apt-get`, `dnf`, `pacman`) before checking operating system. On macOS (Darwin), script aborts at Step 0.5 with error `✗ Hermes agent not detected` (exit code 1) or fails at Step 2 with `✗ Unknown package manager`, never reaching macOS guidance.

**Why it happens:**
Platform detection placed downstream in execution flow instead of acting as early boundary gate. Script assumes target host is always Linux until package installation step.

**How to avoid:**
Execute operating system detection as Step 0 guard clause immediately following header/logging setup, before root check, Hermes check, or package manager inspection. Use `uname -s` to inspect kernel. When `Darwin`, print informative notice directing user to manual installation instructions in README Quickstart, and exit cleanly.

**Warning signs:**
Running `scripts/install.sh` on macOS machine prints red failure banners about missing Hermes or unsupported package manager, terminating with non-zero exit code.

**Phase to address:**
Phase 3 (Shell Installer Platform Detection)

---

### Pitfall 5: Non-Zero Exit Code on Graceful Informational Termination

**What goes wrong:**
Installer detects macOS, displays manual install instructions pointing to README Quickstart, but exits with `exit 1` instead of `exit 0`. CI smoke tests, automated bootstrapping scripts, and parent shell orchestrators treat installer execution as failed build.

**Why it happens:**
Developer conflates "installer did not install package on this OS" with "fatal script failure". Standard shell scripting habit assigns `exit 1` to any execution path that does not complete primary objective.

**How to avoid:**
Follow requirement specification strictly: Issue #53 dictates displaying instructions and exiting 0. Exit 0 signals script successfully determined environment and communicated intended user pathway without unexpected error. Reserve non-zero exit codes for true execution failures (e.g. network failure, permission denied, corrupted download).

**Warning signs:**
Automated multi-platform installer tests fail on macOS runner. Downstream scripts chained with `curl ... | bash && echo "success"` fail to proceed.

**Phase to address:**
Phase 3 (Shell Installer Platform Detection)

---

### Pitfall 6: Bash Portability & Shell Assumptions on macOS (Bash 3.2 vs Zsh)

**What goes wrong:**
Platform detection or shell installer uses Bash 4+ features (associative arrays `declare -A`, `readarray`, `mapfile`, `${var,,}` lowercasing, `&>/dev/null`). On macOS, `/bin/bash` is ancient GNU Bash 3.2 (frozen due to GPLv3 license). Running `bash scripts/install.sh` or piping `curl ... | bash` crashes with `syntax error near unexpected token` or `bad substitution`.

**Why it happens:**
Developer tests on Linux workstation running Bash 5.1/5.2. Developer assumes `bash` on macOS behaves identically to Linux.

**How to avoid:**
Write platform detection guard in strict POSIX-compliant syntax or Bash 3.2-compatible syntax. Use `case "$(uname -s)" in Darwin*) ... ;; esac` instead of regex or parameter expansion. Use standard redirection `> /dev/null 2>&1` instead of `&>`. Never use `declare -A` or Bash 4 builtins in early bootstrap code.

**Warning signs:**
Script execution on macOS outputs syntax errors before printing header banner.

**Phase to address:**
Phase 3 (Shell Installer Platform Detection)

---

### Pitfall 7: Shallow Schema Testing (Identity vs Contract Validation)

**What goes wrong:**
Unit tests for `config_schema.py` only verify `isinstance(CONFIG_SCHEMA, ProviderConfigSchema)` and assert `len(CONFIG_SCHEMA.fields) == 2`. Tests pass, but subtle breaking changes slip into production: field keys renamed (e.g. `notionApiKey` to `notion_api_key`), environment fallback variables omitted, default values corrupted, or placeholder text removed. Desktop UI settings panel fails to bind input fields.

**Why it happens:**
Developer writes minimum tests to satisfy line coverage metrics without asserting declarative schema contract.

**How to avoid:**
Test full declarative specification:
1. Container properties: `name == "notion_brain"`, `label == "Hermes Brain (Notion)"`, `storage == STORAGE_FLAT_JSON`.
2. Exact field key set: `{"notionApiKey", "hermesHome"}`.
3. Field types and kinds: `KIND_SECRET` for API key, `KIND_TEXT` for home directory.
4. Environment variable bindings: `env_key="NOTION_API_KEY"`, `env_fallbacks=("HERMES_HOME",)`.
5. Default values: `None` for secret key, `"~/.hermes"` for home.
6. Layout properties: `inline == True`, `group == "Connection"`.

**Warning signs:**
Coverage report shows 100% on `config_schema.py`, but desktop settings UI fails to save or load keys due to schema mismatch.

**Phase to address:**
Phase 1 (Config Schema Testing & Isolation)

---

### Pitfall 8: Staged File Churn & Formatter Hook Loops

**What goes wrong:**
Developer runs `git commit`. Pre-commit hooks run `ruff` and `ruff-format`. Hook modifies files (e.g. fixes whitespace or formats imports), causing git commit to abort. Developer re-stages and commits, but another hook alters files again or conflicts with editor formatting, creating frustrating multi-step loops.

**Why it happens:**
Hook ordering in `.pre-commit-config.yaml` executes linters, fixers, and formatters in incorrect sequence, or pre-commit rules conflict with editor auto-format settings (e.g. line-length disagreement between 88 and 100 chars).

**How to avoid:**
Sequence hooks in logical execution order:
1. Basic syntax and file sanitizers: `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`.
2. Linter with autofix: `ruff` with `args: [--fix]`.
3. Code formatter: `ruff-format`.
4. Type checker: `mypy`.
Ensure `line-length = 100` is defined in `pyproject.toml` so both `ruff` and `ruff-format` use identical configuration. Document in `CONTRIBUTING.md` that pre-commit auto-fixes files on commit failure and changes must be re-staged.

**Warning signs:**
Committing clean-looking code repeatedly fails with `Files were modified by this hook`. Discarded diffs reappear after commit attempts.

**Phase to address:**
Phase 2 (Pre-commit Hook Infrastructure)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Injecting mock `plugins` into `sys.modules` in tests | Fast test setup without changing `config_schema.py` | Leaks mock across test suite; standalone CLI/introspection crashes on import | Never. Fix `config_schema.py` with fallback classes. |
| Using `repo: local` for all pre-commit hooks | Avoids configuring pre-commit venv dependencies | Pre-commit fails completely if developer does not have `.venv` activated | Only when project environment is strictly managed by `uv` or wrapper. |
| Exiting 1 for macOS in `install.sh` | One-line change reusing existing error exit handler | Breaks automated CI testing, violates Issue #53 acceptance criteria | Never. Issue #53 requires exit 0. |
| Setting `ignore_missing_imports = True` globally in mypy | Silences missing stub errors in pre-commit | Disables type checking across entire package; misses real type bugs | Never. Use scoped `[mypy-<module>.*]` sections. |
| Testing schema with single snapshot / dict comparison | Fast test creation | Brittle tests; breaks on harmless metadata addition | Never. Assert specific semantic fields and invariants. |
| Skipping pre-commit verification in CI | Saves 30 seconds of CI build time | Hook config rots silently; contributors suffer broken hooks | Never. Validate pre-commit configuration in PR checks. |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Pre-commit + Mypy | Running `mirrors-mypy` without `types-requests` | Add `additional_dependencies: [types-requests, pytest]` in `.pre-commit-config.yaml`. |
| Pre-commit + Git Staging | Default `pass_filenames: true` passes individual files to Mypy | Set `pass_filenames: false` and specify target packages (`notion_brain`, `tests`) in `args`. |
| Ruff Linter + Ruff Formatter | Running `ruff-format` before `ruff --fix` | Place `ruff --fix` first; format code second so auto-fixes are properly formatted. |
| Shell OS Check + `/bin/sh` | Checking `$OSTYPE` variable | `$OSTYPE` is Bash/Zsh internal; unset in POSIX `sh`. Use `uname -s`. |
| Shell OS Check + Case Sensitivity | Checking `[ "$OS" = "darwin" ]` | `uname -s` returns `Darwin` with capital D. Match `Darwin` or use `case "$(uname -s)" in Darwin*)`. |
| Interactive Shell + `curl \| bash` | Using `read` from stdin when script is piped | Stdin is consumed by bash reading script. Read user input explicitly from `</dev/tty`. |
| Mypy Config Discovery | Having both `pyproject.toml` and `mypy.ini` with conflicting flags | Pass `--config-file=mypy.ini` explicitly or migrate all overrides to `pyproject.toml`. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Cold Mypy runs on every git commit | `git commit` hangs for 15-30 seconds | Use `.mypy_cache` directory or local daemon; avoid `--no-cache` | Every commit on repositories with >20 modules |
| Running entire test suite via pre-commit | Commit takes 45+ seconds; developers bypass with `--no-verify` | Keep pre-commit limited to linters, formatters, and fast type checks; run tests in pre-push or CI | Repositories with >50 test cases or integration tests |
| Uncached package downloads in pre-commit | Pre-commit re-downloads wheel dependencies on fresh clones | Leverage default `~/.cache/pre-commit` caching; avoid dynamic git URLs without tags | Fresh developer onboarding or offline git commits |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Writing secrets into user shell profiles (`~/.bashrc`, `~/.zshrc`) | Plaintext API keys exposed in world-readable files or dotfile backups | Store `NOTION_API_KEY` only in `$HERMES_HOME/.env` with strict `chmod 600` permissions. |
| Unquoted variable expansion in shell installer | Path injection or command execution if directory path contains spaces or special characters | Quote all shell variable references: `"$INSTALL_DIR"`, `"$HERMES_HOME"`, `"$PYTHON_PKG"`. |
| Running pre-commit hooks from unpinned git branches (e.g. `rev: main`) | Supply chain risk; hook code changes unpredictably outside repository review | Pin all pre-commit hook repos to exact immutable git tags or SHA hashes. |
| Insecure temporary file creation in shell scripts | Symlink race condition / arbitrary file overwrite via predictable paths in `/tmp` | Use `mktemp` utility for all scratch files (`tmp=$(mktemp)`). |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| macOS user sees scary red `✗ Hermes agent not detected` banner | User assumes software is broken on Mac; abandons setup | Display clear cyan/yellow informational banner: macOS requires manual pip setup, link README Step 2, exit 0. |
| Pre-commit fails with obscure internal traceback | Contributor disables hooks permanently using `git commit -n` | Provide clear error output; document `pre-commit run --all-files` in `CONTRIBUTING.md`. |
| Installer prompts for token when running in non-interactive CI | Script hangs waiting for input or crashes on `/dev/tty` | Detect non-interactive shell (`[ -t 0 ]` / `[ -e /dev/tty ]`); fail with helpful message or read from env. |
| Shell script overwrites existing environment variables silently | Developer's custom shell configuration silently replaced | Check existing values before prompting; confirm before updating shell profiles. |

---

## "Looks Done But Isn't" Checklist

- [ ] **Config Schema Isolation:** `python -c "import notion_brain.config_schema"` succeeds in a clean environment where `plugins` is NOT installed.
- [ ] **Config Schema Contract:** Tests assert exact field keys (`notionApiKey`, `hermesHome`), types (`KIND_SECRET`, `KIND_TEXT`), defaults, and `env_fallbacks` tuple.
- [ ] **Pre-commit File Scope:** Running `pre-commit run mypy --all-files` checks both `notion_brain` and `tests` directories without missing import errors.
- [ ] **Pre-commit Version Parity:** Versions in `.pre-commit-config.yaml` match `ruff==0.16.0` and `mypy==2.3.0` from `pyproject.toml`.
- [ ] **Pre-commit Clean Run:** `pre-commit run --all-files` exits 0 on existing codebase without requiring manual file modifications.
- [ ] **Darwin Detection Early Exit:** Running `scripts/install.sh` on macOS exits 0 and prints README Quickstart guidance, even if Hermes is NOT installed and root check is bypassed.
- [ ] **Darwin Exit Code:** Verified with `bash scripts/install.sh; echo $?` returning `0` on Darwin.
- [ ] **POSIX Shell Syntax:** Shell platform detection uses `uname -s` and POSIX constructs without Bash 4+ dependencies (`declare -A`, `${var,,}`).

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Pre-commit virtualenv corrupted or failing | LOW | Run `pre-commit clean` followed by `pre-commit install --install-hooks` to rebuild cache. |
| Mypy import error cascade in pre-commit | LOW | Verify `types-requests` and target stubs are present in `additional_dependencies`. Check `mypy.ini` override sections. |
| `config_schema.py` breaking desktop import | LOW | Revert schema changes; ensure fallback class implementation preserves identical attribute signatures to host classes. |
| Staged commit stuck in pre-commit loop | LOW | Run `ruff check --fix . && ruff format .` manually, stage all changed files (`git add -u`), then commit. |
| Installer crashes on macOS systems | LOW | Move OS detection block above Step 0.5; replace non-POSIX parameter substitutions with standard `case` block. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Host-framework import crash (Pitfall 1) | Phase 1: Config Schema Tests & Isolation | Run `python -c "import notion_brain.config_schema"` in isolated subshell; execute `pytest tests/test_config_schema.py`. |
| Shallow schema testing (Pitfall 7) | Phase 1: Config Schema Tests & Isolation | Verify test suite asserts keys, kinds, env fallbacks, and defaults; mutations in schema fail tests. |
| Pre-commit Mypy isolation & stubs (Pitfall 2) | Phase 2: Pre-Commit Hook Infrastructure | Execute `pre-commit run --all-files` on fresh commit; verify Mypy checks all files without stub errors. |
| Pre-commit vs CI version drift (Pitfall 3) | Phase 2: Pre-Commit Hook Infrastructure | Audit `rev` tags in `.pre-commit-config.yaml` against `pyproject.toml` pins; verify CI runs identical checks. |
| Formatter hook churn & ordering (Pitfall 8) | Phase 2: Pre-Commit Hook Infrastructure | Verify hook order: sanitizers -> ruff --fix -> ruff-format -> mypy; test committing unformatted file. |
| Platform detection sequencing (Pitfall 4) | Phase 3: Shell Installer OS Detection | Mock `uname` returning `Darwin`; run `install.sh`; verify output shows manual instructions without Hermes check error. |
| Non-zero exit code on Darwin (Pitfall 5) | Phase 3: Shell Installer OS Detection | Execute installer under Darwin condition; assert exit status equals 0 (`echo $?` -> 0). |
| Bash 3.2 portability issues (Pitfall 6) | Phase 3: Shell Installer OS Detection | Run script through `shellcheck -s bash` and test under macOS default `/bin/bash` shell. |

---

## Sources

- [Hermes Brain Project Context & Active Issues #51, #52, #53](.planning/PROJECT.md)
- [Hermes Brain Codebase Concerns & Known Import Bugs](.planning/codebase/CONCERNS.md)
- [Pre-commit Official Documentation — Creating New Hooks & Isolated Environments](https://pre-commit.com/)
- [Mypy Documentation — Running Mypy in Pre-commit & Missing Imports Handling](https://mypy.readthedocs.io/)
- [Ruff Documentation — Pre-commit Hook Integration & Formatter Ordering](https://docs.astral.sh/ruff/integrations/#pre-commit)
- [Apple Open Source & macOS Bash 3.2 Compatibility Notes](https://support.apple.com/en-us/HT208050)

---
*Pitfalls research for: hermes-brain release polish (config schema tests, pre-commit hooks, shell installer OS detection)*
*Researched: 2026-09-20*
