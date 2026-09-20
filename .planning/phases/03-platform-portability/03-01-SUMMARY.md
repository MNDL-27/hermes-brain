---
phase: 03-platform-portability
plan: 01
type: execute
wave: 1
status: complete
---

## Summary

Phase 03 executed. Darwin platform detection added to `scripts/install.sh` with graceful manual-setup exit.

### What was done

- **`scripts/install.sh`** — Added Darwin guard (Step 0) before root check and Hermes detection. On `uname -s = Darwin`: prints manual setup instructions referencing README Quickstart Step 2 and exits with status 0.
- **`tests/test_install_guard.py`** — New suite (2 tests) running the real script with a stubbed `uname` binary:
  - `test_darwin_prints_manual_setup_and_exits_zero` (PLAT-01): exit 0, README Quickstart URL in output, no false-positive Linux/Hermes errors
  - `test_linux_unname_continues_past_guard` (PLAT-02/PLAT-03): Linux passes guard with no false-positive errors

### Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_install_guard.py -v` | **2/2 passed** |
| Full suite `uv run pytest -q` | **303/303 passed** |
| `uv run mypy notion_brain tests` | **Clean (27 files)** |
