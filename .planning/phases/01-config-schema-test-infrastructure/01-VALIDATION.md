---
phase: "01"
slug: "config-schema-test-infrastructure"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-20"
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-cov 7.1.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_config_schema.py -v` |
| **Full suite command** | `uv run pytest` |
| **Coverage check command** | `uv run pytest --cov=notion_brain.config_schema --cov-fail-under=100 --cov-branch tests/test_config_schema.py` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_config_schema.py -v`
- **After every plan wave:** Run `uv run pytest --cov=notion_brain.config_schema --cov-fail-under=100 --cov-branch tests/test_config_schema.py && uv run mypy notion_brain tests`
- **Before `/gsd-verify-work`:** Full suite must be green (`uv run pytest`), 100% coverage on `config_schema.py`, and mypy clean
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | SCHEMA-03 | T-01-01 | Host stubs isolated in test harness | unit / harness | `uv run pytest tests/test_config_schema.py` | ❌ W0 (`tests/conftest.py`) | ⬜ pending |
| 01-01-02 | 01 | 1 | SCHEMA-01 | T-01-02 | Schema contract & metadata integrity | unit | `uv run pytest tests/test_config_schema.py -k "test_schema_metadata or test_notion_api_key_field or test_hermes_home_field"` | ❌ W0 (`tests/test_config_schema.py`) | ⬜ pending |
| 01-01-03 | 01 | 1 | SCHEMA-02 | T-01-03 | Secret credential safety & immutability | unit | `uv run pytest tests/test_config_schema.py -k "test_schema_immutability or test_notion_api_key_field or test_negative_import"` | ❌ W0 (`tests/test_config_schema.py`) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — extend runtime stubs for `plugins.memory.config_schema` (`ProviderConfigSchema`, `ProviderField`, `KIND_SECRET`, `KIND_TEXT`, `STORAGE_FLAT_JSON`)
- [ ] `tests/test_config_schema.py` — new test suite covering SCHEMA-01, SCHEMA-02, and SCHEMA-03

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | — | All phase behaviors have automated verification. |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
