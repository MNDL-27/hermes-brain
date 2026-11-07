---
gsd_state_version: "1.0"
milestone: v1.2
milestone_name: Update UX & Tooling Polish
status: complete
last_updated: "2026-11-07T07:44:13.000Z"
last_activity: 2026-11-07
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 4
  completed_plans: 4
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-07)

**Core value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.
**Current focus:** v1.2 closeout complete; next is v1.3 Phase 9, then Phases 10-11, followed by v1.4 Phases 12-15.

## Current Position

Milestone: v1.2 — Update UX & Tooling Polish (complete 2026-11-07)
Phases: 7-8 (2/2 complete)
Plans: 4/4 complete
Next position: v1.3 Phase 9 — Retrieval Correctness & Local Read-Through Cache
Last activity: 2026-11-07 — v1.2 closeout recorded after canonical full-suite verification

## Execution Order (user-confirmed 2026-11-06)

v1.2 Phase 7 → Phase 8 → v1.3 Phase 9 → 10 → 11 → v1.4 Phase 12 → 13 → 14 → 15. No skipping.

## Baseline Test State (2026-11-06)

Full offline suite: **401 passed, 1 deselected** via `.venv/bin/python -m pytest -q` (project venv, Python 3.12).

v1.2 closeout observation (2026-11-07): **407 passed, 1 deselected, 1 warning in 7.77s** via `.venv/bin/python -m pytest -q`. The v1.2-only suite baseline is now isolated because the Phase 9-15 work was moved to branch `feature/metabolic-brain-v1.3-1.5` (commit `0c44a70`), while this branch (`c42ac35`) carries only v1.2. The three TEST-HANGS files complete in the full offline run; one existing network-marked test remains deselected.

⚠ Canonical test command is `.venv/bin/python -m pytest -q`. Do NOT use `uv run --no-sync pytest` on this host: `PYTHONPATH` points at the Hermes installs venv (Python 3.14) which carries a stale editable `notion_brain` snapshot (`plugin-sources/hermes-brain-*/notion_brain`); tests that run before any `sys.path.insert` import that stale copy, it wins the `sys.modules` cache, and 11 unrelated tests then fail with `AttributeError: module 'notion_brain.update' has no attribute 'detect_git_drift'`. Confirmed: same tree, same tests, 401/401 green under `.venv/bin/python -m pytest` with and without `PYTHONPATH` set.

The previous single failure (`test_database_schema_mismatch_detects_zombie_status_options`) is fixed: `_database_schema_matches` is now type-aware — `status` fields compare option-name sets with strict equality (zombie status options must force reset), `select`/`multi_select` accept a superset of user-added options. New test `test_database_schema_allows_user_added_select_options` covers the select-superset path.


## Performance Metrics

**Velocity (v1.1):**

- Total plans completed: 4
- Phases: 3 (4, 5, 6)
- Timeline: 2026-09-21 → 2026-10-07 (16 days)
- LOC: +1,522 / −121 across 12 source files
- New tests: 58 (test_packaging 4 + test_update 26 + test_update_cache 20 + 8 cli contract rewrite)

**Cumulative across milestones:**

- v1.0 + v1.1 = 6 phases, 7 plans, 25 requirements; offline suite audited 2026-11-06: 401 passed, 1 deselected (prior baseline 361)
- v1.2 = 2 phases, 4 plans, 5 requirements completed 2026-11-07; isolated v1.2-only suite baseline: 407 passed, 1 deselected (1 warning, 7.77s). Phase 9-15 work was moved to branch `feature/metabolic-brain-v1.3-1.5` (commit `0c44a70`); this branch (`c42ac35`) carries only v1.2.

## Accumulated Context

### Decisions

All milestone decisions logged in PROJECT.md Key Decisions table (v1.0 + v1.1 sections).

### Pending Todos

- One-time manual PyPI Trusted Publisher registration (owner + repo + `publish.yml` + environment `pypi`) must be done in the maintainer runbook before the first `v*` tag push

### Blockers/Concerns

None yet.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Update UX | UPD-06 — commit-level drift detection between formal tags | Completed | v1.1 close | v1.2 (2026-11-07) |
| Update UX | UPD-07 — update banner links to release notes URL | Completed | v1.1 close | v1.2 (2026-11-07) |
| Dev Tooling | TOOL-01 — optional pre-push git hook running `pytest -q` | Completed | v1.1 close | v1.2 (2026-11-07) |
| Dev Tooling | TOOL-02 — scheduled GitHub Action for `pre-commit autoupdate` | Completed | v1.1 close | v1.2 (2026-11-07) |
| Test Infra | TEST-HANGS — investigate 3 pre-existing test-suite hangs | Completed | v1.1 close | v1.2 (2026-11-07) |
| Retrieval | RET-01 — prefetch hydrates non-empty summary text | Queued | v1.2 | v1.3 |
| Cache | RET-02 — local SQLite read-through cache mirror (<5ms) | Queued | v1.2 | v1.3 |
| Budget | RET-03 — 800-token two-lane injection cap | Queued | v1.2 | v1.3 |
| Supersession | SUP-01 — subject_key schema + conflict detection | Queued | v1.2 | v1.3 |
| Supersession | SUP-02 — non-destructive active->superseded flip | Queued | v1.2 | v1.3 |
| Supersession | SUP-03 — audit timeline + recall-as-of | Queued | v1.2 | v1.3 |
| Adapter | ADAPT-01 — pluggable StorageAdapter protocol | Queued | v1.2 | v1.3 |
| Adapter | ADAPT-02 — NotionAdapter refactor (free tier) | Queued | v1.2 | v1.3 |
| Freemium | ADAPT-03 — license entitlement check / fallback | Queued | v1.2 | v1.3 |
| Freemium | ADAPT-04 — ObsidianVaultAdapter premium scaffold | Queued | v1.2 | v1.3 |

## Session Continuity

Last session: 2026-10-07T00:00:00Z
Stopped at: Milestone v1.1 archived
Resume file: n/a (awaiting `/gsd-new-milestone` to define next cycle)

## Operator Next Steps

- Run `/gsd-new-milestone` to start the next milestone cycle (questioning → research → requirements → roadmap)
- OR hand off with `/gsd-ship` (PR + review + merge prep)
- The first action in either path should be a `/clear` to drop the milestone-close context
