---
last_mapped_commit: 7e1e184f80b4352228eef67fc0fa0a4432cdabbd
last_mapped_at: 2026-09-20
---
# Codebase Structure

**Analysis Date:** 2026-09-20

## Directory Layout

```
hermes-brain/
├── .planning/                  # Project roadmap, GSD state, and codebase analysis
│   └── codebase/               # Architecture, stack, convention, and structure docs
├── assets/                     # Architecture diagrams and documentation assets
├── dev/                        # Developer configs and local notes
│   └── claude/                 # Claude-specific workspace settings
├── docs/                       # Project documentation
│   ├── README.md               # Documentation guide
│   ├── architecture.md         # Architecture overview and design trade-offs
│   └── troubleshooting.md      # Troubleshooting and diagnostic steps
├── examples/                   # Standalone scripts and usage samples
│   ├── README.md               # Examples guide
│   ├── quickstart.py           # Basic provider and tool usage sample
│   └── migrate_memory.py       # Memory import script
├── notion_brain/               # Primary Python package implementation
│   ├── __init__.py             # Public module exports and convenience functions
│   ├── __main__.py             # CLI application entry point (`hermes-brain`)
│   ├── bootstrap.py            # Workspace provisioning, schema repair, and wizard
│   ├── config_schema.py        # Desktop panel UI configuration schema
│   ├── extract.py              # Turn classifier, regex heuristics, and LLM extractor
│   ├── helpers.py              # Disk memory parsing and select option guards
│   ├── provider.py             # Hermes memory provider and tool dispatcher
│   ├── schema.py               # Data models, secret redaction, and domain registry
│   ├── schemas.py              # Agent tool JSON schemas
│   └── store.py                # Synchronous Notion REST client with retry logic
├── scripts/                    # Installer and deployment scripts
│   └── install.sh              # User and CI automated installation script
├── skills/                     # Hermes agent skill package
│   └── notion-brain/           # Agent skill definitions
│       └── SKILL.md            # Skill metadata, trigger phrases, and tool guide
├── tests/                      # Automated test suite
│   ├── characterization/       # Contract and interface stability tests
│   │   ├── test_cli_contract.py        # CLI command interface tests
│   │   └── test_provider_contract.py   # Hermes memory provider contract tests
│   ├── regressions/            # Bug fix regression tests
│   │   ├── test_durability_blockers.py         # Persistence and worker tests
│   │   ├── test_migration_privacy_blockers.py  # Secret redaction and migration tests
│   │   └── test_storage_recall_blockers.py     # Search and recall accuracy tests
│   ├── conftest.py             # Pytest fixtures and mock configurations
│   ├── test_auto_sync.py       # Local disk memory auto-sync tests
│   ├── test_bootstrap_schema.py# Workspace bootstrap and repair tests
│   ├── test_coverage_gaps.py   # Boundary condition and edge case tests
│   ├── test_custom_databases.py# Custom dynamic database registry tests
│   ├── test_extract.py         # Turn extraction and classification tests
│   ├── test_provider.py        # Provider lifecycle and tool execution tests
│   └── test_store.py           # Notion REST client tests
├── AGENTS.md                   # Agent operating guidelines and policies
├── CHANGELOG.md                # Version history and release notes
├── CODEBASE-AUDIT-REPORT.md    # Production-readiness audit report
├── CODE_OF_CONDUCT.md          # Contributor code of conduct
├── CONTRIBUTING.md             # Developer contribution guidelines
├── LICENSE                     # MIT license
├── MANIFEST.in                 # Source distribution file inclusion rules
├── mypy.ini                    # Static type-checking configuration
├── plugin.yaml                 # Hermes plugin manifest
├── pyproject.toml              # Build config, dependencies, and tool settings
├── README.md                   # Project overview and quickstart guide
├── REMEDIATION-STATUS.md       # Audit finding remediation tracking
├── SECURITY.md                 # Security reporting and vulnerability disclosure
└── uv.lock                     # UV dependency lockfile
```

## Directory Purposes

**`notion_brain/`:**

- Purpose: Contains the entire runtime library for the Hermes Notion memory provider.
- Contains: Python modules for API interaction, classification, normalization, bootstrapping, and CLI.
- Key files: `provider.py`, `store.py`, `schema.py`, `extract.py`, `bootstrap.py`, `__main__.py`.

**`skills/`:**

- Purpose: Houses agent skill manifests integrated into Hermes AI workflows.
- Contains: YAML frontmatter and markdown documentation instructing the agent on when and how to call memory tools.
- Key files: `skills/notion-brain/SKILL.md`.

**`tests/`:**

- Purpose: Comprehensive automated test suite ensuring durability, privacy, and contract adherence.
- Contains: Unit tests, regression tests for audited vulnerabilities, and contract tests.
- Key files: `tests/conftest.py`, `tests/test_provider.py`, `tests/characterization/test_provider_contract.py`.

**`docs/`:**

- Purpose: Technical reference documentation for users and contributors.
- Contains: High-level architectural overviews, design trade-offs, and operational troubleshooting manuals.
- Key files: `docs/architecture.md`, `docs/troubleshooting.md`.

**`examples/`:**

- Purpose: Runnable sample code demonstrating library usage and data migration.
- Contains: Standalone Python scripts.
- Key files: `examples/quickstart.py`, `examples/migrate_memory.py`.

**`scripts/`:**

- Purpose: Shell scripts for environment setup and installation.
- Contains: POSIX bash scripts.
- Key files: `scripts/install.sh`.

**`.planning/`:**

- Purpose: GSD workflow planning, project roadmap, and codebase analysis artifacts.
- Contains: Markdown specifications, plans, and codebase snapshots.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`.

## Key File Locations

**Entry Points:**

- `notion_brain/__main__.py`: CLI executable entry point (`python -m notion_brain` / `hermes-brain`).
- `notion_brain/__init__.py`: Package root exporting `ensure_brain()`, `remember()`, `search_entries()`, and provider registration.
- `notion_brain/provider.py`: Hermes memory provider entry point (`register()`).
- `scripts/install.sh`: Shell installer script for installing dependencies and initializing workspace.

**Configuration:**

- `pyproject.toml`: Python package specification, dependencies, entry points, and test/lint configurations.
- `plugin.yaml`: Hermes plugin definition manifest.
- `mypy.ini`: Mypy configuration file.
- `notion_brain/config_schema.py`: UI form specification for desktop panels.

**Core Logic:**

- `notion_brain/provider.py`: `NotionBrainProvider` implementation, worker loop, tool dispatch.
- `notion_brain/store.py`: Notion REST API client, query pagination, retry logic, property serializing.
- `notion_brain/extract.py`: LLM-based and heuristic regex-based memory classification from conversation turns.
- `notion_brain/schema.py`: `BrainEntry` dataclass, secret redactor regexes, domain-to-database mappings.
- `notion_brain/bootstrap.py`: Idempotent Notion workspace bootstrapping, schema verification, and database repair.
- `notion_brain/helpers.py`: Disk memory file parsing (`MEMORY.md`, `USER.md`, `CLAUDE.md`) and property validation.
- `notion_brain/schemas.py`: Tool call JSON schema specifications.

**Testing:**

- `tests/conftest.py`: Global fixtures, environment setup, and mocks.
- `tests/test_provider.py`: Provider lifecycle and tool handler unit tests.
- `tests/test_store.py`: REST client HTTP interaction and retry unit tests.
- `tests/test_extract.py`: Extraction rules and heuristic classifier tests.
- `tests/characterization/test_provider_contract.py`: Golden master provider API tests.
- `tests/regressions/test_durability_blockers.py`: Regression verification for write durability.

## Naming Conventions

**Files:**

- Python modules: lowercase `snake_case.py` (e.g. `config_schema.py`, `bootstrap.py`).
- Test files: prefixed with `test_` (e.g. `test_provider.py`, `test_store.py`).
- Documentation: uppercase or lowercase markdown (e.g. `README.md`, `architecture.md`, `CHANGELOG.md`).
- Scripts: lowercase `snake_case.sh` (e.g. `install.sh`).

**Directories:**

- Python packages: lowercase `snake_case` (e.g. `notion_brain/`).
- Standard directories: lowercase `kebab-case` or `snake_case` (e.g. `skills/notion-brain/`, `examples/`).

**Code Entities:**

- Classes: `PascalCase` (e.g. `BrainEntry`, `NotionBrainProvider`).
- Functions and methods: `snake_case()` (e.g. `classify_turn()`, `redact_secrets()`, `handle_tool_call()`).
- Private helpers: leading underscore `_snake_case()` (e.g. `_worker_loop()`, `_safe_select_value()`).
- Constants & Global Patterns: uppercase `UPPER_SNAKE_CASE` or `_UPPER_SNAKE_CASE` (e.g. `DOMAINS`, `_SECRET_PATTERNS`, `DEFAULT_PARENT_PAGE`).

## Where to Add New Code

**New Agent Tool:**

- Schema: Declare tool JSON schema in `notion_brain/schemas.py`. Add schema to `ALL_TOOL_SCHEMAS`.
- Execution Logic: Add private tool handler method `_tool_<name>(self, args)` in `notion_brain/provider.py`.
- Routing: Add tool name mapping in `NotionBrainProvider.handle_tool_call()` (`notion_brain/provider.py:365`).
- Skill Guidance: Add trigger phrases and parameter documentation to `skills/notion-brain/SKILL.md`.
- Tests: Add corresponding unit tests in `tests/test_provider.py`.

**New Database Domain:**

- Schema Definition: Add domain key and database mapping to `DOMAINS`, `DATABASES`, and `DOMAIN_DATABASE` in `notion_brain/schema.py`.
- Notion Schema: Add required property schema to `_PROPS` in `notion_brain/bootstrap.py`.
- Heuristic Triggers: Add regex pattern and routing condition in `notion_brain/extract.py`.
- Disk Parsing Support: Add heading mapping to `_HEADING_DOMAINS` in `notion_brain/helpers.py`.
- Tests: Add test cases to `tests/test_extract.py` and `tests/test_bootstrap_schema.py`.

**New CLI Subcommand:**

- Parser: Define subparser in `main()` in `notion_brain/__main__.py`.
- Handler: Implement command function in `notion_brain/__main__.py` or expose through `notion_brain/bootstrap.py`.
- Tests: Add contract assertion in `tests/characterization/test_cli_contract.py`.

**New Utility or Data Transformation:**

- Formatting / Parsing: Add parsing helper to `notion_brain/helpers.py`.
- Data Normalization & Sanitization: Add to `notion_brain/schema.py`.
- API Call Helper: Add method to `notion_brain/store.py`.

## Special Directories

**`.planning/`:**

- Purpose: Project roadmap, milestone specifications, and codebase documentation.
- Generated: No.
- Committed: Yes.

**`dev/`:**

- Purpose: Developer configs, scratchpads, and local Claude settings.
- Generated: No.
- Committed: Yes.

**`hermes_brain.egg-info/`:**

- Purpose: Packaging metadata generated by setuptools during installation or build.
- Generated: Yes.
- Committed: Yes.

**`.venv/`:**

- Purpose: Python local virtual environment for development.
- Generated: Yes.
- Committed: No.

**`.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`:**

- Purpose: Build and test tool analysis caches.
- Generated: Yes.
- Committed: No.

---

*Structure analysis: 2026-09-20*
