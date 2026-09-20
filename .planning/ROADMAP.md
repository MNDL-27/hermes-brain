# Roadmap: hermes-brain

## Overview

hermes-brain provides structured Notion memory for the Hermes AI agent ecosystem. This milestone addresses contributor developer experience, quality gates, and platform portability across GitHub issues #51, #52, and #53. The work progresses in three sequential phases: establishing isolated unit test coverage for the declarative configuration schema (#51), enforcing local git pre-commit quality gates mirroring CI (#52), and implementing non-destructive Darwin platform detection in the installation script (#53).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Config Schema Test Infrastructure** - Validate configuration schema contract and host stubs in offline isolation
- [ ] **Phase 2: Pre-Commit Quality Gates & Tooling Parity** - Configure local pre-commit hooks mirroring CI checks
- [ ] **Phase 3: Platform Portability & Installation Guard** - Implement Darwin platform detection and graceful manual setup exit

## Phase Details

### Phase 1: Config Schema Test Infrastructure
**Goal**: Validate declarative configuration schema contract and host stubs in offline isolation without external dependencies
**Depends on**: Nothing (first phase)
**Requirements**: SCHEMA-01, SCHEMA-02, SCHEMA-03
**Success Criteria** (what must be TRUE):
  1. Running `pytest tests/test_config_schema.py` passes in an isolated environment without `ModuleNotFoundError` when host Hermes is absent
  2. Test suite verifies schema name, storage key, property fields, property kinds, defaults, secret flags, and tuple immutability of `CONFIG_SCHEMA`
  3. Running `pytest --cov=notion_brain.config_schema tests/test_config_schema.py` achieves 100% statement and branch coverage on `config_schema.py`
**Plans**: TBD

Plans:
- [ ] 01-01: TBD

### Phase 2: Pre-Commit Quality Gates & Tooling Parity
**Goal**: Enforce automated local code hygiene, formatting, linting, and static typing matching remote CI before git commits
**Depends on**: Phase 1
**Requirements**: HOOK-01, HOOK-02, HOOK-03, HOOK-04
**Success Criteria** (what must be TRUE):
  1. Installing dev dependencies via `pip install -e ".[dev]"` installs the `pre-commit` binary without extra manual dependencies
  2. Running `pre-commit run --all-files` succeeds across the repository, executing `ruff`, `ruff-format`, `mypy`, and standard file sanitizers cleanly
  3. Committing code with formatting defects, trailing whitespace, or Mypy type errors is automatically blocked locally before push
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Platform Portability & Installation Guard
**Goal**: Provide clean, informative macOS onboarding and safeguard Linux package manager installation paths
**Depends on**: Phase 2
**Requirements**: PLAT-01, PLAT-02, PLAT-03
**Success Criteria** (what must be TRUE):
  1. Executing `scripts/install.sh` on macOS (`Darwin`) outputs manual setup instructions referencing README Quickstart Step 2 and exits cleanly with status code 0
  2. Executing `scripts/install.sh` on supported Linux distributions (`apt`, `dnf`, `yum`, `pacman`) continues standard automated installation without regression
  3. Running `scripts/install.sh` on macOS does not trigger false-positive Linux package manager errors or missing Hermes agent errors
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Config Schema Test Infrastructure | 0/1 | Not started | - |
| 2. Pre-Commit Quality Gates & Tooling Parity | 0/1 | Not started | - |
| 3. Platform Portability & Installation Guard | 0/1 | Not started | - |
