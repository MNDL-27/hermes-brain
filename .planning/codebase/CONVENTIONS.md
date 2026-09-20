---
last_mapped_commit: 7e1e184f80b4352228eef67fc0fa0a4432cdabbd
last_mapped_at: 2026-09-20
---
# Coding Conventions

**Analysis Date:** 2026-09-20

## Naming Patterns

**Files:**

- Lowercase snake_case for all Python modules: `notion_brain/bootstrap.py`, `notion_brain/store.py`, `notion_brain/helpers.py`.
- Package entry points follow Python conventions: `notion_brain/__init__.py` and `notion_brain/__main__.py`.
- Configuration and schema definitions: `notion_brain/schema.py`, `notion_brain/schemas.py`, `notion_brain/config_schema.py`.
- Test files prefix with `test_` in snake_case: `tests/test_store.py`, `tests/test_provider.py`, `tests/characterization/test_cli_contract.py`.

**Functions:**

- Public functions and methods use snake_case: `clean_title()`, `normalize_domain()`, `get_api_key()`, `ensure_brain()`, `search_entries()`.
- Private and module-internal functions use leading underscore `_snake_case`: `_load_env_file()`, `_headers()`, `_request()`, `_flatten_result()`, `_page_title()`, `_safe_select_value()`, `_coerce_str_list()`.
- Factory/builder functions start with verbs: `build_custom_database_props()` in `notion_brain/bootstrap.py:42`, `create_database_page()` in `notion_brain/store.py:202`.

**Variables:**

- Local variables and arguments use snake_case: `session_id`, `domain_key`, `custom_fields`, `json_body`, `target_db`.
- Module-level constants use SCREAMING_SNAKE_CASE: `BASE_URL`, `_MAX_RETRIES`, `_RETRY_DELAY_S` in `notion_brain/store.py:23-25`; `DOMAINS`, `DATABASES`, `NOTION_API_VERSION`, `STATUSES`, `CONFIDENCES` in `notion_brain/schema.py:11-31`.
- Compiled regular expressions use leading underscore screaming snake_case or descriptive prefixes: `_SECRET_PATTERNS`, `_GIT_OR_CODE`, `_CONVERSATIONAL_FILLER`, `_TRIGGERS_TASK` in `notion_brain/extract.py:26-73`.

**Types:**

- Classes and dataclasses use PascalCase: `NotionBrainProvider` in `notion_brain/provider.py:65`, `BrainEntry` in `notion_brain/schema.py:112`.
- Modern Python type hints: `from __future__ import annotations` is required at top of every module.
- Use built-in generic collections and pipe unions: `str | None`, `list[dict[str, Any]]`, `dict[str, str]` instead of importing `Optional`, `Union`, `List`, `Dict` from `typing`.

## Code Style

**Formatting:**

- Tool: Ruff (`ruff` version 0.16.0) managed via `pyproject.toml`.
- Key settings in `pyproject.toml` (`[tool.ruff]`):
  - `target-version = "py311"`
  - `line-length = 100`
- Format command: `ruff format .`

**Linting:**

- Tool: Ruff (`ruff check`) and Mypy (`mypy` version 2.3.0).
- Key rules in `pyproject.toml` (`[tool.ruff.lint]`):
  - `select = ["E", "F", "W", "I"]` (Pyflakes, pycodestyle errors/warnings, isort import sorting)
  - `ignore = ["E501"]` (line length checks ignored by linter; handled by formatter)
- Mypy configuration in `pyproject.toml` (`[tool.mypy]`):
  - `python_version = "3.11"`
  - `files = ["notion_brain", "tests"]`
  - `check_untyped_defs = true`
  - `no_implicit_optional = true`
  - `warn_unused_configs = true`
  - Third-party stub ignores in `mypy.ini`: `requests.*`, `agent.*`, `tools.*`, `plugins.*`.

## Import Organization

**Order:**

1. Future annotations: `from __future__ import annotations` (line 1 after module docstring).
2. Standard library modules: `import json`, `import logging`, `import os`, `import re`, `from pathlib import Path`, `from typing import Any`.
3. Third-party dependencies: `import pytest`, `import requests`.
4. First-party internal imports:
   - Within `notion_brain`: relative imports preferred: `from . import bootstrap, extract, helpers, store`, `from .schema import BrainEntry, redact_secrets`.
   - Within `tests`: absolute package imports: `from notion_brain import NotionBrainProvider, store`, `from notion_brain import schema as S`.

**Path Aliases:**

- No path aliases or custom runtime sys.path hooks in production code.
- In test suites, tests include `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` or execute via `uv run pytest`.

## Error Handling

**Patterns:**

- **Strict Secret Redaction in Exceptions:** All error strings, API messages, and user payloads are sanitized before being raised or returned. Never emit raw tokens in errors.
  ```python
  # notion_brain/store.py:96
  raise RuntimeError(f"Notion API {resp.status_code} on {method} {path}: {redact_secrets(str(msg))}") from None
  ```
- **Idempotency and Self-Healing:** The system catches API discrepancies (e.g. archived databases, invalid select options) and falls back safely rather than crashing:
  ```python
  # notion_brain/helpers.py:18-24
  options = prop_schema.get("select", {}).get("options", [])
  valid = {opt.get("name", "") for opt in options}
  if not valid:
      return value
  return value if value in valid else None
  ```
- **Retry with Exponential Backoff:** Network calls retry transient errors (429, 500, 502, 503, 504, Timeout) honoring Notion's `Retry-After` header:
  ```python
  # notion_brain/store.py:77-89
  if resp.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES:
      sleep_for = _RETRY_DELAY_S * attempt
      if resp.status_code == 429:
          # parse Retry-After header safely
      time.sleep(sleep_for)
      continue
  ```
- **Tool Protocol Error Reporting:** Tool entry points catch validation errors and return structured diagnostic strings rather than uncaught exceptions:
  ```python
  # notion_brain/provider.py
  if not query:
      return tool_error("Missing required parameter: query")
  ```

## Logging

**Framework:** Standard library `logging` module (`import logging`).

**Patterns:**

- Initialized per module: `logger = logging.getLogger(__name__)`.
- `logger.warning(...)` for degraded runtime modes (e.g. missing `HERMES_HOME` or unconfigured optional features).
- `logger.error(..., exc_info=True)` for background worker errors during asynchronous sync threads (`notion_brain/provider.py`).
- Never log raw API tokens, authorization headers, or unsanitized credentials. Apply `redact_secrets()` before logging user input or error messages.

## Comments

**When to Comment:**

- Explain *why*, particularly around Notion API edge cases, undocumented behaviors, or security constraints:
  - Documenting Notion API quirks: e.g. Notion rejecting `{"date": None}` and requiring `{"date": {}}` (`tests/test_store.py:30`).
  - Documenting rate limiting or retry constraints: e.g. honoring `Retry-After` header to avoid burning retries (`notion_brain/store.py:78`).
  - Documenting single sources of truth: e.g. ensuring `_STATUS_OPTIONS` remains a subset of `S.STATUSES` (`notion_brain/bootstrap.py:22-24`).

**JSDoc/TSDoc:**

- Not applicable (Python codebase). Python docstrings follow Google/Sphinx style:
  - Module docstring at the top of every `.py` file summarizing purpose, authentication, and caching.
  - Multi-line docstrings using triple double-quotes `"""` with description, arguments, and return values.
  - Public classes and methods require docstrings; private helpers document intent when non-trivial.

## Function Design

**Size:**

- Small to moderate functions focused on a single task (10–40 lines).
- Data transform and parsing helpers are isolated into pure functions in `notion_brain/helpers.py` and `notion_brain/schema.py`.

**Parameters:**

- Type hints on all parameters.
- Default arguments used for optional parameters: `def clean_title(title: str = "Untitled") -> str:`.
- Keyword-only arguments enforced with `*` for configuration or flag options: `def search_entries(query: str, *, database: str = "all", max_results: int = 8, ...)`.
- Coercion helpers handle inconsistent LLM arguments: `_coerce_str_list(value: Any) -> list[str]`.

**Return Values:**

- Explicit return type annotations on every function (`-> None`, `-> str | None`, `-> list[dict[str, Any]]`).
- Functions avoid returning untyped tuples; structured data uses `dict` or `@dataclass BrainEntry`.

## Module Design

**Exports:**

- `notion_brain/__init__.py` serves as the explicit public contract.
- Declares `__all__` listing public entry points: `NotionBrainProvider`, `register`, `ensure_brain`, `remember`, `search_entries`, `classify_text`, and tool schema constants.
- `__version__ = "1.0.3"` defined in `notion_brain/__init__.py`.

**Barrel Files:**

- `notion_brain/__init__.py` acts as the package barrel, exposing top-level functions and re-exporting tools from `provider.py`, `extract.py`, `schema.py`, and `schemas.py`.
- Internal implementation details stay in dedicated modules (`store.py` for network, `bootstrap.py` for workspace provisioning, `helpers.py` for text parsing).
- External runtime dependencies (`agent`, `tools`) are imported lazily inside methods to permit importing `notion_brain` in offline/test environments without the parent Hermes agent installed.

---

*Convention analysis: 2026-09-20*
