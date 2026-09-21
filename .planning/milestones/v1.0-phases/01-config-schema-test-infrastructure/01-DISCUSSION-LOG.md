# Phase 1: Config Schema Test Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-20
**Phase:** 1-Config Schema Test Infrastructure
**Areas discussed:** Host Stub Architecture, Assertion Strictness, Immutability & Safety Checks, Unstubbed Import Behavior, Coverage Enforcement, Mypy Typing in Tests

---

## Host Stub Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Global conftest Classes (Recommended) | Define dataclasses or lightweight classes with kwargs in `tests/conftest.py` matching Hermes host contract (`name`, `label`, `storage`, `fields`). Consistent with existing `agent` stubs. | ✓ |
| Scoped Test Fixture | Inject stubs dynamically inside a pytest fixture in `tests/test_config_schema.py` and restore `sys.modules` on teardown. | |
| Claude Decides | Leave design and placement to Claude discretion during planning and implementation. | |

**User's choice:** Global conftest Classes (Recommended)
**Notes:** Stubs registered in `tests/conftest.py` before test collection.

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror Host Values (Recommended) | Set `KIND_SECRET="secret"`, `KIND_TEXT="text"`, `STORAGE_FLAT_JSON="flat_json"` in the stub module to mirror Hermes desktop constants. | ✓ |
| Sentinel Objects | Use opaque sentinel objects or enum classes for constants. | |
| Claude Decides | Claude decides exact constant representation during implementation. | |

**User's choice:** Mirror Host Values (Recommended)
**Notes:** Explicit string values matching external host runtime.

---

## Assertion Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Exhaustive Property Check (Recommended) | Assert every attribute on `CONFIG_SCHEMA` and both `ProviderField` instances (`key`, `label`, `kind`, `description`, `env_key`, `env_fallbacks`, `placeholder`, `inline`, `group`, `default`). Prevents any silent UI drift. | ✓ |
| Core Contract Only | Assert only critical runtime keys (`name`, `storage`, field `key`, `kind`, `default`, secret status). Ignores UI text/descriptions. | |
| Claude Decides | Let Claude determine assertion granularity during planning. | |

**User's choice:** Exhaustive Property Check (Recommended)
**Notes:** Strict regression testing on all metadata attributes.

| Option | Description | Selected |
|--------|-------------|----------|
| Granular Test Functions (Recommended) | Separate focused test functions (`test_schema_metadata`, `test_notion_api_key_field`, `test_hermes_home_field`, `test_field_immutability`). Provides clear failure messages when specific fields drift. | ✓ |
| Unified Test Suite | Single unified test function validating the entire schema tree in one pass. | |
| Claude Decides | Claude decides test layout and function breakdown. | |

**User's choice:** Granular Test Functions (Recommended)
**Notes:** Clear reporting on individual property changes.

---

## Immutability & Safety Checks

| Option | Description | Selected |
|--------|-------------|----------|
| Tuple Immutability Asserts (Recommended) | Verify `CONFIG_SCHEMA.fields` is an instance of `tuple` and that `env_fallbacks` on `hermesHome` is a `tuple`, preventing in-place mutation by callers. | ✓ |
| Duck-Type Iterable Only | Only check that fields can be iterated over without checking concrete container type. | |
| Claude Decides | Claude decides immutability check depth. | |

**User's choice:** Tuple Immutability Asserts (Recommended)
**Notes:** Assert immutable tuple instances.

| Option | Description | Selected |
|--------|-------------|----------|
| No Secret Defaults Rule (Recommended) | Explicitly assert that `notionApiKey` (`kind=KIND_SECRET`) has `default is None` or unset, guarding against accidental hardcoded credential defaults. | ✓ |
| Field-Specific Only | Check only that `notionApiKey.default is None` without validating general secret-safety rule. | |
| Claude Decides | Claude decides secret safety validation details. | |

**User's choice:** No Secret Defaults Rule (Recommended)
**Notes:** Hard security rule preventing defaults on secret fields.

---

## Unstubbed Import Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Negative Import Test (Recommended) | Add test using `unittest.mock.patch.dict(sys.modules)` to remove `plugins` and verify `importlib.reload(config_schema)` raises `ModuleNotFoundError`. Proves dependency boundary is real. | ✓ |
| Normal Path Only | Skip negative import testing — assume conftest stubs are always active during test runs. | |
| Claude Decides | Claude decides whether to include negative import test. | |

**User's choice:** Negative Import Test (Recommended)
**Notes:** Negative boundary check confirms host requirement.

---

## Coverage Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| 100% Branch & Statement (Recommended) | Verify `pytest --cov=notion_brain.config_schema --cov-fail-under=100 --cov-branch` passes with 100% branch and statement coverage. Locks in total schema test coverage. | ✓ |
| Standard Line Coverage | Require basic line coverage without strict `--cov-branch` or fail-under flag. | |
| Claude Decides | Claude decides coverage verification flags. | |

**User's choice:** 100% Branch & Statement (Recommended)
**Notes:** 100% statement and branch coverage required.

| Option | Description | Selected |
|--------|-------------|----------|
| CLI Target Only (Recommended) | Leave global `pyproject.toml` coverage settings untouched; invoke coverage via CLI target `--cov=notion_brain.config_schema` during phase verification. Keeps existing coverage baseline intact. | ✓ |
| Update pyproject.toml | Add dedicated test configuration or coverage rule in `pyproject.toml`. | |
| Claude Decides | Claude decides configuration approach. | |

**User's choice:** CLI Target Only (Recommended)
**Notes:** No edits to `pyproject.toml` coverage baseline.

---

## Mypy Typing in Tests

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit Typing (Recommended) | Full explicit type annotations (`def test_...() -> None:`, typed dataclass fields on stub classes in `conftest.py`). Ensures zero warnings when Mypy inspects `tests/`. | ✓ |
| Standard Pytest Style | Standard untyped test functions without return annotations. | |
| Claude Decides | Claude decides typing precision. | |

**User's choice:** Explicit Typing (Recommended)
**Notes:** Clean Mypy check with explicit `-> None`.

| Option | Description | Selected |
|--------|-------------|----------|
| Real Typed Classes (Recommended) | Define real classes with explicit typed attributes (`ProviderConfigSchema`, `ProviderField`) in `tests/conftest.py`. Provides clean type inference and IDE support across test files. | ✓ |
| Dynamic Type Factories | Use dynamic `type('ProviderField', (), {})` factory matching the existing `agent.memory_provider` pattern in `conftest.py`. | |
| Claude Decides | Claude decides stub class implementation style. | |

**User's choice:** Real Typed Classes (Recommended)
**Notes:** Real class structures in `tests/conftest.py`.

---

## Claude's Discretion

None — all 6 decision areas were explicitly answered by user.

## Deferred Ideas

None — discussion stayed within phase scope.
