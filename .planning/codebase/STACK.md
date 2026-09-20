---
last_mapped_commit: 7e1e184f80b4352228eef67fc0fa0a4432cdabbd
last_mapped_at: 2026-09-20
---
# Technology Stack

**Analysis Date:** 2026-09-20

## Languages

**Primary:**

- Python `>=3.11,<3.14` (supported: 3.11, 3.12, 3.13) - Core provider package (`notion_brain/`), tests (`tests/`), examples (`examples/`)

**Secondary:**

- Bash 4+ - Installation and environment setup scripts (`scripts/install.sh`)
- YAML 1.2 - GitHub Actions workflows (`.github/workflows/ci.yml`, `.github/workflows/orcarouter-code-review.yml`) and plugin metadata (`plugin.yaml`)
- JSON - Workspace database cache (`notion_brain.json`) and configuration exchange (`notion_brain/config_schema.py`)

## Runtime

**Environment:**

- Python 3.11, 3.12, 3.13 (CPython on POSIX / Linux / WSL2)

**Package Manager:**

- `uv` (Astral uv, lockfile revision 3)
- `pip` / `setuptools` (PEP 517/621 build backend via `pyproject.toml`)
- Lockfile: present (`uv.lock`)

## Frameworks

**Core:**

- Hermes Agent Framework (unpinned runtime interface) - Extensible agent architecture providing memory manager hook points (`agent.memory_provider.MemoryProvider`, `project.entry-points."hermes_agent.memory_providers"`)

**Testing:**

- pytest 9.1.1 - Test execution runner configured in `pyproject.toml`
- pytest-cov 7.1.0 - Code coverage measurement and reporting (`pyproject.toml`, `.github/workflows/ci.yml`)

**Build/Dev:**

- setuptools `>=68.0` - Build backend specified in `pyproject.toml`
- build 1.5.0 - PEP 517 source and wheel package builder
- twine 6.2.0 - PyPI / package distribution metadata validator
- ruff 0.16.0 - Code linter and import formatter (`pyproject.toml`)
- mypy 2.3.0 - Static type checker (`pyproject.toml`, `mypy.ini`)

## Key Dependencies

**Critical:**

- `requests` `>=2.28` (locked `2.34.2`) - Synchronous HTTP client for Notion REST API calls in `notion_brain/store.py` and local LLM completions in `notion_brain/extract.py`

**Infrastructure:**

- `urllib3` 2.7.0 - HTTP connection pooling and transport layer for requests
- `certifi` 2026.7.22 - Mozilla CA root certificate bundle for TLS verification
- `charset-normalizer` 3.4.9 - Character encoding verification for HTTP payloads
- `idna` 3.18 - Internationalized domain names in applications support
- `cryptography` `>=50.0.0` (locked `50.0.0`, optional dev dependency) - Cryptographic primitive support

## Configuration

**Environment:**

- Configured via shell environment variables and local dotenv file at `$HERMES_HOME/.env` (default: `~/.hermes/.env`)
- Key configs required:
  - `NOTION_API_KEY`: Notion internal integration token (`ntn_...`) required for Notion workspace operations
  - `HERMES_HOME`: Base configuration and cache path (defaults to `~/.hermes`)
  - `HERMES_NOTION_PARENT_PAGE`: Optional Notion parent page UUID override
  - `OPENAI_BASE_URL` / `OPENAI_API_BASE`: Base URL for LLM turn extraction (defaults to `http://localhost:11434/v1`)
  - `OPENAI_API_KEY`: Optional auth token for OpenAI-compatible extraction endpoint (defaults to `dummy-key`)
  - `HERMES_MODEL` / `OPENAI_MODEL`: Model identifier for turn extraction (defaults to `qwen3-coder-30b:latest`)
  - `NOTION_BRAIN_LLM_TIMEOUT`: Timeout in seconds for LLM extraction requests (defaults to `5.0`)

**Build:**

- `pyproject.toml` - Project packaging configuration, dependencies, metadata, ruff, mypy, pytest, and coverage settings
- `mypy.ini` - Type-check suppression for dynamically imported or unstubbed modules (`requests.*`, `agent.*`, `tools.*`, `plugins.*`)
- `plugin.yaml` - Plugin specification declared for the Hermes agent system
- `MANIFEST.in` - Source distribution packaging rules
- `uv.lock` - Deterministic multi-platform dependency lockfile

## Platform Requirements

**Development:**

- Linux / POSIX system (Ubuntu, Debian, Fedora, RHEL, or WSL2)
- Python 3.11, 3.12, or 3.13
- Astral `uv` or `pip` / `venv`

**Production:**

- POSIX Linux environment hosting Hermes Agent
- Integration directory path at `~/.hermes/plugins/notion_brain` or Python environment at `~/.hermes/hermes-agent/venv/`
- Outbound HTTPS network access to `api.notion.com:443` and optional local HTTP access to `localhost:11434` (Ollama)

---

*Stack analysis: 2026-09-20*
