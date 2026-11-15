---
phase: 07-update-ux-commit-level-drift-release-notes-link
verified: 2026-11-12
status: passed
source_snapshot: working tree on top of 61a6247
score: "4/4 success criteria verified; UPD-06 and UPD-07 closed"
fingerprint: "Phase 7 retrospective verification: commit-level drift, cached banner fields, canonical release-notes URL and non-mutating behavior all demonstrated. 64 targeted update/update-cache tests pass; full suite 570 passed, 1 deselected. Commits 4c7afdf and edf7259."
gaps: []
closed:
  - truth: A git-clone install on main behind origin/main reports the behind count even when __version__ matches.
    requirements: [UPD-06]
    resolution: detect_git_drift reads git rev-list --left-right --count HEAD...origin/main and skips non-main branches; check_for_update exposes behind_commits/ahead_commits and drift_type.
    evidence: notion_brain/update.py:169-234; tests/test_update.py (64-test Phase 7 suite)
  - truth: The cached auto-update check carries the same commit-drift signal with offline tolerance.
    requirements: [UPD-06]
    resolution: update_cache persists drift_type, behind_commits, ahead_commits and release_url with neutral defaults; refresh failures degrade silently.
    evidence: notion_brain/update_cache.py:159-162; tests/test_update_cache.py
  - truth: The banner prints the canonical release-notes URL derived from the resolved tag.
    requirements: [UPD-07]
    resolution: release_url is built as https://github.com/MNDL-27/hermes-brain/releases/tag/v{latest}; human and JSON formatting surface it.
    evidence: notion_brain/update.py:280; tests/test_update.py
  - truth: The inspection path never mutates the environment.
    requirements: [UPD-06]
    resolution: detect/check paths only run read-only git commands and HTTP GETs; _cmd_update returns exit 0 for commit-only drift and 2 for version/both drift.
    evidence: notion_brain/__main__.py:211; tests/characterization/test_cli_contract.py
---

# Phase 7 verification record

Phase 7 is verified retrospectively from the committed behavior. The original execution did not leave SUMMARY or VERIFICATION artifacts; this record reconstructs them from the implementation, tests and commit history without changing code.

## Verification scope

- Targeted suite: **64 passed in 0.42s** across `tests/test_update.py` and `tests/test_update_cache.py`.
- Full repository gate: **570 passed, 1 deselected**; ruff and mypy clean on the current tree.
- Implementation commits: `4c7afdf` (UPD-06/07 detection and URL) and `edf7259` (cache persistence).
- No live network or repository mutation was required.

## Criterion evidence

1. **Commit drift (UPD-06)** — `detect_git_drift` guards on branch `main`, parses local `rev-list` counts, and falls back to the GitHub compare API only when the local ref is missing. Tests cover local parsing, API fallback and non-main skipping.
2. **Cached signal** — `update_cache` stores the drift fields and keeps older cache files readable through defaults; offline/rate-limited refresh leaves previous values intact.
3. **Release URL (UPD-07)** — `release_url` is derived from the resolved latest tag and surfaces in both human and JSON output; the CLI contract test pins the exit codes and output shape.
4. **No mutation** — the command performs read-only inspection only; no fetch, pull, install or environment change is executed.

## Scope note

This is a retrospective closure record. It does not claim the original plan ran through the GSD executor; it verifies that the committed behavior satisfies the roadmap criteria.

## Remaining scope

Phase 8 and the remaining phases are verified separately.
