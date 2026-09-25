---
phase: 06-cached-non-blocking-auto-update-check
fixed_at: 2026-09-25T19:14:38.388Z
review_path: .planning/phases/06-cached-non-blocking-auto-update-check/06-REVIEW.md
fix_scope: critical_warning
iteration: 1
findings_in_scope: 5
fixed: 1
skipped: 4
status: all_fixed
---

# Phase 06: Code Review Fix Report

**Fixed at:** 2026-09-25T19:14:38.388Z
**Source review:** `.planning/phases/06-cached-non-blocking-auto-update-check/06-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 total (1 Warning actionable under `fix_scope=critical_warning`; 4 Info out of scope)
- Fixed: 1 (WR-01)
- Skipped: 4 (IN-01..IN-04, Info severity / out of `fix_scope`)
- Status: `all_fixed` — every actionable (critical/warning) finding is fixed; the 4 Info findings are documented and intentionally skipped.

## Fixed Issues

### WR-01 — `refresh()` wall-clock "timeout" discards late results; docstring overstates the guarantee

**Disposition:** fixed
**Files modified:** `notion_brain/update_cache.py`
**Commit:** `ad42bce`

**Applied fix (cleanest of the review's options — combine (a) + (b)):**
- Aligned the default `timeout` in `refresh()` from `2.5` to `3.0` to match the `3.0 s` `urlopen` cap in `bootstrap._find_latest_tag()` (`bootstrap.py:632`). This directly removes consequence #2 from the review: a check that succeeds in 2.5–3.0 s is no longer silently discarded (returns `None` with no cache write) and will now be kept and cached.
- Reworded the `refresh()` docstring so it states accurately that `timeout` is a wall-clock **discard** threshold — the guard runs *after* `check_for_update` returns, so it cannot pre-empt a slow call; and that the hard wall-time bound is the caller's `urlopen` timeout (3.0 s in `bootstrap._find_latest_tag`).
- Reworded the module-level CHK-05 line, which made the same "we additionally cap the whole refresh at `timeout` seconds" overstatement, to stay consistent with the `refresh()` docstring.

The change is minimal: no redesign of the refresh flow, no new public API, no new dependencies. The non-blocking contract (worker-thread-only network, `queue.Queue` dispatch, `redact_secrets` on all log paths) is untouched.

**Tests:** No test update required. All three `refresh()` tests in `tests/test_update_cache.py` mock `update_mod.check_for_update` to return/raise immediately with **no** timeout assertions, so raising the default `2.5 → 3.0` changes no asserted behavior. (Confirmed by reading the full file; no assertion references the `2.5` literal or a discard-at-timeout path.)

**Verification (ran in the MAIN CHECKOUT, not an isolated worktree — see "Worktree note" below):**
- `uv run --no-sync ruff check notion_brain tests` → All checks passed
- `uv run --no-sync mypy notion_brain tests` → Success: no issues found in 32 source files
- `uv run --no-sync pytest tests/test_update_cache.py tests/test_update.py -q` → 46 passed in 1.51s

**Commit note:** `notion_brain/update_cache.py` is a **new, previously untracked** Phase 06 module, so the atomic commit records the full module (167 insertions) — the WR-01 edit cannot be isolated from the rest of the file's initial introduction because the file had no prior committed version. I verified this is a clean tree: at HEAD (`336a647`) neither `bootstrap.py` nor `provider.py` references `update_cache`, and the module's only dependency on `update.py` is lazy (inside `refresh()`), so committing it standalone leaves an importable tree. The sibling `update.py` (also untracked, not the subject of WR-01) was deliberately left uncommitted. A pre-commit `ruff format` hook reflowed one pre-existing multi-line `logger.warning(...)` call in the module to a single line as part of this commit (first commit of the file through the repo's format hook); the second commit pass passed all hooks (`ruff format`, `ruff`, `mypy`, etc.).

## Skipped Issues

### IN-01 — `bootstrap._check_for_update()` is dead production code after CHK-04
**Disposition:** skipped (out of `fix_scope` — Info severity)
**Reason:** `fix_scope=critical_warning` excludes Info findings; deleting the function plus its three tests in `tests/test_bootstrap_schema.py` is a follow-up cleanup task, not a review fix in this run.

### IN-02 — Network failure is cached as a 24 h "no update" negative cache
**Disposition:** skipped (out of `fix_scope` — Info severity)
**Reason:** Info severity; the review states the 24 h negative-cache behavior is acceptable-by-design (benign — the next init after TTL re-checks), so no critical/warning action is required. Deciding whether to add a docstring note or skip `save_cache` on error is a design call for the owner.

### IN-03 — `detect_install_mode` uv heuristic misses uv-created `.venv` installs
**Disposition:** skipped (out of `fix_scope` — Info severity)
**Reason:** Info severity; the review itself notes the impact is cosmetic (wrong tooling hint; both commands work) and suggests leaving as-is unless an accurate `uv` hint matters.

### IN-04 — `save_cache` except-branch performs a redundant double `os.close(fd)`
**Disposition:** skipped (out of `fix_scope` — Info severity)
**Reason:** Info severity; the review confirms the code is "Correct today" — a clarity-only nit with no behavior change, not a critical/warning fix.

## Worktree note

Worktree isolation was **not** used for this run. The WR-01 target file (`notion_brain/update_cache.py`) and its Phase 06 siblings are **untracked** in the main checkout — they are not part of any commit, so an isolated worktree checked out from the branch tip (`336a647`) would not contain them to edit. The fix was therefore applied and committed directly in the main checkout (equivalent to the `workflow.use_worktrees=false` path: `wt="."`, no temp branch, no recovery sentinel, no cleanup tail). All verification gates ran in the main checkout; the numbers above are reproducible from that tree.

---

_Fixed: 2026-09-25T19:14:38.388Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
