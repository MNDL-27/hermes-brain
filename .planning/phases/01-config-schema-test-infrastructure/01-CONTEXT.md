# Phase 1: Config Schema Test Infrastructure - Context

**Gathered:** 2026-09-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 establishes unit test coverage for `notion_brain/config_schema.py` and provides host runtime stubs in `tests/conftest.py` so the test suite runs in standalone isolation without `ModuleNotFoundError` when the external Hermes host environment is absent. It covers schema validation, property attributes, type hints, immutability, negative import behavior, and 100% statement/branch test coverage.

</domain>

<decisions>
## Implementation Decisions

### Host Stub Architecture
- **D-01:** Define real, typed classes (`ProviderConfigSchema`, `ProviderField`) in `tests/conftest.py` attached to `plugins.memory.config_schema` rather than dynamic anonymous objects.
- **D-02:** Mirror Hermes host constants in `plugins.memory.config_schema` stub: `KIND_SECRET = "secret"`, `KIND_TEXT = "text"`, and `STORAGE_FLAT_JSON = "flat_json"`.
- **D-03:** Register stubs globally in `tests/conftest.py` alongside existing `agent.*` and `tools.*` stubs before test discovery.

### Assertion Strictness
- **D-04:** Perform exhaustive property assertions across `CONFIG_SCHEMA` and both fields (`notionApiKey` and `hermesHome`), verifying `key`, `label`, `kind`, `description`, `env_key`, `env_fallbacks`, `placeholder`, `inline`, `group`, and `default`.
- **D-05:** Organize assertions into focused, granular test functions (`test_schema_metadata`, `test_notion_api_key_field`, `test_hermes_home_field`, `test_schema_immutability`) to deliver precise test failure reporting.

### Immutability & Safety Checks
- **D-06:** Enforce container immutability assertions: verify `isinstance(CONFIG_SCHEMA.fields, tuple)` and `isinstance(hermesHome.env_fallbacks, tuple)` to ensure callers cannot mutate field definitions in place.
- **D-07:** Enforce secret field safety rule: assert that `notionApiKey` (`kind=KIND_SECRET`) has `default is None` (or unset default), guarding against accidental credential defaults.

### Negative Import Behavior
- **D-08:** Add negative import test using `unittest.mock.patch.dict(sys.modules)` to remove `plugins` and verify that importing `notion_brain.config_schema` cleanly raises `ModuleNotFoundError` when stubs are absent.

### Coverage Enforcement
- **D-09:** Verify that `pytest --cov=notion_brain.config_schema --cov-fail-under=100 --cov-branch` achieves 100% statement and branch coverage on `notion_brain/config_schema.py`.
- **D-10:** Keep `pyproject.toml` global coverage configuration untouched; target `notion_brain.config_schema` explicitly via CLI invocation during verification.

### Mypy Typing in Tests
- **D-11:** Apply full explicit typing in `tests/test_config_schema.py` (`def test_...() -> None:`) and typed attributes on stub classes in `tests/conftest.py` to ensure clean passage under `mypy.ini` without warnings.

### Claude's Discretion
- Internal test helper structure and fixture naming choices.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source Code
- `notion_brain/config_schema.py` — Declared configuration schema defining Desktop panel UI surface (`CONFIG_SCHEMA`, `ProviderConfigSchema`, `ProviderField`).
- `tests/conftest.py` — Test harness configuration and host module stubs for standalone environments (`agent.*`, `tools.*`).

### Project Context & Quality Gates
- `.planning/REQUIREMENTS.md` § Config Schema Testing — Requirements SCHEMA-01, SCHEMA-02, SCHEMA-03.
- `.planning/ROADMAP.md` § Phase 1 — Phase goals and success criteria.
- `mypy.ini` — Type checking configuration and module suppression rules.
- `pyproject.toml` — Pytest runner options and coverage baseline settings.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py`: Existing `sys.modules` loop mocking `agent`, `agent.memory_manager`, `agent.memory_provider`, and `tools.registry`. Can be extended to register `plugins.memory.config_schema`.

### Established Patterns
- Isolated contract testing: Existing tests in `tests/` mock external boundaries so tests run offline in sub-second time without live credentials or external daemons.
- Static typing: Strict typing adherence defined in `mypy.ini` with `ignore_missing_imports = True`.

### Integration Points
- `tests/test_config_schema.py`: New test module imported by `pytest tests/`.
- `tests/conftest.py`: Executed at test session startup to register stubs in `sys.modules`.

</code_context>

<specifics>
## Specific Ideas

- Ensure `ProviderConfigSchema` and `ProviderField` stubs in `tests/conftest.py` faithfully reproduce the expected signature and attribute access so `notion_brain/config_schema.py` imports without friction.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Config Schema Test Infrastructure*
*Context gathered: 2026-09-20*
