---
gsd_state_version: "1.0"
milestone: v1.3
milestone_name: Brain Architecture & Freemium Foundation
status: planning
current_phase: 14
current_phase_name: Graph Provenance & Relational Recall
last_updated: "2026-11-12T00:00:00Z"
last_activity: 2026-11-12
progress:
  total_phases: 15
  completed_phases: 14
  percent: 93
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-09)

**Core value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.
**Current focus:** Phase 14 is verified with PROV-01 provenance continuity closed. Phase 15 answerability closure is the final roadmap phase. v1.5 remains undefined.

## Current Position

Milestone: v1.3 — Brain Architecture & Freemium Foundation (gap closure)
Phase: 14 of 15 — Graph Provenance & Relational Recall
Status: Verified 3/3 success criteria; provenance now survives the cache and reaches prefetch/timeline
Next position: `/gsd-plan-phase 15 --gaps`; see [Phase 14 verification](phases/14-graph-provenance-relational-recall/14-VERIFICATION.md)
Last activity: 2026-11-12 — added cache provenance continuity, conflict-safe backfill, prefetch suffix and timeline block; full suite 579 passed

Phases 1–9 retain their historical closeout status. Phases 10–14 are verified with current SUMMARY/VERIFICATION evidence, giving 14/15 phases complete in this roadmap. Phase 15 still needs its own closure evidence; the original 15/15 claim remains superseded.

Implementation history: v1.3 `7b78b98`, `7ceaafb`, `71e7122`; v1.4 `da6b1d4`, `700221c`, `c5e829e`, `6208569`; semantic review fixes `fb7ec04`. Commit existence, automated verification, push, merge and release are separate observations. Prerequisite merge and feature-branch push: observed at `24ce18b`. Merge to main/release: not performed.

## Execution Order (user-confirmed 2026-11-06)

v1.2 Phase 7 → Phase 8 → v1.3 Phase 9 → 10 → 11 → v1.4 Phase 12 → 13 → 14 → 15. No skipping.

## Verification Baselines and Historical Observations

Current verification (2026-11-12): **579 passed, 1 deselected in 5.77s**, Ruff clean, mypy clean (`notion_brain`). Phase 14 is verified: PROV-01 provenance continuity closed with six new regressions; 23 cache/provenance tests and 46 scoped tests pass. See the [Phase 14 verification](phases/14-graph-provenance-relational-recall/14-VERIFICATION.md).

Phase 11 verification (2026-11-12): **568 passed, 1 deselected in 5.59s**; seven new provider-wiring regressions closed ADAPT-02/03 for read and selection paths. See the [Phase 11 verification](phases/11-storage-adapters/11-VERIFICATION.md) and [summary](phases/11-storage-adapters/11-01-SUMMARY.md).

Phase 10 verification (2026-11-09): **561 passed, 1 deselected in 6.15s**, 3/3 scoped contracts, 121 targeted supersession tests. Phase 9 verification (2026-11-09): **532 passed, 1 deselected in 6.39s**; cached prefetch on committed `45c8ca2` measured 1.012ms median / 1.349ms p95 over 120 samples with zero warm Notion calls. The initial [audit](v1.4-MILESTONE-AUDIT.md) records the original gaps and a follow-up below.

GSD integrity remediation (2026-11-12): Phases 7 and 8 gained retrospective SUMMARY and VERIFICATION artifacts reconstructed from committed behavior; `verify phase-completeness` passes for Phases 04–12; `validate health` is **healthy** and `validate consistency` reports 0 warnings. Phase 9's verification digest was refreshed after later provider changes, and dispatch briefs now live under `.planning/milestones/dispatches/`.

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
- Historical 2026-11-07 v1.3/v1.4 report claimed 7 phases and 21 requirements complete after 487 passing tests. The initial 2026-11-09 audit superseded that claim: 8 requirements had concrete gaps and all 7 phases lacked original GSD closure evidence. Phase 9's subsequent verified repair closes RET-02/03, leaving 6 concrete requirement gaps and Phases 10–15 awaiting closure evidence. The earlier implementation commits remain valid history.

## Accumulated Context

### Decisions

All milestone decisions logged in PROJECT.md Key Decisions table (v1.0 + v1.1 sections).

### Pending Todos

- One-time manual PyPI Trusted Publisher registration (owner + repo + `publish.yml` + environment `pypi`) must be done in the maintainer runbook before the first `v*` tag push

### Blockers/Concerns

- Later approved work: Phase 15 answerability closure evidence.
- Phases 9–14 current closures are verified. Phase 14 closed the provenance-continuity residual. Phase 15 still lacks complete GSD closure evidence; reconcile from actual behavior rather than suite counts.
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
| Answerability | ANS-01/02 — zero-coverage gate + contradiction surfacing | Implementation observed; closure unverified | v1.3 close | v1.4 (2026-11-07) |

## Session Continuity

Last session: 2026-11-12
Stopped at: Phase 14 verified with PROV-01 provenance continuity closed; Phase 15 answerability closure is next
Resume file: `.planning/phases/14-graph-provenance-relational-recall/14-VERIFICATION.md`

## Operator Next Steps

- Review and commit the Phase 14 implementation (`notion_brain/brain_cache.py`, `notion_brain/provider.py`, tests) and closure artifacts.
- Run `/gsd-plan-phase 15 --gaps` for answerability closure: ANS-01/02 are implemented; verify the zero-coverage gate, contradiction payload and bounded notice.
- After Phase 15, run the final milestone integrity check and decide on merge/release separately.
- Define v1.5 only after its scope is supplied; no new milestone is created by this repair work.

## Prerequisite integration

The v1.2-only branch recorded **407 passed, 1 deselected** in its isolated baseline. Follow-ups `c42ac35`, `9af9d7e`, and `752fc51` are integrated here; the v1.2 archive retains that branch history. Planning conflicts preserve this branch's later audit and Phase 9 gap-closure state.

## Completed gap plans

- [09-02-PLAN.md](phases/09-retrieval-correctness-local-cache/09-02-PLAN.md) completed in `45c8ca2`; fingerprinted by [09-VERIFICATION.md](phases/09-retrieval-correctness-local-cache/09-VERIFICATION.md).
- [10-02-PLAN.md](phases/10-event-driven-supersession/10-02-PLAN.md) completed in `f9c589b`; fingerprinted by [10-VERIFICATION.md](phases/10-event-driven-supersession/10-VERIFICATION.md).
- [11-01-PLAN.md](phases/11-storage-adapters/11-01-PLAN.md) completed in `61a6247`; fingerprinted by [11-VERIFICATION.md](phases/11-storage-adapters/11-VERIFICATION.md).
- [12-01-PLAN.md](phases/12-semantic-catalog/12-01-PLAN.md) completed 2026-11-12 as verification plus Obsidian catalog-ref recall on `61a6247`; fingerprinted by [12-VERIFICATION.md](phases/12-semantic-catalog/12-VERIFICATION.md).
- [13-01-PLAN.md](phases/13-user-gated-certification-flow/13-01-PLAN.md) completed 2026-11-12 in `e1d55c6`; fingerprinted by [13-VERIFICATION.md](phases/13-user-gated-certification-flow/13-VERIFICATION.md).
- [14-01-PLAN.md](phases/14-graph-provenance-relational-recall/14-01-PLAN.md) completed 2026-11-12 (working tree on top of `e1d55c6`); fingerprinted by [14-VERIFICATION.md](phases/14-graph-provenance-relational-recall/14-VERIFICATION.md).
