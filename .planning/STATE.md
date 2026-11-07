---
gsd_state_version: "1.0"
milestone: v1.4
milestone_name: Semantic Brain Layer
status: complete
last_updated: "2026-11-07T18:35:00.000Z"
last_activity: 2026-11-07
progress:
  total_phases: 15
  completed_phases: 15
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-07)

**Core value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.
**Current focus:** v1.3 (Phases 9-11) and v1.4 (Phases 12-15) shipped 2026-11-07; no active phase — next milestone cycle not yet defined.

## Current Position

Milestone: v1.4 — Semantic Brain Layer (complete 2026-11-07)
Phases: 9-15 shipped (v1.2 Phases 7-8 closed earlier the same day); roadmap total 15/15
Commits: v1.3 = 7b78b98 (Phase 9), 7ceaafb (Phase 10), 71e7122 (Phase 11); v1.4 = da6b1d4 (12), 700221c (13), c5e829e (14), 6208569 (15)
Next position: awaiting /gsd-new-milestone (v1.5 undefined)
Last activity: 2026-11-07 — v1.3/v1.4 closeout: per-phase commits split from WIP, ROADMAP/REQUIREMENTS marked, full gate green

## Execution Order (user-confirmed 2026-11-06)

v1.2 Phase 7 → Phase 8 → v1.3 Phase 9 → 10 → 11 → v1.4 Phase 12 → 13 → 14 → 15. No skipping.

## Baseline Test State (2026-11-06)

Full offline suite: **401 passed, 1 deselected** via `.venv/bin/python -m pytest -q` (project venv, Python 3.12).

v1.4 closeout observation (2026-11-07): **487 passed, 1 deselected, 1 warning in 5.80s** via `.venv/bin/python -m pytest -q`; ruff and mypy clean in the same run (verification, review, CI and merge remain separate observed states — no CI run for these commits yet).

v1.2 closeout observation (2026-11-07): **451 passed, 1 deselected, 1 warning in 5.41s** via `.venv/bin/python -m pytest -q`. This working tree includes v1.3/v1.4 implementation changes, so this count is a tree-wide observation and not a v1.2-only baseline. The three TEST-HANGS files complete in the full offline run; one existing network-marked test remains deselected.

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
- v1.2 = 2 phases, 4 plans, 5 requirements completed 2026-11-07; observed full-tree suite: 451 passed, 1 deselected (1 warning, 5.41s). The v1.2-only suite baseline was not isolated because v1.3/v1.4 implementation changes are present in this working tree.
- v1.3 + v1.4 = 7 phases (9-15), 21 requirements completed 2026-11-07; observed full-tree suite at closeout: 487 passed, 1 deselected, ruff + mypy clean. Fix cycle T-050..T-054 (PROV-01 source honesty, CAT-03 catalog-resolved retrieval + mypy, CERT-02 orchestrator-only certification, ANS-01 zero-coverage gate) landed as the final four per-phase commits.

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
| Retrieval | RET-01 — prefetch hydrates non-empty summary text | Completed | v1.2 close | v1.3 (2026-11-07) |
| Cache | RET-02 — local SQLite read-through cache mirror (<5ms) | Completed | v1.2 close | v1.3 (2026-11-07) |
| Budget | RET-03 — 800-token two-lane injection cap | Completed | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-01 — subject_key schema + conflict detection | Completed | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-02 — non-destructive active->superseded flip | Completed | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-03 — audit timeline + recall-as-of | Completed | v1.2 close | v1.3 (2026-11-07) |
| Adapter | ADAPT-01 — pluggable StorageAdapter protocol | Completed | v1.2 close | v1.3 (2026-11-07) |
| Adapter | ADAPT-02 — NotionAdapter refactor (free tier) | Completed | v1.2 close | v1.3 (2026-11-07) |
| Freemium | ADAPT-03 — license entitlement check / fallback | Completed | v1.2 close | v1.3 (2026-11-07) |
| Freemium | ADAPT-04 — ObsidianVaultAdapter premium scaffold | Completed | v1.2 close | v1.3 (2026-11-07) |
| Retrieval | RET-03 — 800-token two-lane injection cap | Completed | v1.2 close | v1.3 (2026-11-07) |
| Semantic | CAT-01..03 — provider-neutral catalog + storage-ref resolution | Completed | v1.3 close | v1.4 (2026-11-07) |
| Certification | CERT-01..03 — inferred/certified truth + orchestrator-only promote | Completed | v1.3 close | v1.4 (2026-11-07) |
| Provenance | PROV-01..03 — provenance block, supersedes edge, graph traverse | Completed | v1.3 close | v1.4 (2026-11-07) |
| Answerability | ANS-01/02 — zero-coverage gate + contradiction surfacing | Completed | v1.3 close | v1.4 (2026-11-07) |

## Session Continuity

Last session: 2026-11-07
Stopped at: v1.3/v1.4 closeout recorded (Phases 9-15 shipped, planning docs marked)
Resume file: n/a (awaiting `/gsd-new-milestone` to define next cycle)

## Operator Next Steps

- Run `/gsd-new-milestone` to start the next milestone cycle (questioning → research → requirements → roadmap)
- OR hand off with `/gsd-ship` (PR + review + merge prep)
- The first action in either path should be a `/clear` to drop the milestone-close context
