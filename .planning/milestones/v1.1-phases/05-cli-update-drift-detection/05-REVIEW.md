---
phase: 05-cli-update-drift-detection
reviewed: 2026-09-26T00:00:00Z
depth: deep
files_reviewed: 4
files_reviewed_list:
  - notion_brain/update.py
  - notion_brain/__main__.py
  - tests/test_update.py
  - tests/characterization/test_cli_contract.py
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-09-26T00:00:00Z
**Depth:** deep
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 05 "CLI Update Drift Detection" change set: the new `notion_brain/update.py`
module, the slimmed `_cmd_update` wrapper in `notion_brain/__main__.py`, and the two test files.
Cross-checked the out-of-scope collaborator `bootstrap._find_latest_tag` (bootstrap.py:618-639)
because the in-scope code's correctness and security depend on its return/exception contract.

Headline assessment against the priority focus areas:

1. **SemVer parsing/comparison (UPD-03): correct.** The `(major, minor, patch, pre_slot)` encoding
   with `pre_slot = (float("inf"),)` for releases and `(rank, n)` for pre-releases gives the required
   orderings: `1.10.0 > 1.9.0` (integer tuple, not lexical) and `1.1.0 > 1.1.0b1` (inf outranks any
   pre-release rank). Verified by tracing tuple comparison element by element.
2. **Detect-only guarantee (UPD-05): upheld.** No path in `update.py` or `_cmd_update` runs
   `pip install`, `git pull/checkout/fetch`, `os.system`, `eval`, or any mutating subprocess.
   `detect_install_mode` shells out only to read-only `pip show` (with a 10s timeout);
   `build_upgrade_command` returns strings that are printed, never executed. Confirmed no BLOCKER here.
3. **Security (secret redaction / offline safety): satisfied.** The GitHub tag fetch is unauthenticated
   (no token in the request), and `check_for_update` records only `type(exc).__name__` in `error`,
   never a raw message — so no token can leak through error/log/output paths. `_find_latest_tag` uses a
   3.0s timeout and swallows failures; `pip show` uses a 10s timeout. No crash on network failure.
4. **Exit-code contract (UPD-04): correct.** `_cmd_update` returns `2` when `drift` is truthy, else `0`;
   `--json` emits the full 7-key payload via `format_json`. Verified against the CLI tests.
5. **Py 3.11–3.13 / conventions: clean.** `from __future__ import annotations`, built-in generics,
   snake_case throughout, no deprecated APIs.

Two WARNING-level robustness/correctness issues and five INFO items follow. Nothing blocks shipping,
consistent with this review being advisory.

## Warnings

### WR-01: Non-SemVer upstream tag yields a bogus (and potentially unsafe) upgrade instruction

**File:** `notion_brain/update.py:157-172`
**Issue:** When `_find_latest_tag()` returns a string that is not a clean `x.y.z[abc|rc]N` version,
`compare_versions(latest, current_ver)` raises `ValueError` and the fallback sets
`result["drift"] = latest != current_ver` (line 162). This is reachable in practice:
`bootstrap._find_latest_tag` does `raw_name.lstrip("v")` (bootstrap.py:636), so a repo tag such as
`nightly`, `v2` (→ `"2"`), or `2024-01` survives as a non-parseable string and, being unequal to
`"1.0.3"`, is treated as available drift. The unvalidated `latest` is then interpolated verbatim into
a copy-pasteable shell command and a release URL:

- `build_upgrade_command(mode, "nightly")` → `pip install --upgrade hermes-brain==nightly`
- `release_url` → `.../releases/tag/vnightly`

Because the repo owner controls tags this is low severity, but a malformed or hostile tag (e.g.
`1.0.0; rm -rf ~`) would be surfaced to the user as an instruction to run. Detect-only prevents
execution, so the blast radius is a misleading/dangerous *displayed* command, not a mutation.
**Fix:** Validate `latest` is parseable before emitting an upgrade command/URL; treat unparseable tags
as "cannot determine latest" rather than drift.
```python
if latest:
    result["latest"] = latest
    try:
        result["drift"] = compare_versions(latest, current_ver) > 0
    except ValueError:
        # Upstream tag isn't SemVer — don't guess drift or emit an install command.
        result["drift"] = False
        result["error"] = "unparseable latest tag"
```

### WR-02: `check_for_update` network-error diagnostics are effectively unreachable; offline runs never explain "latest: unknown"

**File:** `notion_brain/update.py:151-155` (depends on `bootstrap.py:637-639`)
**Issue:** The `try/except` around `bootstrap._find_latest_tag()` sets
`result["error"] = f"network: {type(exc).__name__}"` on failure. But `_find_latest_tag` already wraps
its entire body in `except Exception: pass` and returns `None`, so it does not propagate network errors.
In real offline/failed-fetch usage the except branch here never fires: `latest` comes back `None` and
`error` stays `None`, so `format_human` prints `latest: unknown` with no reason (the `(error)` suffix at
line 184-185 is dead in production). The feature that would tell a user *why* the check failed silently
never works; the passing test (`test_check_for_update_handles_network_failure`) only succeeds because it
patches `_find_latest_tag` to raise directly, bypassing bootstrap's own swallow.
**Fix:** Either have `bootstrap._find_latest_tag` distinguish "no tags" from "fetch failed" (e.g. return
a sentinel / raise a narrow error the caller maps to `error`), or drop the misleading `error` plumbing
and document that offline simply reports `latest: unknown`. Minimum: don't advertise diagnostics that
can't surface.

## Info

### IN-01: `check_only` parameter is unused; `--check` is a no-op and the `--json` help is misleading

**File:** `notion_brain/__main__.py:195-211` (flags at `94-103`)
**Issue:** `_cmd_update(check_only=..., json_output=...)` never references `check_only`. Since the
command is intentionally always detect-only, `--check` changes nothing — which is behaviorally correct
but the parameter is dead, and the `--json` help string "implies --check" suggests a mode toggle that
does not exist. This invites future confusion.
**Fix:** Drop the `check_only` parameter (and the `--check` argument, or keep `--check` purely as a
documented alias for default behavior) and reword the `--json` help to "Emit machine-readable JSON".

### IN-02: Redundant conditionals in `detect_install_mode`

**File:** `notion_brain/update.py:99-106`
**Issue:** Three redundancies: (a) line 99 `"/uv/" in loc or "/.cache/uv/" in loc` — `/.cache/uv/`
always contains the substring `/uv/`, so the second clause is unreachable; (b) line 101
`loc.startswith(home + "/.local/lib/") or "/.local/lib/" in loc` — the `startswith` case is a strict
subset of the `in` case; (c) lines 104-106 the `if loc.endswith("/site-packages")...` branch and the
final `return "pip_venv"` both return `"pip_venv"`, so the `if` is dead.
**Fix:** Collapse to `if "/uv/" in loc: return "uv"`, `if "/.local/lib/" in loc: return "pip_user"`,
and a single trailing `return "pip_venv"`.

### IN-03: `parse_semver` return type annotated as bare `tuple`

**File:** `notion_brain/update.py:32`
**Issue:** `-> tuple` is unparameterized; project conventions call for parameterized built-in generics.
The value is heterogeneous (`int, int, int, tuple`).
**Fix:** Annotate as `-> tuple[int, int, int, tuple[float | int, ...]]` (or introduce a small type
alias) for clarity and mypy precision.

### IN-04: Docstring encoding example has a typo

**File:** `notion_brain/update.py:41`
**Issue:** The example reads `` `1.10.0` -> `(10, 10, 0, inf)` `` — the major should be `1`, i.e.
`(1, 10, 0, (inf,))`. Misleads readers about the encoding.
**Fix:** Correct the example to `(1, 10, 0, (inf,))`.

### IN-05: Tautological assertion weakens the network-failure test

**File:** `tests/test_update.py:167`
**Issue:** The final assertion `... or result.get("error") is not None` makes the whole `or` chain pass
whenever `error` is non-`None`, regardless of its content, so it does not actually verify the error is
network-related. Combined with WR-02, this test gives false confidence in the error-reporting path.
**Fix:** Assert the concrete contract, e.g. `assert result["error"] is not None and "network" in result["error"].lower()`.

---

_Reviewed: 2026-09-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
