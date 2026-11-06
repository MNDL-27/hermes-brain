---
gsd_state_version: "1.0"
milestone: v1.2
milestone_name: Update UX & Tooling Polish
status: planning
last_updated: "2026-11-06T10:53:19.680Z"
last_activity: 2026-11-06
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-07)

**Core value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.
**Current focus:** v1.2 Phase 7 execution (UPD-06/07 commit drift) — then Phase 8, then v1.3 Phases 9-11, then v1.4 Phases 12-15.

## Current Position

Phase: 7 — Update UX: Commit-Level Drift + Release-Notes Link
Plan: 07-01 (in flight via fleet dispatch T-012)
Status: Executing
Last activity: 2026-11-06 — v1.4 milestone artifacts written; Phase 7 dispatched to fleet

## Execution Order (user-confirmed 2026-11-06)

v1.2 Phase 7 → Phase 8 → v1.3 Phase 9 → 10 → 11 → v1.4 Phase 12 → 13 → 14 → 15. No skipping.

## Baseline Test State (2026-11-06)

Full offline suite: **401 passed, 1 deselected** via `.venv/bin/python -m pytest -q` (project venv, Python 3.12).

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

## Accumulated Context

### Decisions

All milestone decisions logged in PROJECT.md Key Decisions table (v1.0 + v1.1 sections).

### Pending Todos

- One-time manual PyPI Trusted Publisher registration (owner + repo + `publish.yml` + environment `pypi`) must be done in the maintainer runbook before the first `v*` tag push
- Pre-existing test-suite hangs in `test_coverage_gaps`, `test_migration_privacy_blockers`, `test_provider` (unrelated to v1.1, deferred as TEST-HANGS in PROJECT.md)

### Blockers/Concerns

None yet.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Update UX | UPD-06 — commit-level drift detection between formal tags | Deferred | v1.1 close | Next |
| Update UX | UPD-07 — update banner links to release notes URL | Deferred | v1.1 close | Next |
| Dev Tooling | TOOL-01 — optional pre-push git hook running `pytest -q` | Deferred | v1.1 close | Next |
| Dev Tooling | TOOL-02 — scheduled GitHub Action for `pre-commit autoupdate` | Deferred | v1.1 close | Next |
| Test Infra | TEST-HANGS — investigate 3 pre-existing test-suite hangs | Deferred | v1.1 close | Next |
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
