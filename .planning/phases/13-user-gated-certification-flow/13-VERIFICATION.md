---
phase: 13-user-gated-certification-flow
verified: 2026-11-12
status: gaps_found
source_snapshot: 61a6247
score: "CERT-01 and CERT-02 demonstrated by existing regressions; CERT-03 has one failure-isolation gap"
fingerprint: "Phase 13 gap report: certification requires exact per-call confirmation and agent writes default to inferred, but _tool_certify performs the Truth flip, optional predecessor metadata, catalog edge and cache mirror under one outer try. A recoverable auxiliary failure after the accepted Truth write returns an error, skips the predecessor cache update and can leave later inferred peers active. Full suite 570 passed, 1 deselected; ruff and mypy clean. No live Notion mutation performed."
gaps:
  - id: CERT-03
    truth: "A certification whose Truth write is accepted completes predecessor supersession and cache/graph bookkeeping independently of recoverable auxiliary failures."
    reason: "All certification follow-up work shares one outer try. A catalog load/save failure, a rejected optional Superseded Page ID update, or a cache mirror failure jumps to the error return after predecessor status flips may already have occurred."
    artifacts:
      - notion_brain/provider.py
    missing:
      - "Isolate the optional Superseded Page ID write, catalog edge write and predecessor cache mirror per peer."
      - "Continue processing the remaining active inferred peers after a recoverable auxiliary failure."
      - "Return Certified once the Truth flip is accepted; report auxiliary failures only through redacted diagnostics."
      - "Preserve the existing boundary that a rejected Truth write returns an error and performs no predecessor transitions."
deferred: []
---

# Phase 13 verification record

CERT-01 and CERT-02 are demonstrated by the existing certification suite. CERT-03 is partially implemented and has one concrete failure-isolation gap, matching the 2026-11-09 milestone audit.

## Verification scope

- Existing certification suite: `tests/test_certification.py` covers inferred defaults, exact per-call confirmation, schema non-exposure, argument/initialization non-authorization, one-call confirmation scope, certified-first ranking, schema evolution and certified-predecessor protection.
- Full repository gate at `61a6247`: **570 passed, 1 deselected**; ruff and mypy clean.
- No live Notion call or external confirmation UI was required.

## CERT-03 gap evidence

`notion_brain/provider.py::_tool_certify` (around lines 1429–1485):

1. The Truth update is accepted with `store.update_page(page_id, {"Truth": "certified"})`.
2. Predecessor processing then runs inside the same outer `try`:
   - `store.update_page(..., {"Status": Superseded})`
   - optional `Superseded Page ID` write
   - catalog load, `add_relation("supersedes")`, `graph.save`
   - `brain_cache.upsert_active(..., status="Superseded")`
3. Any exception in the metadata/catalog/cache work jumps to the outer handler, logs `Certification update failed`, and returns `"Error: certification update failed"`.
4. The already-flipped predecessor is left `active` in the local cache, and the `for older in rows` loop stops, so later inferred peers are never superseded.

The ordinary supersession path already isolates catalog and cache work; certification does not. The fix is to apply the same per-concern isolation without changing the certification permission model.

## Required closure

- Separate the accepted Truth write from optional bookkeeping; an accepted certification must not be reported as failed because of provenance/cache work.
- Continue the peer loop after recoverable auxiliary failures.
- Keep a rejected Truth write fatal, with no predecessor transitions.
- Keep all diagnostics and outbound values redacted.

## Scope fences

- CERT-01 (truth status + certified-first ranking) and CERT-02 (exact per-call confirmation) are already demonstrated; do not redesign them.
- Phase 14 provenance persistence and Phase 15 answerability are out of scope.
- No new dependency, schema change or live Notion mutation is required.
