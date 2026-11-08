---
gsd_state_version: "1.0"
milestone: v1.3
milestone_name: Brain Architecture & Freemium Foundation
status: executing
current_phase: 9
current_phase_name: Retrieval Correctness & Local Read-Through Cache
last_updated: "2026-11-08T22:01:43Z"
last_activity: 2026-11-09
progress:
  total_phases: 15
  completed_phases: 8
  percent: 53
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-09)

**Core value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.
**Current focus:** Phase 9 gap closure within the approved v1.3 → v1.4 sequence. The GSD audit found code gaps and missing original phase closure evidence. Semantic follow-up fixes are committed in `fb7ec04`; the v1.2 prerequisite is integrated and the verified baseline is pushed as `24ce18b`. v1.5 remains undefined.

## Current Position

Milestone: v1.3 — Brain Architecture & Freemium Foundation (gap closure)
Phase: 9 of 15 — Retrieval Correctness & Local Read-Through Cache
Status: Executing checked gap-closure plan 09-02 for RET-01/02/03
Next position: `/gsd-execute-phase 9 --gaps-only`; see [milestone audit](v1.4-MILESTONE-AUDIT.md)
Last activity: 2026-11-09 — verification reopened Phases 9–15; current automated baseline is green but does not prove all approved requirements

Phases 1–8 retain their prior closeout history. The 8/15 progress count carries that historical status; none of Phases 9–15 has complete original GSD SUMMARY/VERIFICATION evidence. Their implementations exist, but the old 15/15 completion claim is superseded.

Implementation history: v1.3 `7b78b98`, `7ceaafb`, `71e7122`; v1.4 `da6b1d4`, `700221c`, `c5e829e`, `6208569`; semantic review fixes `fb7ec04`. Commit existence, automated verification, push, merge and release are separate observations. Prerequisite merge and feature-branch push: observed at `24ce18b`. Merge to main/release: not performed.

## Execution Order (user-confirmed 2026-11-06)

v1.2 Phase 7 → Phase 8 → v1.3 Phase 9 → 10 → 11 → v1.4 Phase 12 → 13 → 14 → 15. No skipping.

## Verification Baselines and Historical Observations

Current verification (2026-11-09): **519 passed, 1 deselected in 7.17s**, Ruff clean, mypy clean across 52 source files. The run used the project virtualenv through `uv` with `UV_NO_SYNC=1` and `PYTHONPATH` unset. Code fixes are committed in `fb7ec04`; current phase gaps remain open. See the [audit](v1.4-MILESTONE-AUDIT.md), which supersedes the earlier [review snapshot](reviews/v1.4-review.md).

Full offline suite: **401 passed, 1 deselected** via `.venv/bin/python -m pytest -q` (project venv, Python 3.12).

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
- Historical 2026-11-07 v1.3/v1.4 report claimed 7 phases and 21 requirements complete after 487 passing tests. The 2026-11-09 audit supersedes that claim: 8 requirements have concrete gaps; all 7 phases lack original GSD closure evidence. The earlier implementation commits remain valid history.

## Accumulated Context

### Decisions

All milestone decisions logged in PROJECT.md Key Decisions table (v1.0 + v1.1 sections).

### Pending Todos

- One-time manual PyPI Trusted Publisher registration (owner + repo + `publish.yml` + environment `pypi`) must be done in the maintainer runbook before the first `v*` tag push

### Blockers/Concerns

- Phase 9: cold Notion reads do not populate the SQLite cache; fallback can include superseded rows; disk context and contradiction output bypass the total injection budget.
- Later approved work: background subject-key inference and same-title history (Phase 10), adapter routing/runtime selection (Phase 11), certification failure isolation (Phase 13), and cached/prompt provenance (Phase 14).
- Original GSD SUMMARY/VERIFICATION artifacts for Phases 9–15 are missing. Reconcile from actual evidence; do not infer completion from checkboxes or suite counts.
- The merge at `24ce18b` incorporates v1.2 follow-ups through `752fc51`, including the executable pre-push hook. Remote feature-branch SHA was independently checked after push.
- The external Hermes host must collect user approval and supply per-call certification confirmation. This package exposes the boundary, not that UI.

## Deferred Items

Earlier carryover history is retained below. For v1.3/v1.4, statuses reflect the 2026-11-09 audit rather than the superseded closeout report:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Update UX | UPD-06 — commit-level drift detection between formal tags | Completed | v1.1 close | v1.2 (2026-11-07) |
| Update UX | UPD-07 — update banner links to release notes URL | Completed | v1.1 close | v1.2 (2026-11-07) |
| Dev Tooling | TOOL-01 — optional pre-push git hook running `pytest -q` | Completed | v1.1 close | v1.2 (2026-11-07) |
| Dev Tooling | TOOL-02 — scheduled GitHub Action for `pre-commit autoupdate` | Completed | v1.1 close | v1.2 (2026-11-07) |
| Test Infra | TEST-HANGS — investigate 3 pre-existing test-suite hangs | Completed | v1.1 close | v1.2 (2026-11-07) |
| Retrieval | RET-01 — prefetch hydrates non-empty summary text | Implementation observed; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Cache | RET-02 — local SQLite read-through cache mirror (<5ms) | Gaps found; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Budget | RET-03 — 800-token two-lane injection cap | Gaps found; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-01 — subject_key schema + conflict detection | Gaps found; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-02 — non-destructive active->superseded flip | Gaps found; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Supersession | SUP-03 — audit timeline + recall-as-of | Implementation observed; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Adapter | ADAPT-01 — pluggable StorageAdapter protocol | Implementation observed; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Adapter | ADAPT-02 — NotionAdapter refactor (free tier) | Gaps found; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Freemium | ADAPT-03 — license entitlement check / fallback | Gaps found; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Freemium | ADAPT-04 — ObsidianVaultAdapter premium scaffold | Implementation observed; closure unverified | v1.2 close | v1.3 (2026-11-07) |
| Semantic | CAT-01..03 — provider-neutral catalog + storage-ref resolution | Implementation observed; closure unverified | v1.3 close | v1.4 (2026-11-07) |
| Certification | CERT-01..03 — inferred/certified truth + orchestrator-only promote | Gaps found; closure unverified | v1.3 close | v1.4 (2026-11-07) |
| Provenance | PROV-01..03 — provenance block, supersedes edge, graph traverse | Gaps found; closure unverified | v1.3 close | v1.4 (2026-11-07) |
| Answerability | ANS-01/02 — zero-coverage gate + contradiction surfacing | Implementation observed; closure unverified | v1.3 close | v1.4 (2026-11-07) |

## Session Continuity

Last session: 2026-11-09
Stopped at: GSD audit recorded; baseline pushed at `24ce18b`; plan 09-02 checked and Phase 9 gap closure executing
Resume file: `.planning/phases/09-retrieval-correctness-local-cache/09-VERIFICATION.md`

## Operator Next Steps

- Complete prerequisite integration and the authorized push, recording observed results.
- Run `/gsd-plan-phase 9 --gaps`, then implement and verify the RET-02/RET-03 repairs.
- Continue the already-approved phase order after Phase 9 passes; keep later code gaps and missing closure evidence visible.
- Define v1.5 only after its scope is supplied; no new milestone is created by this repair work.

## Prerequisite integration

The v1.2-only branch recorded **407 passed, 1 deselected** in its isolated baseline. Follow-ups `c42ac35`, `9af9d7e`, and `752fc51` are integrated here; the v1.2 archive retains that branch history. Planning conflicts preserve this branch's later audit and Phase 9 gap-closure state.

## Active gap plan

[09-02-PLAN.md](phases/09-retrieval-correctness-local-cache/09-02-PLAN.md) passed independent GSD plan checking with no blockers. Execution follows the verified 519-test baseline; later phase gaps remain open.
