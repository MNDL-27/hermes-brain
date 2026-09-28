---
status: complete
phase: 05-cli-update-drift-detection
source:
  - .planning/phases/05-cli-update-drift-detection/05-01-SUMMARY.md
started: 2026-09-24T10:55:00Z
updated: 2026-09-24T10:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. `notion_brain/update.py` exists with public surface
expected: Module exposes `parse_semver`, `compare_versions`, `detect_install_mode`, `build_upgrade_command`, `check_for_update`, `format_human`, `format_json`.
result: pass
evidence: All seven functions present; import smoke `from notion_brain import update as u` succeeds.

### 2. UPD-03: Integer-tuple SemVer ranking
expected: `parse_semver('1.10.0') > parse_semver('1.9.0')`.
result: pass
evidence: `tests/test_update.py::test_semver_integer_tuple_ranking` passes.

### 3. UPD-03: Release ranks above pre-release
expected: `parse_semver('1.1.0') > parse_semver('1.1.0b1')`, `> '1.1.0a1'`, `> '1.1.0rc1'`.
result: pass
evidence: `test_semver_release_above_prerelease` passes.

### 4. UPD-03: Pre-release intra-class ordering
expected: `1.0.0a1 < 1.0.0b1 < 1.0.0rc1 < 1.0.0` and `rc1 < rc2`.
result: pass
evidence: `test_semver_prerelease_ordering` passes.

### 5. UPD-03: SemVer parser rejects garbage
expected: `parse_semver('not-a-version')` and `parse_semver('1.0')` raise `ValueError`.
result: pass
evidence: `test_semver_rejects_garbage` passes.

### 6. UPD-03: compare_versions reflexive + antisymmetric
expected: `compare_versions(x,x)==0`; `compare_versions(a,b)==-compare_versions(b,a)`.
result: pass
evidence: `test_compare_versions_reflexive_and_antisymmetric` passes.

### 7. UPD-02: uv upgrade command
expected: `build_upgrade_command('uv', '1.2.3') == 'uv pip install --upgrade hermes-brain==1.2.3'`.
result: pass
evidence: `test_build_upgrade_command_uv` passes.

### 8. UPD-02: pip venv upgrade command
expected: `build_upgrade_command('pip_venv', '1.2.3') == 'pip install --upgrade hermes-brain==1.2.3'`.
result: pass
evidence: `test_build_upgrade_command_pip_venv` passes.

### 9. UPD-02: pip user upgrade command
expected: `build_upgrade_command('pip_user', '1.2.3') == 'pip install --user --upgrade hermes-brain==1.2.3'`.
result: pass
evidence: `test_build_upgrade_command_pip_user` passes.

### 10. UPD-02: git clone upgrade command
expected: Command starts with `git` and contains `v<target>`.
result: pass
evidence: `test_build_upgrade_command_git_clone` passes with `repo_dir=/tmp/repo`.

### 11. detect_install_mode — uv
expected: Returns `'uv'` when `pip show` Location is under `.cache/uv/` or contains `/uv/`.
result: pass
evidence: `test_detect_install_mode_uv_when_location_under_uv_cache` passes.

### 12. detect_install_mode — pip_user
expected: Returns `'pip_user'` when Location is under `~/.local/lib/`.
result: pass
evidence: `test_detect_install_mode_pip_user_when_location_under_local` passes.

### 13. detect_install_mode — git_clone
expected: Returns `'git_clone'` when editable project location matches repo_dir.
result: pass
evidence: `test_detect_install_mode_git_clone_when_editable_matches_repo` passes.

### 14. detect_install_mode — pip_venv default
expected: Returns `'pip_venv'` for any site-packages path.
result: pass
evidence: `test_detect_install_mode_pip_venv_default` passes.

### 15. detect_install_mode — unknown on failure
expected: Returns `'unknown'` when `pip show` raises; never propagates.
result: pass
evidence: `test_detect_install_mode_unknown_when_pip_show_fails` passes.

### 16. UPD-05: check_for_update never mutates (drift path)
expected: Drift-detected call does not invoke any `subprocess.run` for pip or git.
result: pass
evidence: `test_check_for_update_no_mutation_when_drift_detected` patches `subprocess.run` to raise on any call; result returned without raising.

### 17. UPD-05: check_for_update never mutates (current path)
expected: Same guarantee on the no-drift path.
result: pass
evidence: `test_check_for_update_no_mutation_when_current` passes.

### 18. check_for_update swallows network errors
expected: ConnectionError from `_find_latest_tag` does not propagate; `result['latest'] is None`, `result['drift'] is False`.
result: pass
evidence: `test_check_for_update_handles_network_failure` passes.

### 19. UPD-04: --check exits 0 when current
expected: `python -m notion_brain update --check` exits 0 when current; output contains "up to date".
result: pass
evidence: `test_cmd_update_check_exits_0_when_current` passes; live CLI smoke shows exit 0 with `latest: 1.0.1 (up to date)`.

### 20. UPD-04: --check exits 2 when drift
expected: Same command exits 2 when drift; output contains "UPDATE AVAILABLE".
result: pass
evidence: `test_cmd_update_check_exits_2_when_drift` passes.

### 21. UPD-04: --check --json emits parseable JSON, exits 0/2
expected: Drift case prints JSON parseable by `json.loads`; exit 2. Current case exits 0.
result: pass
evidence: `test_cmd_update_check_json_exits_2_and_prints_json` and `test_cmd_update_check_json_exits_0_when_current` pass; live CLI returns `{"current":"1.0.3","drift":false,...}`.

### 22. UPD-05: Bare `update` is detect+instruct only
expected: `python -m notion_brain update` exits 2 on drift, prints human report, no mutating subprocess.
result: pass
evidence: `tests/characterization/test_cli_contract.py::test_update_command_detects_drift_without_mutating` passes; asserts `mutating_calls == []`.

### 23. No mutating subprocess calls remain in `__main__.py`
expected: `__main__.py` has zero `subprocess.run`/`subprocess.call`/`subprocess.Popen` references and no `_git_pull_and_install`/`_checkout_tag_and_install`/`_reinstall`.
result: pass
evidence: Inline verifier confirmed; live `python -m notion_brain update --check` shows no pip install or git activity.

### 24. format_human includes drift line + upgrade command + release URL
expected: Human output contains installed version, latest version, drift marker, upgrade command, release URL.
result: pass
evidence: `test_format_human_includes_drift_line_when_drift` passes.

### 25. format_json round-trips through json.loads
expected: `json.loads(format_json(d)) == d` for an arbitrary sample dict.
result: pass
evidence: `test_format_json_is_parseable_and_round_trips` passes.

### 26. Lint clean (ruff)
expected: `uv run ruff check notion_brain tests` reports no errors.
result: pass
evidence: `All checks passed!`.

### 27. Type-check clean (mypy)
expected: `uv run mypy notion_brain tests` reports no errors.
result: pass
evidence: `Success: no issues found in 30 source files`.

### 28. Live CLI smoke (offline-tolerant)
expected: `python -m notion_brain update --check --json` returns valid JSON; `--check` exits 0 or 2.
result: pass
evidence: Live run returned `{"current":"1.0.3","drift":false,"error":null,"install_mode":"unknown","latest":"1.0.1","release_url":"","upgrade_command":""}` and `installed: 1.0.3 / latest: 1.0.1 (up to date) / install: unknown`.

## Summary

total: 28
passed: 28
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

(none)
