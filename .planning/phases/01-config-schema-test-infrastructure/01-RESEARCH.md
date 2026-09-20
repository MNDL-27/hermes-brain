# Phase 01: Config Schema Test Infrastructure - Research

**Researched:** 2026-09-20
**Domain:** Python unit testing, declarative configuration schemas, test harness stubs, coverage validation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Define real, typed classes (`ProviderConfigSchema`, `ProviderField`) in `tests/conftest.py` attached to `plugins.memory.config_schema` rather than dynamic anonymous objects.
- **D-02:** Mirror Hermes host constants in `plugins.memory.config_schema` stub: `KIND_SECRET = "secret"`, `KIND_TEXT = "text"`, and `STORAGE_FLAT_JSON = "flat_json"`.
- **D-03:** Register stubs globally in `tests/conftest.py` alongside existing `agent.*` and `tools.*` stubs before test discovery.
- **D-04:** Perform exhaustive property assertions across `CONFIG_SCHEMA` and both fields (`notionApiKey` and `hermesHome`), verifying `key`, `label`, `kind`, `description`, `env_key`, `env_fallbacks`, `placeholder`, `inline`, `group`, and `default`.
- **D-05:** Organize assertions into focused, granular test functions (`test_schema_metadata`, `test_notion_api_key_field`, `test_hermes_home_field`, `test_schema_immutability`) to deliver precise test failure reporting.
- **D-06:** Enforce container immutability assertions: verify `isinstance(CONFIG_SCHEMA.fields, tuple)` and `isinstance(hermesHome.env_fallbacks, tuple)` to ensure callers cannot mutate field definitions in place.
- **D-07:** Enforce secret field safety rule: assert that `notionApiKey` (`kind=KIND_SECRET`) has `default is None` (or unset default), guarding against accidental credential defaults.
- **D-08:** Add negative import test using `unittest.mock.patch.dict(sys.modules)` to remove `plugins` and verify that importing `notion_brain.config_schema` cleanly raises `ModuleNotFoundError` when stubs are absent.
- **D-09:** Verify that `pytest --cov=notion_brain.config_schema --cov-fail-under=100 --cov-branch` achieves 100% statement and branch coverage on `notion_brain/config_schema.py`.
- **D-10:** Keep `pyproject.toml` global coverage configuration untouched; target `notion_brain.config_schema` explicitly via CLI invocation during verification.
- **D-11:** Apply full explicit typing in `tests/test_config_schema.py` (`def test_...() -> None:`) and typed attributes on stub classes in `tests/conftest.py` to ensure clean passage under `mypy.ini` without warnings.

### Claude's Discretion
- Internal test helper structure and fixture naming choices.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHEMA-01 | Unit test suite in `tests/test_config_schema.py` verifies `notion_brain/config_schema.py` schema name, storage key, and declared property fields. | Exhaustive property checks on `CONFIG_SCHEMA` (`name="notion_brain"`, `label="Hermes Brain (Notion)"`, `storage="flat_json"`) and fields tuple (`notionApiKey`, `hermesHome`) [VERIFIED: notion_brain/config_schema.py:11-38]. |
| SCHEMA-02 | Tests verify property kinds, defaults, secret status (`notionApiKey` has no default), and tuple immutability. | Explicit assertions on `KIND_SECRET`, `KIND_TEXT`, `default is None` for `notionApiKey`, default `"~/.hermes"` for `hermesHome`, and `isinstance(..., tuple)` checks [VERIFIED: notion_brain/config_schema.py:16-36]. |
| SCHEMA-03 | Lightweight runtime stubs for `plugins.memory.config_schema` in `tests/conftest.py` ensure `pytest` runs offline without `ModuleNotFoundError` when host Hermes is absent. | Stubs registering `plugins`, `plugins.memory`, `plugins.memory.config_schema` with typed `@dataclass` classes and constants in `tests/conftest.py` before pytest imports test files [VERIFIED: tests/conftest.py:6-15]. |
</phase_requirements>

## Summary

Phase 1 provides test infrastructure for `notion_brain/config_schema.py` without requiring the external Hermes host runtime. `notion_brain/config_schema.py` defines configuration metadata rendered by the Hermes desktop UI panel. It imports host stubs (`ProviderConfigSchema`, `ProviderField`, `KIND_SECRET`, `KIND_TEXT`, `STORAGE_FLAT_JSON`) from `plugins.memory.config_schema`. In standalone development environments without the Hermes host package installed, direct import of `notion_brain.config_schema` fails with `ModuleNotFoundError: No module named 'plugins'`.

`tests/conftest.py` already stubs `agent`, `agent.memory_manager`, `agent.memory_provider`, `tools`, and `tools.registry` into `sys.modules`. Phase 1 extends `tests/conftest.py` to stub `plugins`, `plugins.memory`, and `plugins.memory.config_schema` using typed `@dataclass(frozen=True)` classes. This satisfies D-01, D-02, and D-03, unblocking offline test execution.

The new test suite `tests/test_config_schema.py` executes granular property validations across `CONFIG_SCHEMA`, verifying name, label, storage type, field keys, labels, kinds, descriptions, environment variable bindings, fallback tuples, placeholders, inline flags, groups, defaults, tuple immutability, secret safety, and negative import behavior under missing stubs. `pytest --cov=notion_brain.config_schema --cov-fail-under=100 --cov-branch` verifies 100% statement and branch coverage.

**Primary recommendation:** Register typed `@dataclass(frozen=True)` stubs in `tests/conftest.py` for `plugins.memory.config_schema`, write granular typed test functions in `tests/test_config_schema.py`, and isolate negative import verification using `unittest.mock.patch.dict(sys.modules)`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Host Runtime Stubbing | Test Harness (`tests/conftest.py`) | — | Populates `sys.modules` at pytest initialization to decouple tests from external Hermes agent package. |
| Declarative Schema Testing | Test Suite (`tests/test_config_schema.py`) | Desktop UI Contract | Asserts structural integrity and safety invariant compliance of `CONFIG_SCHEMA`. |
| Host Boundary Isolation | Test Suite (`tests/test_config_schema.py`) | — | Validates that importing without stubs cleanly raises `ModuleNotFoundError`, ensuring no hidden runtime leaks. |
| Coverage & Typing Enforcement | CI / Tooling (`pytest-cov`, `mypy`) | — | Guarantees 100% test coverage and zero static type-check errors. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pytest` | 9.1.1 [VERIFIED: pyproject.toml:37] | Test runner and framework | Standard test runner configured in `pyproject.toml:47-50`. |
| `pytest-cov` | 7.1.0 [VERIFIED: pyproject.toml:38] | Statement and branch coverage measurement | Standard coverage plugin configured in `pyproject.toml:52-58`. |
| `dataclasses` | stdlib | Lightweight typed container stubs | Native Python 3.11+ stdlib container avoiding unneeded dependencies. |
| `unittest.mock` | stdlib | Dictionary and module patching | Native Python stdlib tool for non-leaking `sys.modules` patching (`patch.dict`). |
| `importlib` | stdlib | Programmatic module importing | Native Python stdlib tool for isolated import testing. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mypy` | 2.3.0 [VERIFIED: pyproject.toml:36] | Static type checking | Run via `uv run mypy notion_brain tests` per CI quality-debt job. |
| `ruff` | 0.16.0 [VERIFIED: pyproject.toml:39] | Code linting and formatting | Run via `uv run ruff check .` per CI quality-debt job. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Stdlib `@dataclass(frozen=True)` stubs | Anonymous `type("ProviderField", (), {})` | Anonymous classes lack type annotations, violating D-01 and failing mypy inspection. |
| `unittest.mock.patch.dict(sys.modules)` | Manual `del sys.modules["plugins"]` | Manual deletion risks test order leakage if an exception occurs before restoration. `patch.dict` guarantees teardown restoration [CITED: github.com/pytest-dev/pytest/blob/main/doc/en/how-to/monkeypatch.rst]. |

**Installation:**
No new dependencies required. Existing development dependencies are locked in `uv.lock`.

**Version verification:**
- `pytest`: 9.1.1 (confirmed via `uv run pytest --version`)
- `pytest-cov`: 7.1.0 (confirmed via `uv run pytest --version`)
- `mypy`: 2.3.0 (confirmed via `uv run mypy --version`)
- `ruff`: 0.16.0 (confirmed via `uv run ruff --version`)

## Package Legitimacy Audit

No external packages are installed in this phase. Existing development dependencies are locked in `uv.lock` and defined in `pyproject.toml:34-42`.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `pytest` | PyPI | 8+ yrs | >100M/mo | github.com/pytest-dev/pytest | [OK] | Approved (existing) |
| `pytest-cov` | PyPI | 8+ yrs | >50M/mo | github.com/pytest-dev/pytest-cov | [OK] | Approved (existing) |
| `mypy` | PyPI | 8+ yrs | >80M/mo | github.com/python/mypy | [OK] | Approved (existing) |
| `ruff` | PyPI | 2+ yrs | >50M/mo | github.com/astral-sh/ruff | [OK] | Approved (existing) |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
               +-------------------------------------------+
               |                pytest run                 |
               +-------------------------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |      tests/conftest.py      |
                      |  Registers stubs in         |
                      |  sys.modules:               |
                      |    - plugins                |
                      |    - plugins.memory         |
                      |    - plugins.memory.        |
                      |      config_schema          |
                      +-----------------------------+
                                     |
                                     v
                 +---------------------------------------+
                 |     tests/test_config_schema.py       |
                 +---------------------------------------+
                    |                |                |
                    |                |                v
                    v                v       +-------------------+
            +---------------+ +------------+ | Negative Import   |
            | Schema & Field| | Immutability| | Isolation:        |
            | Assertions    | | & Secrets  | | unittest.mock.    |
            | (D-04, D-05)  | | (D-06, D-07)| | patch.dict()      |
            +---------------+ +------------+ +-------------------+
                    |                |                |
                    +----------------+----------------+
                                     |
                                     v
                 +---------------------------------------+
                 |      notion_brain/config_schema.py    |
                 |  Executes cleanly in test run         |
                 |  Achieves 100% statement & branch cov |
                 +---------------------------------------+
```

### Recommended Project Structure
```
tests/
├── conftest.py              # Extended with plugins.memory.config_schema stubs
└── test_config_schema.py    # New unit tests for config_schema contract
```

### Pattern 1: Host Stub Registration via Dataclasses in `conftest.py`
**What:** Define typed immutable dataclasses representing `ProviderConfigSchema` and `ProviderField`, assign them along with host constants to a synthetic `ModuleType` chain, and register them into `sys.modules`.
**When to use:** In `tests/conftest.py` at test session setup.
**In-repo source:** `notion_brain/config_schema.py:3-9`:
```python
from plugins.memory.config_schema import (
    KIND_SECRET,
    KIND_TEXT,
    STORAGE_FLAT_JSON,
    ProviderConfigSchema,
    ProviderField,
)
```
**Example implementation:**
```python
import sys
import types
from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderField:
    key: str
    label: str
    kind: str
    description: str = ""
    env_key: str | None = None
    env_fallbacks: tuple[str, ...] = ()
    placeholder: str = ""
    inline: bool = False
    group: str = ""
    default: str | None = None

@dataclass(frozen=True)
class ProviderConfigSchema:
    name: str
    label: str
    storage: str
    fields: tuple[ProviderField, ...]

if "plugins" not in sys.modules:
    plugins_mod = types.ModuleType("plugins")
    memory_mod = types.ModuleType("plugins.memory")
    config_schema_mod = types.ModuleType("plugins.memory.config_schema")
    
    plugins_mod.memory = memory_mod
    memory_mod.config_schema = config_schema_mod
    
    config_schema_mod.KIND_SECRET = "secret"
    config_schema_mod.KIND_TEXT = "text"
    config_schema_mod.STORAGE_FLAT_JSON = "flat_json"
    config_schema_mod.ProviderConfigSchema = ProviderConfigSchema
    config_schema_mod.ProviderField = ProviderField
    
    sys.modules["plugins"] = plugins_mod
    sys.modules["plugins.memory"] = memory_mod
    sys.modules["plugins.memory.config_schema"] = config_schema_mod
```

### Pattern 2: Granular Property Contract Tests
**What:** Break schema validation into granular test functions (`test_schema_metadata`, `test_notion_api_key_field`, `test_hermes_home_field`, `test_schema_immutability`).
**When to use:** In `tests/test_config_schema.py` to satisfy D-04, D-05, D-06, and D-07.
**In-repo source:** `notion_brain/config_schema.py:11-38`:
```python
CONFIG_SCHEMA = ProviderConfigSchema(
    name="notion_brain",
    label="Hermes Brain (Notion)",
    storage=STORAGE_FLAT_JSON,
    fields=(
        ProviderField(
            key="notionApiKey",
            label="Notion API Key",
            kind=KIND_SECRET,
            description="Notion integration token. Create one at notion.so/my-integrations.",
            env_key="NOTION_API_KEY",
            placeholder="ntn_xxxxx_xxxxx",
            inline=True,
            group="Connection",
        ),
        ProviderField(
            key="hermesHome",
            label="Hermes Home",
            kind=KIND_TEXT,
            description="Directory for cache and config. Defaults to ~/.hermes.",
            default="~/.hermes",
            env_fallbacks=("HERMES_HOME",),
            placeholder="~/.hermes",
            inline=True,
            group="Connection",
        ),
    ),
)
```

### Pattern 3: Negative Import Isolation via `patch.dict(sys.modules)`
**What:** Verify that importing `notion_brain.config_schema` outside the host environment cleanly raises `ModuleNotFoundError`.
**When to use:** In `tests/test_config_schema.py` to satisfy D-08.
**Source:** pytest documentation [CITED: github.com/pytest-dev/pytest/blob/main/testing/test_pathlib.py].
**Example implementation:**
```python
import importlib
import sys
import unittest.mock
import pytest

def test_negative_import_without_host_stubs() -> None:
    """Verify that importing config_schema without plugins raises ModuleNotFoundError."""
    clean_modules = {
        k: v for k, v in sys.modules.items()
        if not k.startswith("plugins") and k != "notion_brain.config_schema"
    }
    with unittest.mock.patch.dict(sys.modules, clean_modules, clear=True):
        with pytest.raises(ModuleNotFoundError) as exc_info:
            importlib.import_module("notion_brain.config_schema")
        assert "plugins" in str(exc_info.value)
```

### Anti-Patterns to Avoid
- **Mutating `sys.modules` without restoration:** Deleting keys directly from `sys.modules` without `patch.dict` leaks state into subsequent tests.
- **Top-level module caching in negative tests:** If `notion_brain.config_schema` is already loaded in `sys.modules`, `importlib.import_module` returns the cached module without executing import statements. `notion_brain.config_schema` must be stripped alongside `plugins` during the negative test.
- **Missing parent attribute linkage:** Registering `plugins.memory.config_schema` in `sys.modules` without setting `plugins.memory = memory_mod` and `memory_mod.config_schema = config_schema_mod` causes `AttributeError` when accessing nested modules in standard Python import hooks.
- **Untyped test functions:** Omitting return type annotations `-> None` on test functions violates D-11 and triggers mypy inconsistencies.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Environment dictionary mocking | Custom dictionary save/restore context manager | `unittest.mock.patch.dict(sys.modules)` | Handles exception safety, clearing, and full dictionary restoration natively. |
| Stub class definitions | Anonymous `type()` metaclass calls or dict mockers | `dataclasses.dataclass(frozen=True)` | Generates clean typed representations inspectable by IDEs, tests, and mypy. |
| Test assertion framework | Custom assertion helpers or test runners | Standard `assert` with pytest introspection | Pytest provides detailed AST assertion failure diffs automatically. |

## Common Pitfalls

### Pitfall 1: Leaking Mock Modules Across Tests
**What goes wrong:** Modifying `sys.modules` directly in a test function causes subsequent tests to fail or behave differently depending on execution order.
**Why it happens:** `sys.modules` is a process-global dictionary shared across the entire test runner.
**How to avoid:** Use `unittest.mock.patch.dict(sys.modules, ..., clear=True)` as a context manager. It guarantees restoration upon block exit.
**Warning signs:** Tests pass in isolation (`pytest tests/test_config_schema.py`) but fail when run with the full suite (`pytest tests/`).

### Pitfall 2: Module Caching Defeating Negative Import Checks
**What goes wrong:** `importlib.import_module("notion_brain.config_schema")` in the negative test succeeds instead of raising `ModuleNotFoundError`.
**Why it happens:** `notion_brain.config_schema` was already imported by another test or at the top of the test module, so Python serves it from `sys.modules` cache without attempting to resolve `from plugins.memory.config_schema import ...`.
**How to avoid:** Explicitly filter out `notion_brain.config_schema` from the patched `sys.modules` dictionary inside the negative test context.
**Warning signs:** Negative import test fails with `Failed: DID NOT RAISE <class 'ModuleNotFoundError'>`.

### Pitfall 3: Submodule Attribute Missing on Parent Module
**What goes wrong:** `from plugins.memory.config_schema import ...` raises `ModuleNotFoundError: No module named 'plugins.memory'`.
**Why it happens:** Python module traversal checks `hasattr(plugins, 'memory')`. If only `sys.modules["plugins.memory"]` is set without `plugins.memory = memory_mod`, the import lookup fails in certain Python runtimes.
**How to avoid:** Wire parent-child module attributes explicitly: `plugins_mod.memory = memory_mod` and `memory_mod.config_schema = config_schema_mod`.

## Code Examples

### Complete `tests/conftest.py` Stub Extension
```python
# Source: tests/conftest.py:6-15 and D-01, D-02, D-03
import sys
import types
from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderField:
    key: str
    label: str
    kind: str
    description: str = ""
    env_key: str | None = None
    env_fallbacks: tuple[str, ...] = ()
    placeholder: str = ""
    inline: bool = False
    group: str = ""
    default: str | None = None

@dataclass(frozen=True)
class ProviderConfigSchema:
    name: str
    label: str
    storage: str
    fields: tuple[ProviderField, ...]

# Register host plugins stubs
if "plugins" not in sys.modules:
    plugins_mod = types.ModuleType("plugins")
    memory_mod = types.ModuleType("plugins.memory")
    config_schema_mod = types.ModuleType("plugins.memory.config_schema")
    
    plugins_mod.memory = memory_mod
    memory_mod.config_schema = config_schema_mod
    
    config_schema_mod.KIND_SECRET = "secret"
    config_schema_mod.KIND_TEXT = "text"
    config_schema_mod.STORAGE_FLAT_JSON = "flat_json"
    config_schema_mod.ProviderConfigSchema = ProviderConfigSchema
    config_schema_mod.ProviderField = ProviderField
    
    sys.modules["plugins"] = plugins_mod
    sys.modules["plugins.memory"] = memory_mod
    sys.modules["plugins.memory.config_schema"] = config_schema_mod
```

### Complete `tests/test_config_schema.py` Test Suite Pattern
```python
# Source: notion_brain/config_schema.py:11-38 and D-04, D-05, D-06, D-07, D-08, D-11
from __future__ import annotations

import importlib
import sys
import unittest.mock
import pytest

from plugins.memory.config_schema import KIND_SECRET, KIND_TEXT, STORAGE_FLAT_JSON
from notion_brain.config_schema import CONFIG_SCHEMA

def test_schema_metadata() -> None:
    """Verify top-level schema name, label, storage type, and field count."""
    assert CONFIG_SCHEMA.name == "notion_brain"
    assert CONFIG_SCHEMA.label == "Hermes Brain (Notion)"
    assert CONFIG_SCHEMA.storage == STORAGE_FLAT_JSON
    assert len(CONFIG_SCHEMA.fields) == 2

def test_notion_api_key_field() -> None:
    """Verify notionApiKey property configuration and secret protection."""
    field = CONFIG_SCHEMA.fields[0]
    assert field.key == "notionApiKey"
    assert field.label == "Notion API Key"
    assert field.kind == KIND_SECRET
    assert field.description == "Notion integration token. Create one at notion.so/my-integrations."
    assert field.env_key == "NOTION_API_KEY"
    assert field.placeholder == "ntn_xxxxx_xxxxx"
    assert field.inline is True
    assert field.group == "Connection"
    assert field.default is None
    assert field.env_fallbacks == ()

def test_hermes_home_field() -> None:
    """Verify hermesHome property configuration, fallbacks, and default."""
    field = CONFIG_SCHEMA.fields[1]
    assert field.key == "hermesHome"
    assert field.label == "Hermes Home"
    assert field.kind == KIND_TEXT
    assert field.description == "Directory for cache and config. Defaults to ~/.hermes."
    assert field.default == "~/.hermes"
    assert field.env_fallbacks == ("HERMES_HOME",)
    assert field.placeholder == "~/.hermes"
    assert field.inline is True
    assert field.group == "Connection"
    assert field.env_key is None

def test_schema_immutability() -> None:
    """Verify container immutability across fields and fallbacks."""
    assert isinstance(CONFIG_SCHEMA.fields, tuple)
    assert isinstance(CONFIG_SCHEMA.fields[1].env_fallbacks, tuple)

def test_negative_import_without_host_stubs() -> None:
    """Verify clean ModuleNotFoundError when host plugins package is absent."""
    clean_modules = {
        k: v for k, v in sys.modules.items()
        if not k.startswith("plugins") and k != "notion_brain.config_schema"
    }
    with unittest.mock.patch.dict(sys.modules, clean_modules, clear=True):
        with pytest.raises(ModuleNotFoundError) as exc_info:
            importlib.import_module("notion_brain.config_schema")
        assert "plugins" in str(exc_info.value)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mocking with untyped `MagicMock` in tests | Typed `@dataclass(frozen=True)` stubs in `conftest.py` | Python 3.7+ / modern pytest | Eliminates subtle attribute typos, provides strict immutability, and passes mypy cleanly without mock pollution. |
| Global mutable `sys.modules` edits in test files | Scoped `unittest.mock.patch.dict` or `monkeypatch` | Python 3.4+ / pytest 3+ | Guarantees test isolation and prevents test order execution pollution. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | *(No assumptions — all claims verified via in-repo source code inspection and pytest runtime tests)* | — | — |

## Open Questions

None. The schema structure, stub architecture, test assertions, and negative import behavior were verified against the running environment and existing test suite.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.11.15 (`.venv`), 3.12.3 (system) | — |
| uv | Package manager & environment runner | ✓ | 0.12.3 | `python3 -m venv` / `pip` |
| pytest | Test execution runner | ✓ | 9.1.1 | — |
| pytest-cov | Test coverage reporter | ✓ | 7.1.0 | — |
| mypy | Static type checking | ✓ | 2.3.0 | — |
| ruff | Linter & formatter | ✓ | 0.16.0 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-cov 7.1.0 [VERIFIED: pyproject.toml:37-38] |
| Config file | `pyproject.toml` [VERIFIED: pyproject.toml:47-58] |
| Quick run command | `uv run pytest tests/test_config_schema.py -v` |
| Full suite command | `uv run pytest` |
| Coverage check command | `uv run pytest --cov=notion_brain.config_schema --cov-fail-under=100 --cov-branch tests/test_config_schema.py` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHEMA-01 | Verify schema name, storage key, declared property fields | Unit | `uv run pytest tests/test_config_schema.py -k "test_schema_metadata or test_notion_api_key_field or test_hermes_home_field"` | ❌ Wave 0 (`tests/test_config_schema.py`) |
| SCHEMA-02 | Verify property kinds, defaults, secret status, and tuple immutability | Unit | `uv run pytest tests/test_config_schema.py -k "test_schema_immutability or test_notion_api_key_field"` | ❌ Wave 0 (`tests/test_config_schema.py`) |
| SCHEMA-03 | Host stubs in `conftest.py` permit offline execution without `ModuleNotFoundError` | Unit / Harness | `uv run pytest tests/test_config_schema.py` | ❌ Wave 0 (`tests/conftest.py` stub extension) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_config_schema.py`
- **Per wave merge:** `uv run pytest --cov=notion_brain.config_schema --cov-fail-under=100 --cov-branch tests/test_config_schema.py && uv run mypy notion_brain tests`
- **Phase gate:** Full suite green (`uv run pytest`), 100% coverage on `config_schema.py`, and mypy clean before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/conftest.py` — extend existing stubs with `plugins.memory.config_schema` (`ProviderConfigSchema`, `ProviderField`, `KIND_SECRET`, `KIND_TEXT`, `STORAGE_FLAT_JSON`)
- [ ] `tests/test_config_schema.py` — new test file covering SCHEMA-01, SCHEMA-02, and SCHEMA-03

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Strict dataclass typing and tuple immutability verification guarding against tampering. |
| V6 Cryptography | no | — |
| Secret Management | yes | Strict enforcement of D-07: `notionApiKey` (`kind=KIND_SECRET`) must have `default is None` to prevent credential exposure or hardcoded defaults [VERIFIED: notion_brain/config_schema.py:16-25]. |

### Known Threat Patterns for Configuration Schemas

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| In-place schema mutation | Tampering | Immutable tuples for `CONFIG_SCHEMA.fields` and `env_fallbacks` prevent runtime tampering by callers. |
| Hardcoded credential defaults | Information Disclosure | Secret field safety test asserting `default is None` on `KIND_SECRET` fields. |

## Sources

### Primary (HIGH confidence)
- `notion_brain/config_schema.py:1-38` — Source definition of `CONFIG_SCHEMA`, `ProviderConfigSchema`, `ProviderField`.
- `tests/conftest.py:1-16` — Existing runtime stub harness for Hermes host packages.
- `pyproject.toml:34-73` — Package metadata, locked dependencies, pytest configuration, mypy configuration.
- `mypy.ini:1-14` — Static type checker suppression configuration (`ignore_missing_imports = True` for `plugins.*`).
- Context7 `/pytest-dev/pytest` — Official documentation on `monkeypatch` and `unittest.mock.patch.dict(sys.modules)` [CITED: github.com/pytest-dev/pytest/blob/main/doc/en/how-to/monkeypatch.rst].

### Secondary (MEDIUM confidence)
- GSD Seam tool `package-legitimacy check` — Verified legitimacy of pytest ecosystem packages.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Verified via `pyproject.toml`, `.venv`, and `uv run pytest`.
- Architecture: HIGH — Verified via standalone Python runtime simulation and test suite execution.
- Pitfalls: HIGH — Verified via `patch.dict(sys.modules)` behavior and Python import caching mechanics.

**Research date:** 2026-09-20
**Valid until:** Stable indefinitely (relies on Python stdlib dataclasses and standard pytest patterns).
