---
last_mapped_commit: 7e1e184f80b4352228eef67fc0fa0a4432cdabbd
last_mapped_at: 2026-09-20
---
# Testing Patterns

**Analysis Date:** 2026-09-20

## Test Framework

**Runner:**

- pytest 9.1.1 with pytest-cov 7.1.0
- Config: `pyproject.toml` (`[tool.pytest.ini_options]`)
  - `testpaths = ["tests"]`
  - `addopts = ["--strict-config", "--strict-markers"]`
  - `xfail_strict = true`

**Assertion Library:**

- Standard Python `assert` statements evaluated via pytest AST rewriting

**Run Commands:**

```bash
uv run pytest                                               # Run all tests
uv run pytest -q                                            # Run all tests quietly
uv run pytest tests/test_extract.py -v                       # Run single test file verbosely
uv run pytest -k "test_rich_text"                           # Run tests matching expression
uv run pytest --cov=notion_brain --cov-report=term-missing  # Run test suite with coverage report
```

## Test File Organization

**Location:**

- Separate `tests/` directory at repository root (not co-located with production code in `notion_brain/`).

**Naming:**

- Files named `test_<module_or_feature>.py`.
- Test classes named `Test<Subject>` in PascalCase.
- Test methods and functions named `test_<scenario_or_behavior>` in snake_case.

**Structure:**

```
tests/
├── conftest.py                             # Global stubs for Hermes runtime dependencies
├── test_auto_sync.py                       # Local disk memory sync tests
├── test_bootstrap_schema.py                # Schema generation and validation tests
├── test_coverage_gaps.py                   # Targeted unit tests closing branch gaps
├── test_custom_databases.py                # Dynamic domain/database registry tests
├── test_extract.py                         # Text classification, regex routing, prompt parsing
├── test_provider.py                        # NotionBrainProvider lifecycle and tool dispatch
├── test_store.py                           # Notion REST client helpers and property transforms
├── characterization/
│   ├── __init__.py
│   ├── test_cli_contract.py                # CLI commands (url, health, reset) offline contracts
│   └── test_provider_contract.py           # Provider protocol interface contracts
└── regressions/
    ├── __init__.py
    ├── test_durability_blockers.py         # Regression tests for cache & storage durability
    ├── test_migration_privacy_blockers.py  # Regression tests for secret leaks and privacy
    └── test_storage_recall_blockers.py     # Regression tests for page body recall
```

## Test Structure

**Suite Organization:**

```python
"""Tests for property helpers and Notion response parsing."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

from notion_brain.store import date_property, rich_text_property

class TestDateProperty:
    def test_with_date(self):
        prop = date_property("2026-07-22")
        assert prop["date"]["start"] == "2026-07-22"

    def test_none_returns_empty_date(self):
        # Notion rejects {"date": None}; documented absence shape is {"date": {}}
        assert date_property(None) == {"date": {}}

    def test_empty_string_still_empty(self):
        assert date_property("") == {"date": {}}
```

**Patterns:**

- **Setup pattern:** Autouse fixtures in `conftest.py` and test modules configure global isolation before tests run (e.g. `_forbid_network` blocking `store.requests.request`).
- **Teardown pattern:** Handled automatically by `pytest.MonkeyPatch` context teardown and `tmp_path` directory cleanup.
- **Assertion pattern:** Idiomatic pytest equality checks (`assert result == expected`), inclusion checks (`assert "keyword" in data["result"]`), or exception handling with `pytest.raises()`.

## Mocking

**Framework:**

- `pytest.MonkeyPatch` (`monkeypatch` fixture) and `unittest.mock` (`patch`, `MagicMock`).

**Patterns:**

```python

# tests/regressions/test_storage_recall_blockers.py:62-68

@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_network(*args: object, **kwargs: object) -> None:
        raise RuntimeError("storage/recall regressions must not make network calls")

    monkeypatch.setattr(store.requests, "request", unexpected_network)
```

```python

# tests/test_provider.py:105-112

def test_search_dispatches(self):
    provider = self._make_initialized_provider()
    with patch("notion_brain.store.search_entries") as mock_search:
        mock_search.return_value = []
        result = provider.handle_tool_call("notion_brain_search", {"query": "test"})
        data = json.loads(result)
        assert "result" in data
```

**What to Mock:**

- **External Network Calls:** Real HTTP requests to `https://api.notion.com` MUST be mocked in all automated tests. Autouse fixtures enforce this across regression and characterization suites.
- **Environment Variables and Tokens:** `os.environ["NOTION_API_KEY"]` and `HERMES_HOME` paths mocked using `monkeypatch.setenv()` or `monkeypatch.setattr(store, "get_api_key", ...)`.
- **Filesystem Paths:** Use pytest's built-in `tmp_path` fixture for disk cache files (`notion_brain.json`) and memory imports (`MEMORY.md`).
- **External Runtime Modules:** Hermes agent environment (`agent`, `tools.registry`) stubbed globally in `tests/conftest.py`.

**What NOT to Mock:**

- **Data Transformation & Serialization:** `store.date_property`, `store.rich_text_property`, `store._flatten_result`, `bootstrap.build_custom_database_props`.
- **Classification & Parsing:** `extract.classify_text`, `extract.classify_turn`, `helpers.parse_disk_memory_text`.
- **Sanitization & Redaction:** `schema.redact_secrets`, `schema.clean_title`, `schema.dedupe_strings`.
- **Dataclass Normalization:** `BrainEntry.normalized()`.

## Fixtures and Factories

**Test Data:**

```python

# Helper factories for Notion payload fixtures (tests/test_store.py:65-67, 96-104)

def _page(props: dict[str, Any]) -> dict[str, Any]:
    return {"properties": props}

def _result(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "object": "page",
        "id": "abc123",
        "created_time": "2026-01-01T00:00:00Z",
        "last_edited_time": "2026-01-02T00:00:00Z",
        "properties": props,
    }

# Provider test factory (tests/test_provider.py:87-103)

def _make_initialized_provider() -> NotionBrainProvider:
    provider = NotionBrainProvider()
    provider._db_ids = {k: f"db-{k}-id" for k in S.DATABASES}
    provider._parent_page_id = "page-123"
    provider._hermes_home = "/tmp/test-hermes"
    provider._session_id = "test-session"
    return provider
```

**Location:**

- Global runtime stubs: `tests/conftest.py`.
- Module-specific mock helpers and test factories: defined at the top of individual test modules (`tests/test_store.py`, `tests/test_provider.py`, `tests/regressions/test_storage_recall_blockers.py`).

## Coverage

**Requirements:**

- >80% coverage on all new functionality per `CONTRIBUTING.md:88`.
- Branch coverage enforced via `pyproject.toml` (`branch = true`, `source = ["notion_brain"]`).
- Current repository baseline: 72% total branch coverage with 296 passing tests.

**View Coverage:**

```bash
uv run pytest --cov=notion_brain --cov-report=term-missing
uv run pytest --cov=notion_brain --cov-report=xml
```

## Test Types

**Unit Tests:**

- Scope: In-memory logic, property encoding, title cleaning, secret redaction, text extraction, heuristics.
- Location: `tests/test_store.py`, `tests/test_extract.py`, `tests/test_bootstrap_schema.py`, `tests/test_coverage_gaps.py`.

**Integration Tests:**

- Scope: Provider tool dispatching, background disk synchronization, local cache reads/writes, custom database dynamic registrations.
- Location: `tests/test_provider.py`, `tests/test_auto_sync.py`, `tests/test_custom_databases.py`.

**E2E Tests:**

- Scope: Offline contract and CLI behavior tests simulating end-to-end user workflows without external network access.
- Framework: Pytest invoking `notion_brain.__main__.main()` or `subprocess.run([sys.executable, "-m", "notion_brain", ...])`.
- Location: `tests/characterization/test_cli_contract.py`.

## Common Patterns

**Async Testing:**

```python

# Background thread and queue verification (tests/test_auto_sync.py:53-80)

def test_auto_disk_sync_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mem_dir = tmp_path / "memories"
    mem_dir.mkdir()
    (mem_dir / "MEMORY.md").write_text("Audit done: All fixed.\n§\nPreference: Python.\n")

    stored_entries = []
    def mock_store(entry):
        stored_entries.append(entry)

    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {k: f"db-{k}" for k in S.DATABASES}
    monkeypatch.setattr(provider, "_store_entry", mock_store)

    provider._sync_disk_memories()
    assert len(stored_entries) == 2
```

**Error Testing:**

```python

# Exception verification and secret redaction checks (tests/test_store.py:235-240)

def test_request_exception_redacts_secret(monkeypatch: pytest.MonkeyPatch):
    import requests
    def mock_request(*args, **kwargs):
        resp = requests.Response()
        resp.status_code = 400
        resp._content = b'{"message": "Invalid token sk-ant-123456789012"}'
        return resp

    monkeypatch.setattr(requests, "request", mock_request)
    with pytest.raises(RuntimeError) as exc_info:
        store._request("GET", "/databases")
    assert "sk-ant-" not in str(exc_info.value)
    assert "[REDACTED_SECRET]" in str(exc_info.value)
```

---

*Testing analysis: 2026-09-20*
