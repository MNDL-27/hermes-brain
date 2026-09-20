# Phase 01: Config Schema Test Infrastructure - Pattern Map

**Mapped:** 2026-09-20
**Files analyzed:** 2
**Analogs found:** 2 / 2

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tests/conftest.py` | config | static setup | `tests/conftest.py` | exact |
| `tests/test_config_schema.py` | test | declarative assertion | `tests/test_bootstrap_schema.py` | exact |

## Pattern Assignments

### `tests/conftest.py` (config, static setup)

**Analog:** `tests/conftest.py`

**Imports pattern** (lines 1-2):
```python
import sys
import types
from dataclasses import dataclass
```

**Auth/Guard:**
N/A. Offline test harness. No network or API credentials allowed.

**Core pattern (stub registration)** (`tests/conftest.py` lines 6-15):
```python
# Stub out the Hermes runtime — not installed in dev env.
# Do NOT stub notion_brain; the tests import from it directly.
for mod_name in ['agent', 'agent.memory_manager', 'agent.memory_provider', 'tools', 'tools.registry']:
    if mod_name not in sys.modules:
        mod = types.ModuleType(mod_name)
        if mod_name == 'agent.memory_manager':
            setattr(mod, 'sanitize_context', lambda x: x)
        elif mod_name == 'agent.memory_provider':
            setattr(mod, 'MemoryProvider', type('MemoryProvider', (), {}))
        elif mod_name == 'tools.registry':
            setattr(mod, 'tool_error', lambda x: 'error: ' + str(x))
        sys.modules[mod_name] = mod
```

**Extension pattern for `plugins.memory.config_schema` stubs:**
```python
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

**Error handling pattern:**
Pre-import existence check `if "plugins" not in sys.modules:` prevents stomping modules if already registered. Parent-child attribute linking (`plugins_mod.memory = memory_mod`, `memory_mod.config_schema = config_schema_mod`) prevents `AttributeError` on subpackage traversal.

**Validation pattern:**
Frozen dataclasses enforce read-only schema definitions at Python runtime.

---

### `tests/test_config_schema.py` (test, declarative assertion)

**Analog:** `tests/test_bootstrap_schema.py` and `tests/characterization/test_cli_contract.py`

**Imports pattern** (`tests/characterization/test_cli_contract.py` lines 3-15):
```python
from __future__ import annotations

import importlib
import sys
import unittest.mock
from pathlib import Path

import pytest
```

**Auth/Guard:**
N/A. Offline test execution. No API calls or secret persistence.

**Core assertion pattern** (`tests/test_bootstrap_schema.py` lines 19-31):
```python
def test_status_property_options_match_schema_statuses():
    for db_name, props in bootstrap._PROPS.items():
        status = props.get("Status") or {}
        if "status" not in status:
            continue
        names = {o["name"] for o in status["status"].get("options", [])}
        assert names == STATUSES, db_name


def test_database_schema_matches_expected_schema():
    db = _notion_db_from_expected(bootstrap._PROPS["memory"])
    assert bootstrap._database_schema_matches(db, bootstrap._PROPS["memory"])
```

**Targeted schema assertion pattern for `CONFIG_SCHEMA`:**
```python
from plugins.memory.config_schema import KIND_SECRET, KIND_TEXT, STORAGE_FLAT_JSON
from notion_brain.config_schema import CONFIG_SCHEMA


def test_schema_metadata() -> None:
    assert CONFIG_SCHEMA.name == "notion_brain"
    assert CONFIG_SCHEMA.label == "Hermes Brain (Notion)"
    assert CONFIG_SCHEMA.storage == STORAGE_FLAT_JSON
    assert len(CONFIG_SCHEMA.fields) == 2


def test_notion_api_key_field() -> None:
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
    assert isinstance(CONFIG_SCHEMA.fields, tuple)
    assert isinstance(CONFIG_SCHEMA.fields[1].env_fallbacks, tuple)
```

**Negative import isolation pattern (`unittest.mock.patch.dict` with `pytest.raises`)** (`tests/test_coverage_gaps.py` lines 14, 24, and `mypy.ini` import isolation):
```python
def test_negative_import_without_host_stubs() -> None:
    clean_modules = {
        k: v for k, v in sys.modules.items()
        if not k.startswith("plugins") and k != "notion_brain.config_schema"
    }
    with unittest.mock.patch.dict(sys.modules, clean_modules, clear=True):
        with pytest.raises(ModuleNotFoundError) as exc_info:
            importlib.import_module("notion_brain.config_schema")
        assert "plugins" in str(exc_info.value)
```

**Error handling / Negative assertion pattern:**
`pytest.raises(ModuleNotFoundError)` tests boundary condition when host stubs absent. `clear=True` in `unittest.mock.patch.dict` guarantees teardown and state restoration after test exit.

**Validation pattern:**
Static type checking via annotations `def test_...() -> None:` enforced under `[tool.mypy]` in `pyproject.toml` and `mypy.ini`.

---

## Shared Patterns

### Stub Harness Registration
**Source:** `tests/conftest.py` lines 6-15
**Apply to:** `tests/conftest.py`
Register synthetic module hierarchies into `sys.modules` during early pytest discovery so test modules import top-level package paths without host environment installation.
```python
for mod_name in ['agent', 'agent.memory_manager', 'agent.memory_provider', 'tools', 'tools.registry']:
    if mod_name not in sys.modules:
        mod = types.ModuleType(mod_name)
        ...
        sys.modules[mod_name] = mod
```

### Static Type Annotations in Test Functions
**Source:** `tests/characterization/test_cli_contract.py` lines 3-18
**Apply to:** `tests/test_config_schema.py`
Every test function declares explicit `-> None` return type and typed arguments, complying with `mypy.ini` and `pyproject.toml:61` (`files = ["notion_brain", "tests"]`).
```python
from __future__ import annotations

def test_something() -> None:
    assert ...
```

### Isolated Environment Mocking with Automatic Restoration
**Source:** `tests/test_custom_databases.py` lines 14-19 / `tests/test_auto_sync.py` lines 14-19
**Apply to:** `tests/test_config_schema.py`
Use context manager or fixture teardown (`unittest.mock.patch.dict(sys.modules, ..., clear=True)`) to ensure global dictionaries return to initial state on test exit.
```python
with unittest.mock.patch.dict(sys.modules, clean_modules, clear=True):
    # execute isolated logic
    ...
```

## No Analog Found

None. All files have direct analogs in `tests/`.

## Metadata

**Analog search scope:** `tests/`, `notion_brain/`
**Files scanned:** 10
**Pattern extraction date:** 2026-09-20
