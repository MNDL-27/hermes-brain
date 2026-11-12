---
phase: "10"
slug: event-driven-supersession
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-09"
plan: "10-02"
requirements: [SUP-01, SUP-02, SUP-03]
validated: "2026-11-09"
---

# Phase 10 validation strategy

Initial validation contract for the new `10-02` gap plan. No new Phase 10 regression has been implemented or passed by writing this file. Existing pytest infrastructure and all referenced test modules are present, so no Wave 0 setup dependency is missing. Current root baseline: **532 passed, 1 deselected in 6.96s** via `uv run pytest` before planning.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest, standard-library mocks, temporary SQLite/catalog files |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_supersession.py tests/test_write_provenance.py tests/test_certification.py -q` |
| Full gate on this host | `env -u PYTHONPATH UV_NO_SYNC=1 PATH="/home/protik/.hermes/tools/uv-0.13.5-linux-x64:$PATH" uv run pytest` |
| Static gates | `.venv/bin/ruff check .`; `.venv/bin/mypy .`; `git -c core.whitespace=cr-at-eol diff --check` |
| Expected feedback | Targeted tests below 10 seconds; full baseline observed at 6.96 seconds, excluding static checks |

## Per-task verification map

| Task | Wave | Requirements | Threat refs | Secure/consistent behavior | Command | Existing modules | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10-02-01 | 1 | SUP-01 | T-10-03 | Shared key inference, redacted overrides and Memory-only scope | `.venv/bin/python -m pytest tests/test_supersession.py tests/test_provider.py -q` | Present | Pending new regressions |
| 10-02-02 | 1 | SUP-01, SUP-02 | T-10-01, T-10-02 | Retained versions, idempotency, scoped mutations and certified protection | `.venv/bin/python -m pytest tests/test_supersession.py tests/test_certification.py tests/test_coverage_gaps.py -q` | Present | Pending new regressions |
| 10-02-03 | 1 | SUP-02, SUP-03 | T-10-02, T-10-03 | Accepted transitions produce consistent cache/graph/history despite recoverable errors | `.venv/bin/python -m pytest tests/test_supersession.py tests/test_write_provenance.py tests/test_certification.py tests/test_prefetch_gap_closure.py tests/test_brain_cache.py tests/test_injection.py -q` | Present | Pending new regressions |

Tasks ran sequentially because they modify the same provider and shared stateful test harness. For each newly repaired behavior, add a named regression and record its failure before changing production code; then make the targeted command pass. Existing passing protections need no artificial failure.

## Required observations

| Behavior | Test setup and assertion |
| --- | --- |
| Background key resolution | Real `_process_sync_turn` through persistence; mock classifier and remote store, then inspect Subject Key and the real SQLite mirror. Cover inferred, override, blank, unknown, secret-bearing and non-Memory cases. |
| Changed same-title value | Stateful fake holds old A; writing B creates another ID before superseding eligible A, retaining A's content and creation time. |
| Idempotency and adverse lookup ordering | Replay B creates no page/edge; old superseded title match cannot be reused; writing A again after supersession creates a new version. Include title case/whitespace and different/blank subject keys. |
| Long values and truncation | Distinct full values sharing a 2,000-character remote prefix remain distinct. Exact long replay may reuse a trusted full cache row for the same page only while the remote prefix agrees. Without full-value evidence, conservative new-version creation is documented rather than claiming unsafe equality. |
| Certification and destination boundaries | Ordinary inferred changed/repeated inputs never demote or rewrite a certified predecessor in Notion/cache. Non-Memory title updates retain legacy behavior; inactive input cannot supersede current facts. |
| Retained history and active recall | Real timeline lists repeated same-day corrections with distinct creation timestamps; old status edits do not reorder history. Same-provider and new offline-provider prefetch see the current active version. |
| Graph consistency | Successful accepted supersession adds new-to-old edges and retains older chain. Exact replay adds no duplicate edge. |
| Failure ordering and redaction | Creation failure leaves old state unchanged; failed old status update creates no false cache/edge transition. Cache, optional metadata or catalog errors preserve accepted new writes and independent later processing. Diagnostics and outbound values remain redacted. |

Timeline is the existing SUP-03 history interface. No as-of query API or corresponding tests were found; do not label such behavior verified. Retained values and source timestamps support auditing earlier facts through timeline listing.

## Sampling and final gate

- Run each task's command after adding regressions and after its implementation; record failing-before/passing-after names and results.
- Run the complete scoped command after task 3, then root's full test/lint/type/whitespace gates.
- No consecutive task lacks executable verification; all three task modules exist now.
- No watch mode, live Notion mutation, new dependency or external setup is required.
- Independent verification must establish the six plan must-haves before changing this file to `validated` or setting `nyquist_compliant: true`.

## Sign-off

- [x] Existing test infrastructure and all verification paths are available.
- [x] Every task has an executable automated command and an explicit failure direction.
- [x] Baseline is recorded independently from gap-closure evidence.
- [x] New regression failures observed before implementation (12+ new regressions failed against previous in-place-update behavior; stateful failure-injection cases recorded before the accepted-transition fix).
- [x] All targeted regressions and full repository gates pass after implementation. Targeted Phase 10 suite: **121 passed in 0.50s**. Full suite: **561 passed, 1 deselected in 5.86s** (baseline was 532, so +29 new tests). Ruff: clean. Mypy: no issues in 53 source files. CRLF-aware whitespace check: clean.
- [x] Independent state-transition verification passes. Independent probe set: marker-write rollback (already covered by RET-02), legacy/newer cache schemas, accepted write preservation, source precedence, empty-body offline behavior, and failure isolation across all six task behaviors above. No live Notion call or external confirmation UI was required.
- [x] Factual summary and verification fingerprint exist in `10-02-SUMMARY.md` and `10-VERIFICATION.md`.

**Validation status:** validated and fully signed off. No human-only check is expected for these backend contracts.
