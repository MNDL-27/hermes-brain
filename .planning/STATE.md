---
gsd_state_version: "1.0"
milestone: v1.4
milestone_name: Semantic Brain Layer
status: Awaiting milestone closeout
stopped_at: v1.3 archived; v1.4 phases 12-15 verified
last_updated: "2026-11-13T00:00:00Z"
last_activity: 2026-11-13
last_activity_desc: Milestone v1.3 completed and archived; v1.4 closeout pending
state_head: c1261af56110f0c76b85d51d97ac2881ec0789e6
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 4
  completed_plans: 4
  percent: 100
current_phase: 15
current_phase_name: Answerability Gate & Contradiction Detection
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-09)

**Core value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.
**Current focus:** v1.4 is complete and verified; milestone closeout is pending. v1.3 shipped and archived on 2026-11-13. Merge/tag/release and v1.5 scope remain separate decisions.

## Current Position

Phase: Milestone v1.3 complete; v1.4 closeout pending
Plan: —
Status: Awaiting v1.4 milestone closeout
Last activity: 2026-11-13 — Milestone v1.3 completed and archived; v1.4 phases 12-15 verified

## Execution Order (user-confirmed 2026-11-06)

v1.2 Phase 7 → Phase 8 → v1.3 Phase 9 → 10 → 11 → v1.4 Phase 12 → 13 → 14 → 15. No skipping.

## Verification Baselines and Historical Observations

Current verification (2026-11-12): **582 passed, 1 deselected in 5.67s**, Ruff clean, mypy clean (`notion_brain`). Milestone audit: **passed** for Phases 9–15 (21/21 requirements, 7/7 phases, 11/11 integration flows, Nyquist 7/7 compliant); 181 cross-phase tests pass. See [v1.3-MILESTONE-AUDIT.md](v1.3-MILESTONE-AUDIT.md) and [v1.4-MILESTONE-AUDIT.md](v1.4-MILESTONE-AUDIT.md).

Phase 11 verification (2026-11-12): **568 passed, 1 deselected in 5.59s**; seven new provider-wiring regressions closed ADAPT-02/03 for read and selection paths. See the [Phase 11 verification](phases/11-storage-adapters/11-VERIFICATION.md) and [summary](phases/11-storage-adapters/11-01-SUMMARY.md).

Phase 10 verification (2026-11-09): **561 passed, 1 deselected in 6.15s**, 3/3 scoped contracts, 121 targeted supersession tests. Phase 9 verification (2026-11-09): **532 passed, 1 deselected in 6.39s**; cached prefetch on committed `45c8ca2` measured 1.012ms median / 1.349ms p95 over 120 samples with zero warm Notion calls. The initial [audit](v1.4-MILESTONE-AUDIT.md) records the original gaps and a follow-up below.

GSD integrity remediation (2026-11-12): Phases 7 and 8 gained retrospective SUMMARY and VERIFICATION artifacts reconstructed from committed behavior; `verify phase-completeness` passes for Phases 04–15; `validate health` is **healthy** and `validate consistency` reports 0 warnings. Verification digests were refreshed after later shared-source changes, and dispatch briefs now live under `.planning/milestones/dispatches/`.

Historical offline baseline (2026-11-06): **401 passed, 1 deselected** via `.venv/bin/python -m pytest -q` (project venv, Python 3.12).

Historical v1.4 closeout report (2026-11-07, completion claim superseded by the current audit): **487 passed, 1 deselected, 1 warning in 5.80s** via `.venv/bin/python -m pytest -q`; ruff and mypy clean in the same run (verification, review, CI and merge remain separate observed states — no CI run for these commits yet).

v1.2 closeout observation (2026-11-07): **451 passed, 1 deselected, 1 warning in 5.41s** via `.venv/bin/python -m pytest -q`. This working tree includes v1.3/v1.4 implementation changes, so this count is a tree-wide observation and not a v1.2-only baseline. The three TEST-HANGS files complete in the full offline run; one existing network-marked test remains deselected.

Use `uv run pytest` with the project virtualenv selected; on this host unset `PYTHONPATH` and use `UV_NO_SYNC=1`. The equivalent direct command is `.venv/bin/python -m pytest -q`. Historical environment diagnosis: `PYTHONPATH` points at the Hermes installs venv (Python 3.14) which carries a stale editable `notion_brain` snapshot (`plugin-sources/hermes-brain-*/notion_brain`); tests that run before any `sys.path.insert` import that stale copy, it wins the `sys.modules` cache, and 11 unrelated tests then fail with `AttributeError: module 'notion_brain.update' has no attribute 'detect_git_drift'`. Confirmed: same tree, same tests, 401/401 green under `.venv/bin/python -m pytest` with and without `PYTHONPATH` set.

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
- Historical 2026-11-07 v1.3/v1.4 report claimed 7 phases and 21 requirements complete after 487 passing tests. The initial 2026-11-09 audit superseded that claim; subsequent gap plans closed every partial requirement. Current state: v1.3 shipped 2026-11-13 (3 phases, 10 requirements); v1.4 phases 12–15 verified (11 requirements); full suite 582 passed, 1 deselected.

## Accumulated Context

### Decisions

All milestone decisions logged in PROJECT.md Key Decisions table (v1.0 + v1.1 sections).

### Pending Todos

- One-time manual PyPI Trusted Publisher registration (owner + repo + `publish.yml` + environment `pypi`) must be done in the maintainer runbook before the first `v*` tag push

### Blockers/Concerns

- No open roadmap code gaps remain; all 15 phases have current closure evidence.
- Milestone closeout is not a release: merge to `main`, tagging, PyPI Trusted Publisher registration and v1.5 scope remain separate decisions.
- The merge at `24ce18b` incorporates v1.2 follow-ups through `752fc51`, including the executable pre-push hook. Remote feature-branch SHA was independently checked after push.
- The external Hermes host must collect user approval and supply per-call certification confirmation. This package exposes the boundary, not that UI.

## Deferred Items

Earlier carryover history is retained below. For v1.3/v1.4, statuses reflect the current verification records; the 2026-11-09 audit remains the historical snapshot that reopened them:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Update UX | UPD-06 — commit-level drift detection between formal tags | Completed | v1.1 close | v1.2 (2026-11-07) |
| Update UX | UPD-07 — update banner links to release notes URL | Completed | v1.1 close | v1.2 (2026-11-07) |
| Dev Tooling | TOOL-01 — optional pre-push git hook running `pytest -q` | Completed | v1.1 close | v1.2 (2026-11-07) |
| Dev Tooling | TOOL-02 — scheduled GitHub Action for `pre-commit autoupdate` | Completed | v1.1 close | v1.2 (2026-11-07) |
| Test Infra | TEST-HANGS — investigate 3 pre-existing test-suite hangs | Completed | v1.1 close | v1.2 (2026-11-07) |
| Retrieval | RET-01 — prefetch hydrates non-empty summary text | Verified 09-02 (2026-11-09) | v1.2 close | v1.3 (2026-11-07) |
| Cache | RET-02 — local SQLite read-through cache mirror (<5ms) | Verified 09-02 (2026-11-09) | v1.2 close | v1.3 (2026-11-07) |
| Budget | RET-03 — 800-token two-lane injection cap | Verified 09-02 (2026-11-09) | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-01 — subject_key schema + conflict detection | Verified 10-02 (2026-11-09) | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-02 — non-destructive active->superseded flip | Verified 10-02 (2026-11-09) | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-03 — audit timeline + recall-as-of | Verified 10-02 (2026-11-09) | v1.2 close | v1.3 (2026-11-07) |
| Adapter | ADAPT-01 — pluggable StorageAdapter protocol | Verified 11-01 (2026-11-12) | v1.2 close | v1.3 (2026-11-07) |
| Adapter | ADAPT-02 — NotionAdapter refactor (free tier) | Verified for read paths 11-01; write path ceiling documented | v1.2 close | v1.3 (2026-11-07) |
| Freemium | ADAPT-03 — license entitlement check / fallback | Verified 11-01 (2026-11-12) | v1.2 close | v1.3 (2026-11-07) |
| Freemium | ADAPT-04 — ObsidianVaultAdapter premium scaffold | Verified 11-01 (2026-11-12) | v1.2 close | v1.3 (2026-11-07) |
| Semantic | CAT-01..03 — provider-neutral catalog + storage-ref resolution | Verified 12-01 (2026-11-12) | v1.3 close | v1.4 (2026-11-07) |
| Certification | CERT-01..03 — inferred/certified truth + orchestrator-only promote | Verified 13-01 (2026-11-12) | v1.3 close | v1.4 (2026-11-07) |
| Provenance | PROV-01..03 — provenance block, supersedes edge, graph traverse | Verified 14-01 (2026-11-12) | v1.3 close | v1.4 (2026-11-07) |
| Answerability | ANS-01/02 — zero-coverage gate + contradiction surfacing | Verified 15-01 (2026-11-12) | v1.3 close | v1.4 (2026-11-07) |

## Session Continuity

Last session: 2026-11-13
Stopped at: v1.3 completed and archived; v1.4 phases 12–15 verified and awaiting milestone closeout
Resume file: `.planning/v1.4-MILESTONE-AUDIT.md`

## Operator Next Steps

- Run `/gsd-complete-milestone v1.4` after confirming the v1.4 audit; this archives Phases 12–15 and removes the milestone-scoped requirements file.
- Decide separately on merge to `main`, tagging and release; PyPI Trusted Publisher registration remains a one-time manual step.
- Define v1.5 only after its scope is supplied.


## Prerequisite integration

The v1.2-only branch recorded **407 passed, 1 deselected** in its isolated baseline. Follow-ups `c42ac35`, `9af9d7e`, and `752fc51` are integrated here; the v1.2 archive retains that branch history. Planning conflicts preserve this branch's later audit and Phase 9 gap-closure state.

## Completed gap plans

- [09-02-PLAN.md](milestones/v1.3-phases/09-retrieval-correctness-local-cache/09-02-PLAN.md) completed in `45c8ca2`; fingerprinted by [09-VERIFICATION.md](milestones/v1.3-phases/09-retrieval-correctness-local-cache/09-VERIFICATION.md).
- [10-02-PLAN.md](milestones/v1.3-phases/10-event-driven-supersession/10-02-PLAN.md) completed in `f9c589b`; fingerprinted by [10-VERIFICATION.md](milestones/v1.3-phases/10-event-driven-supersession/10-VERIFICATION.md).
- [11-01-PLAN.md](milestones/v1.3-phases/11-storage-adapters/11-01-PLAN.md) completed in `61a6247`; fingerprinted by [11-VERIFICATION.md](milestones/v1.3-phases/11-storage-adapters/11-VERIFICATION.md).
- [12-01-PLAN.md](phases/12-semantic-catalog/12-01-PLAN.md) completed 2026-11-12 as verification plus Obsidian catalog-ref recall on `61a6247`; fingerprinted by [12-VERIFICATION.md](phases/12-semantic-catalog/12-VERIFICATION.md).
- [13-01-PLAN.md](phases/13-user-gated-certification-flow/13-01-PLAN.md) completed 2026-11-12 in `e1d55c6`; fingerprinted by [13-VERIFICATION.md](phases/13-user-gated-certification-flow/13-VERIFICATION.md).
- [14-01-PLAN.md](phases/14-graph-provenance-relational-recall/14-01-PLAN.md) completed 2026-11-12 in `b868c39`; fingerprinted by [14-VERIFICATION.md](phases/14-graph-provenance-relational-recall/14-VERIFICATION.md).
- [15-01-PLAN.md](phases/15-answerability-gate-contradiction-detection/15-01-PLAN.md) completed 2026-11-12 in `cf12265`; fingerprinted by [15-VERIFICATION.md](phases/15-answerability-gate-contradiction-detection/15-VERIFICATION.md).
