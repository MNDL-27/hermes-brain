---
phase: 05-cli-update-drift-detection
verified: 2026-09-26T00:00:00Z
status: passed
score: 5/5 must-haves verified
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/phases/05-cli-update-drift-detection/05-01-PLAN.md
  - .planning/phases/05-cli-update-drift-detection/05-01-SUMMARY.md
  - notion_brain/__main__.py
  - notion_brain/update.py
  - tests/characterization/test_cli_contract.py
  - tests/test_update.py
covered_digest: "v1:sha256:caba8dee6f45d7c4f174d1c28abb3082939df30bbedae743321f9c64336c20db"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 5/5
  reason: "Source recommitted at HEAD 5fb52ea after a ruff format pass; prior covered_digest (v1:sha256:42be373110d1e2c35572e9d7222d1554604516b75f58ef7fd6bf7eb435ddec7e) was stale."
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 5: CLI Update Drift Detection Verification Report

**Phase Goal:** Users running hermes-brain from any install mode (uv, pip venv, pip user, git clone) can check for newer releases and get exact, copy-pasteable upgrade instructions — without the tool ever modifying their environment.
**Verified:** 2026-09-26
**Status:** passed
**Re-verification:** Yes — digest refresh after ruff-format recommit (HEAD 5fb52ea). No behavioral change; all five must-haves re-confirmed against committed source.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | UPD-01: `update` prints installed + latest GitHub release; drift line shown when versions differ | ✓ VERIFIED | `check_for_update` (update.py:133) reads `notion_brain.__version__` and `bootstrap._find_latest_tag()`; `format_human` (update.py:174) emits `installed:` / `latest:` lines with `(UPDATE AVAILABLE)` / `(up to date)`. Live run `python -m notion_brain update --check --json` printed `current: 1.0.3`, `latest: 1.0.1`. Tests `test_cmd_update_check_exits_*`, `test_update_check_only_*` pass. |
| 2 | UPD-02: copy-pasteable upgrade command matches detected install mode, using `hermes-brain` dist name for wheel/pip | ✓ VERIFIED | `build_upgrade_command` (update.py:111) dispatches uv / pip_venv / pip_user / git_clone; all pip paths use `hermes-brain==<v>`. Inline asserts confirmed exact strings for all four modes. Tests `test_build_upgrade_command_*` pass. |
| 3 | UPD-03: integer-tuple SemVer with pre-release ranking (1.10.0>1.9.0, 1.1.0>1.1.0b1) | ✓ VERIFIED | `parse_semver` (update.py:32) returns `(M,m,p,pre_slot)` with `(inf,)` sentinel for releases. Inline confirmed 1.10.0>1.9.0, 1.1.0 > b1/a1/rc1, 2.0.0>1.99.99. Tests `test_semver_*`, `test_compare_versions_*` pass. |
| 4 | UPD-04: `--check` exits 0 current / 2 drift; `--json` emits parseable payload | ✓ VERIFIED | `_cmd_update` (\_\_main\_\_.py:195) returns `2 if result['drift'] else 0`; live `--check --json` exited 0 with valid JSON payload. Tests `test_cmd_update_check_exits_0/2`, `test_cmd_update_check_json_*` pass. |
| 5 | UPD-05: command never runs pip install / git pull / mutates environment | ✓ VERIFIED (behavioral) | No mutating literals in `__main__.py` (grep found only one docstring mention at line 198). `_git_pull_and_install`/`_checkout_tag_and_install`/`_reinstall` removed. Behavioral guard tests patch `subprocess.run` to raise on any mutating call and pass: `test_check_for_update_no_mutation_when_drift_detected`, `test_check_for_update_no_mutation_when_current`, `test_cmd_update_no_flags_does_not_invoke_pip_or_git`, `test_update_command_detects_drift_without_mutating`. Only read-only `pip show` invoked for mode detection. |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `notion_brain/update.py` | semver, mode detection, command gen, check, JSON/human format | ✓ VERIFIED | All 7 public functions present (parse_semver, compare_versions, detect_install_mode, build_upgrade_command, check_for_update, format_human, format_json); stdlib-only imports (json, re, subprocess, sys, pathlib, typing); wired into `__main__.py`. |
| `notion_brain/__main__.py` | thin `_cmd_update` wrapper, `--check`/`--json` flags | ✓ VERIFIED | `_cmd_update` delegates to `update.check_for_update`; both flags in the `update` subparser; dispatcher routes `update` before the NOTION_API_KEY gate. No mutating subprocess. |
| `tests/test_update.py` | offline unit coverage | ✓ VERIFIED | 26 tests; runs offline; passes. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `update.py:check_for_update` | `bootstrap._find_latest_tag` | direct call | ✓ WIRED | Called inside try/except; network error surfaced as `error` field, `latest=None`. Signature `() -> str | None` unchanged. |
| `update.py:build_upgrade_command` | mode string table | pure dispatch | ✓ WIRED | Exact strings verified inline. |
| `__main__.py:_cmd_update` | `update.check_for_update` | `from . import update as update_mod` | ✓ WIRED | Result drives print + exit code. |
| `main` dispatcher | `_cmd_update` | `args.cmd == 'update'` | ✓ WIRED | Routed before the API-key check so offline runs work. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `format_human`/`format_json` | `current` | `notion_brain.__version__` | Yes | ✓ FLOWING |
| `format_human`/`format_json` | `latest` | `bootstrap._find_latest_tag()` (live GitHub tags API) | Yes (live run returned `1.0.1`) | ✓ FLOWING |
| `format_*` | `install_mode` | `detect_install_mode` via read-only `pip show` | Yes (safe `unknown` fallback) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| CLI JSON payload parseable, exit code correct | `python -m notion_brain update --check --json` | valid JSON, exit 0 (no drift; current 1.0.3, latest 1.0.1) | ✓ PASS |
| SemVer ranking + per-mode commands | inline `parse_semver`/`build_upgrade_command` asserts | OK | ✓ PASS |
| Update + CLI-contract suites | `pytest tests/test_update.py tests/characterization/test_cli_contract.py` | 34 passed (1.63s) | ✓ PASS |
| No-mutation invariant (UPD-05) | subprocess-raise guard tests | passed | ✓ PASS |
| No mutating literals in update path | grep of `__main__.py` | only a docstring mention at line 198 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| UPD-01 | 05-01 | Detect drift, print installed vs latest | ✓ SATISFIED | Truth 1 |
| UPD-02 | 05-01 | Per-env copy-pasteable upgrade command | ✓ SATISFIED | Truth 2 |
| UPD-03 | 05-01 | Integer-tuple SemVer with pre-release ranking | ✓ SATISFIED | Truth 3 |
| UPD-04 | 05-01 | `--check` exit 0/2; `--json` payload | ✓ SATISFIED | Truth 4 |
| UPD-05 | 05-01 | Detect+instruct only, no mutation | ✓ SATISFIED | Truth 5 |

No orphaned requirements: REQUIREMENTS.md maps exactly UPD-01..05 to Phase 5, all claimed by plan 05-01. (Note: REQUIREMENTS.md still shows these as `[ ]` Pending — a documentation-status lag, not a code gap; the implementation satisfies each.)

### Prohibitions

| Prohibition | Status | Evidence |
| --- | --- | --- |
| No pip install / git pull mutation in `_cmd_update` / `check_for_update` | ✓ VERIFIED | No mutating subprocess; enforced by 4 passing subprocess-guard tests. |
| Do not change `bootstrap._find_latest_tag` / `_check_for_update` signatures | ✓ VERIFIED | Both remain `() -> str | None` (bootstrap.py:618, :642). |
| No new third-party dependencies; stdlib only | ✓ VERIFIED | `update.py` imports only json, re, subprocess, sys, pathlib, typing. |

### Anti-Patterns Found

None. No TODO/FIXME/XXX/HACK/PLACEHOLDER markers in `update.py`, `__main__.py`, or `tests/test_update.py`.

### Gaps Summary

No gaps. All five success criteria are observably met in the committed codebase (HEAD 5fb52ea) and exercised by passing offline tests (34 total across the two suites), independent inline checks, and a live CLI run. UPD-05 (the no-mutation invariant) is behaviorally verified, not merely present, via four subprocess-guard tests. The `covered_digest` was regenerated against the ruff-formatted source and now matches the commit (`v1:sha256:caba8dee...`, superseding the stale `v1:sha256:42be3731...`).

**Noted deviation (non-blocking):** PLAN task 2 specified that bare `update` (no `--check`) should print a one-line notice and exit 0. The shipped `_cmd_update` instead always runs the check and prints the full report, exiting 0/2 on drift. This deviation better satisfies ROADMAP SC1 (bare `update` prints both versions) and does not violate UPD-05 (still no mutation). The characterization test `test_update_command_detects_drift_without_mutating` codifies the shipped behavior.

---

_Verified: 2026-09-26_
_Verifier: Claude (gsd-verifier)_
