---
last_mapped_commit: 7e1e184f80b4352228eef67fc0fa0a4432cdabbd
last_mapped_at: 2026-09-20
---
# External Integrations

**Analysis Date:** 2026-09-20

## APIs & External Services

**Cloud Knowledge & Document Storage:**

- Notion API (`https://api.notion.com/v1`) - Core persistence backend for structured long-term memories across 7 databases (`Memory`, `Tasks`, `Projects`, `Content`, `Research`, `Career`, `Entities`) and dynamically registered custom databases
  - SDK/Client: Direct HTTP via `requests` in `notion_brain/store.py` (API version `2022-06-28`)
  - Auth: `NOTION_API_KEY` (Notion internal integration token)

**Inference & Extraction Services:**

- OpenAI-compatible Chat Completions API (`/chat/completions`) - Optional LLM-assisted turn extraction to convert conversational text into structured memories
  - SDK/Client: Direct HTTP via `requests` in `notion_brain/extract.py:extract_with_llm`
  - Auth: `OPENAI_API_KEY` (defaults to `dummy-key` for local instances like Ollama)
  - Default Endpoint: `http://localhost:11434/v1` (configurable via `OPENAI_BASE_URL` or `OPENAI_API_BASE`)

**Repository & Distribution Services:**

- GitHub API / Git Repository (`https://github.com/MNDL-27/hermes-brain.git`) - Self-updating mechanism invoked via `hermes-brain update`
  - SDK/Client: Subprocess `git pull` / `pip install` in `notion_brain/__main__.py:_cmd_update`
  - Auth: Standard Git transport credentials / public HTTPS access

## Data Storage

**Databases:**

- Notion Workspace (Cloud Relational Document Store)
  - Connection: `NOTION_API_KEY` Bearer token against `https://api.notion.com/v1`
  - Client: Synchronous REST client wrapped in `notion_brain/store.py`
  - Structure: Parent page ("Hermes Brain" or ID in `HERMES_NOTION_PARENT_PAGE`) hosting 7 structured database objects with typed properties

**File Storage:**

- Local filesystem only:
  - Cache: `$HERMES_HOME/notion_brain.json` (stores parent page ID, database IDs mapping, and `schema_version`)
  - Config / Secrets: `$HERMES_HOME/.env` (stores `NOTION_API_KEY`, file permission `0600`)
  - Disk memory files: `MEMORY.md`, `USER.md`, `CLAUDE.md` parsed and synchronized into Notion via `notion_brain/helpers.py:parse_disk_memory_text` and `notion_brain/__main__.py:main`

**Caching:**

- Disk JSON Cache: Stored in `$HERMES_HOME/notion_brain.json` (`SCHEMA_VERSION = 2`), loaded by `notion_brain/bootstrap.py` to prevent redundant Notion search calls
- In-Memory Prefetch Cache: Thread-safe memory buffer on `NotionBrainProvider._prefetch_cache` guarded by `_prefetch_lock` in `notion_brain/provider.py`

## Authentication & Identity

**Auth Provider:**

- Notion Integration Token:
  - Implementation: Internal integration bearer token created in Notion Developer Portal (`notion.so/my-integrations`). Passed via HTTP header `Authorization: Bearer <NOTION_API_KEY>` in `notion_brain/store.py:_headers()`.
  - Resolution order: `NOTION_API_KEY` environment variable first; if unset, loaded from `$HERMES_HOME/.env`.

**LLM Endpoint Auth:**

- Bearer token via `OPENAI_API_KEY` environment variable passed to `extract_with_llm()` in `notion_brain/extract.py`.

## Monitoring & Observability

**Error Tracking:**

- None external. All exceptions during Notion API communication pass through `notion_brain.schema.redact_secrets()` to strip API keys, tokens, and private keys before logging or bubbling up (`raise ... from None` in `notion_brain/store.py`).

**Logs:**

- Standard Python library `logging.getLogger(__name__)`. Logs operational diagnostics, retry warnings, and cache bootstrap states to stdout / stderr or Hermes agent log streams.

## CI/CD & Deployment

**Hosting:**

- Self-hosted client plugin. Runs locally or on a virtual private server inside the user's Hermes Agent process environment.

**CI Pipeline:**

- GitHub Actions (`.github/workflows/ci.yml` and `.github/workflows/orcarouter-code-review.yml`):
  - Matrix test runner across Python `3.11`, `3.12`, and `3.13` on `ubuntu-latest` using `astral-sh/setup-uv@v6`
  - Test coverage tracking with `pytest-cov` and upload to Codecov (`codecov/codecov-action@v5`)
  - Static analysis, linting, and formatting checks via `ruff check` and `mypy`
  - Build validation using `python -m build` and `twine check`
  - Automated PR code review via `Continuum-AI-Corp/orca-code-review@v1` using `ORCAROUTER_API_KEY` secret

## Environment Configuration

**Required env vars:**

- `NOTION_API_KEY`: Notion internal integration secret token (`ntn_...`)

**Optional env vars:**

- `HERMES_HOME`: Directory path for configuration and local cache files (defaults to `~/.hermes`)
- `HERMES_NOTION_PARENT_PAGE`: Notion page UUID to use as the root parent page for Hermes Brain
- `OPENAI_BASE_URL` / `OPENAI_API_BASE`: Base HTTP URL for local or remote OpenAI-compatible extraction model (default: `http://localhost:11434/v1`)
- `OPENAI_API_KEY`: API key for the OpenAI-compatible extraction endpoint (default: `dummy-key`)
- `HERMES_MODEL` / `OPENAI_MODEL`: Model name for extraction (default: `qwen3-coder-30b:latest`)
- `NOTION_BRAIN_LLM_TIMEOUT`: Timeout in seconds for LLM extraction requests (default: `5.0`)

**Secrets location:**

- Stored on local disk at `$HERMES_HOME/.env` with `0600` file permissions
- Sourced into runtime process via `notion_brain/store.py:_load_env_file()`
- In-memory secret scrubbing applied to outgoing network content, log statements, and exception messages via `notion_brain/schema.py:redact_secrets()`

## Webhooks & Callbacks

**Incoming:**

- None. The plugin operates purely on a synchronous request or background daemon thread model initiated by agent turns.

**Outgoing:**

- None. Communications are direct synchronous/asynchronous HTTP REST client calls to Notion API and local/remote LLM endpoints.

---

*Integration audit: 2026-09-20*
