# Requirements: hermes-brain

**Defined:** 2026-09-20
**Core Value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.

## v1 Requirements

Requirements for Release Polish milestone addressing issues #51, #52, and #53. Each maps to roadmap phases.

### Config Schema Testing

- [ ] **SCHEMA-01**: Unit test suite in `tests/test_config_schema.py` verifies `notion_brain/config_schema.py` schema name, storage key, and declared property fields.
- [ ] **SCHEMA-02**: Tests verify property kinds, defaults, secret status (`notionApiKey` has no default), and tuple immutability.
- [ ] **SCHEMA-03**: Lightweight runtime stubs for `plugins.memory.config_schema` in `tests/conftest.py` ensure `pytest` runs offline without `ModuleNotFoundError` when host Hermes is absent.

### Pre-Commit Quality Gates

- [ ] **HOOK-01**: `.pre-commit-config.yaml` is added to repository root wiring `astral-sh/ruff-pre-commit` (v0.16.0) for `ruff-check` and `ruff-format`, plus standard whitespace and EOF hooks.
- [ ] **HOOK-02**: Static type-checking hook (`mirrors-mypy` v2.3.0) is configured in `.pre-commit-config.yaml` scoped to `^(notion_brain|tests)/` matching `pyproject.toml` and CI.
- [ ] **HOOK-03**: `pre-commit>=4.1.0` is declared in `pyproject.toml` under `[project.optional-dependencies] dev` to support `pip install -e ".[dev]"`.
- [ ] **HOOK-04**: Hook revisions and linter rules in `.pre-commit-config.yaml` mirror the GitHub Actions `quality-debt` CI job in `.github/workflows/ci.yml`.

### Platform Portability & Installation

- [ ] **PLAT-01**: `scripts/install.sh` inspects `uname -s` at the start of system detection before invoking Linux package managers.
- [ ] **PLAT-02**: When running on macOS (`Darwin`), `scripts/install.sh` prints formatted manual setup steps referencing README Quickstart Step 2 and exits with code 0.
- [ ] **PLAT-03**: Linux installation pathways in `scripts/install.sh` (`apt`, `dnf`, `yum`, `pacman`) remain functional and regression-free.

## v2 Requirements

Deferred to future releases. Tracked but not in current roadmap.

### Tooling Automation

- **TOOL-01**: Optional pre-push git hook running `pytest -q` test suite before remote push.
- **TOOL-02**: Scheduled GitHub Action workflow for automated `pre-commit autoupdate` verification.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Automated Homebrew package bootstrap in `install.sh` | Apple Silicon vs Intel paths and Xcode prompts are brittle; manual setup via README Step 2 is reliable and sufficient. |
| Live Notion API mocks in `test_config_schema.py` | `config_schema.py` is pure declarative metadata for Desktop UI; network mocks add latency and failure modes. |
| Automatic staging of hook fixes (`git add`) | Silent automatic commits hide formatting side effects from developers; working tree changes must be reviewed and staged manually. |
| Native Windows PowerShell installer in `install.sh` | Windows users are documented to use WSL2 or manual virtualenv `pip install`. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCHEMA-01 | Phase 1 | Pending |
| SCHEMA-02 | Phase 1 | Pending |
| SCHEMA-03 | Phase 1 | Pending |
| HOOK-01 | Phase 2 | Pending |
| HOOK-02 | Phase 2 | Pending |
| HOOK-03 | Phase 2 | Pending |
| HOOK-04 | Phase 2 | Pending |
| PLAT-01 | Phase 3 | Pending |
| PLAT-02 | Phase 3 | Pending |
| PLAT-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-09-20*
*Last updated: 2026-09-20 after roadmap creation*
