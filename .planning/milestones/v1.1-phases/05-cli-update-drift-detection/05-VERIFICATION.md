---
phase: 05-cli-update-drift-detection
verified: 2026-09-29T00:00:00Z
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
covered_digest: "v2:sha256:a331a8527b8122057b6d7d6e0b39affd4bf69d3b8d054abc646838f0d45b32e8"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 5/5
  reason: "Stale covered_digest. Commit a0c7390 (feat(06): wire update cache into provider init and health report) modified shared source (notion_brain/provider.py, bootstrap.health_report) after the phase-05 verifier last ran, so the prior digest (v1:sha256:caba8dee6f45d7c4f174d1c28abb3082939df30bbedae743321f9c64336c20db) no longer matched HEAD. Re-verified against the current codebase and regenerated the digest (now v2 format)."
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 5: CLI Update Drift Detection Verification Report

**Phase Goal:** Users running hermes-brain from any install mode (uv, pip venv, pip user, git clone) can check for newer releases and get exact, copy-pasteable upgrade instructions — without the tool ever modifying their environment.
**Verified:** 2026-09-29
**Status:** passed
**Re-verification:** Yes — digest refresh after Phase 06 (commit a0c7390) touched shared source. All five must-haves re-confirmed against HEAD; Phase 06 introduced no regression to the Phase 05 update path.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | UPD-01: `update --check` prints installed + latest GitHub release; drift line shown when versions differ | ✓ VERIFIED | `check_for_update` (update.py:133) reads `notion_brain.__version__` and `bootstrap._find_latest_tag()`; `format_human` (update.py:174) emits `installed:` / `latest:` lines with `(UPDATE AVAILABLE)` / `(up to date)` / `unknown`. Live inline run reported `current=1.0.3 latest=1.0.1 drift=False`. Tests `test_cmd_update_check_exits_0/2`, `test_check_for_update_*` pass. |
| 2 | UPD-02: copy-pasteable upgrade command matches detected install mode, using `hermes-brain` dist name for wheel/pip | ✓ VERIFIED | `build_upgrade_command` (update.py:111) dispatches uv / pip_user / git_clone with pip_venv+unknown fallback; all pip paths use `hermes-brain==<v>`. Inline asserts confirmed exact strings for all four modes plus git_clone `v1.2.3` fetch/checkout string. Tests `test_build_upgrade_command_*` pass. |
| 3 | UPD-03: integer-tuple SemVer with pre-release ranking (1.10.0>1.9.0, 1.1.0>1.1.0b1) | ✓ VERIFIED | `parse_semver` (update.py:32) returns `(M,m,p,pre_slot)` with `(float('inf'),)` release sentinel and `(rank,n)` pre-release slot. Inline confirmed 1.10.0>1.9.0, 1.1.0 > b1/a1/rc1, 2.0.0>1.99.99. Tests `test_semver_*`, `test_compare_versions_*` pass. |
| 4 | UPD-04: `--check` exits 0 current / 2 drift; `--json` emits parseable payload | ✓ VERIFIED | `_cmd_update` (__main__.py:195) returns `2 if result.get('drift') else 0`; `--json` prints `format_json` (json.dumps, indent=2, sort_keys). Payload round-trips through json.loads inline. Tests `test_cmd_update_check_exits_0/2_*`, `test_cmd_update_check_json_exits_0/2_*`, `test_format_json_is_parseable_and_round_trips` pass. |
| 5 | UPD-05: command never runs pip install / git pull / mutates environment | ✓ VERIFIED (behavioral) | No mutating literals in `__main__.py` (only a docstring mention at line 198); no `subprocess` import there; `_git_pull_and_install`/`_checkout_tag_and_install`/`_reinstall` absent. `update.py` uses subprocess solely for read-only `pip show` (line 74, mode detection). No-mutation invariant proven by four passing subprocess-guard tests: `test_check_for_update_no_mutation_when_drift_detected`, `test_check_for_update_no_mutation_when_current`, `test_cmd_update_no_flags_does_not_invoke_pip_or_git`, `test_update_command_detects_drift_without_mutating`. |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `notion_brain/update.py` | semver, mode detection, command gen, check, JSON/human format | ✓ VERIFIED | All 7 public functions present (parse_semver, compare_versions, detect_install_mode, build_upgrade_command, check_for_update, format_human, format_json); stdlib-only imports (json, re, subprocess, sys, pathlib, typing); imported and called by `__main__.py`. |
| `notion_brain/__main__.py` | thin `_cmd_update` wrapper, `--check`/`--json` flags | ✓ VERIFIED | `_cmd_update` (line 195) delegates to `update.check_for_update`; both flags declared on the `update` subparser (lines 94-103); dispatcher routes `update` (line 107) before the NOTION_API_KEY gate (line 113) so offline runs work. No mutating subprocess. |
| `tests/test_update.py` | offline unit coverage | ✓ VERIFIED | 26 tests; runs offline; all pass. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `update.py:check_for_update` | `bootstrap._find_latest_tag` | direct call inside try/except | ✓ WIRED | Signature `() -> str | None` unchanged at bootstrap.py:618 despite Phase 06 edits. Network error surfaced as `error` field, `latest=None`. |
| `update.py:build_upgrade_command` | mode string table | pure dispatch | ✓ WIRED | Exact strings verified inline for all modes. |
| `__main__.py:_cmd_update` | `update.check_for_update` | `from . import update as update_mod` | ✓ WIRED | Result drives print (`format_human`/`format_json`) + exit code. |
| `main` dispatcher | `_cmd_update` | `args.cmd == 'update'` (line 107) | ✓ WIRED | Routed before the API-key check so offline runs work. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `format_human`/`format_json` | `current` | `notion_brain.__version__` | Yes (1.0.3) | ✓ FLOWING |
| `format_human`/`format_json` | `latest` | `bootstrap._find_latest_tag()` (live GitHub tags API) | Yes (inline run returned 1.0.1) | ✓ FLOWING |
| `format_*` | `install_mode` | `detect_install_mode` via read-only `pip show` | Yes (safe `unknown` fallback) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Update + CLI-contract suites (offline) | `.venv/bin/python -m pytest tests/test_update.py tests/characterization/test_cli_contract.py -q -p no:cacheprovider` | 34 passed (1.63s) | ✓ PASS |
| SemVer ranking + per-mode commands + check payload | inline `parse_semver` / `build_upgrade_command` / `check_for_update` / `format_json` asserts | CONTRACT OK; current=1.0.3 latest=1.0.1 mode=unknown drift=False | ✓ PASS |
| No mutating literals / subprocess in `_cmd_update` path | grep of `__main__.py` | only a docstring mention at line 198; no subprocess import | ✓ PASS |
| No-mutation invariant (UPD-05) | subprocess-raise guard tests | 4 tests pass | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| UPD-01 | 05-01 | Detect drift, print installed vs latest | ✓ SATISFIED | Truth 1; REQUIREMENTS.md marks `[x]` / Phase 5 Complete |
| UPD-02 | 05-01 | Per-env copy-pasteable upgrade command | ✓ SATISFIED | Truth 2; REQUIREMENTS.md `[x]` |
| UPD-03 | 05-01 | Integer-tuple SemVer with pre-release ranking | ✓ SATISFIED | Truth 3; REQUIREMENTS.md `[x]` |
| UPD-04 | 05-01 | `--check` exit 0/2; `--json` payload | ✓ SATISFIED | Truth 4; REQUIREMENTS.md `[x]` |
| UPD-05 | 05-01 | Detect+instruct only, no mutation | ✓ SATISFIED | Truth 5; REQUIREMENTS.md `[x]` |

No orphaned requirements: REQUIREMENTS.md traceability table maps exactly UPD-01..05 to Phase 5, all claimed by plan 05-01's `requirements` frontmatter, and all now marked `[x]` / Complete (the earlier `[ ]` documentation lag noted in the prior report has since been reconciled).

### Prohibitions

| Prohibition | Status | Evidence |
| --- | --- | --- |
| No pip install / git pull mutation in `_cmd_update` / `check_for_update` | ✓ VERIFIED | No mutating subprocess anywhere in the path; enforced by 4 passing subprocess-guard tests. |
| Do not change `bootstrap._find_latest_tag` / `_check_for_update` signatures | ✓ VERIFIED | Both remain `() -> str | None` (bootstrap.py:618, :642) after Phase 06's edits. |
| No new third-party dependencies; stdlib only | ✓ VERIFIED | `update.py` imports only json, re, subprocess, sys, pathlib, typing. |

### Anti-Patterns Found

None. No TODO/FIXME/XXX/HACK/PLACEHOLDER markers in `update.py`, `__main__.py`, or `tests/test_update.py`.

### Phase 06 Regression Check

Commit a0c7390 added the `update_cache` module and rewired provider init (provider.py:105-108, 245) and `bootstrap.health_report` (bootstrap.py:670-677, CHK-04) to a stale-while-revalidate cache. These changes:
- Did NOT alter `bootstrap._find_latest_tag()` or `_check_for_update()` signatures (`() -> str | None`), the only bootstrap surface Phase 05 depends on.
- Touch a separate call path (`update_cache.load_cache` / `refresh`), not `notion_brain.update.check_for_update`.
- Both Phase 05 suites still pass (34 tests). No regression.

### Gaps Summary

No gaps. All five success criteria are observably met in the current codebase (HEAD 1039fc1) and exercised by passing offline tests (34 across the two suites), independent inline contract checks, and a live `check_for_update` call. UPD-05 (the no-mutation invariant) is behaviorally verified — not merely present — via four subprocess-guard tests. The `covered_digest` was regenerated against HEAD and now matches (`v2:sha256:a331a852...`, superseding the stale `v1:sha256:caba8dee...`).

**Noted deviation (non-blocking, unchanged from prior report):** bare `update` (no `--check`) runs the check and prints the full report, exiting 0/2 on drift, rather than the one-line notice the PLAN task described. This better satisfies ROADMAP SC1 (bare `update` prints both versions) and does not violate UPD-05. Codified by `test_update_command_detects_drift_without_mutating`.

---

_Verified: 2026-09-29_
_Verifier: Claude (gsd-verifier)_
