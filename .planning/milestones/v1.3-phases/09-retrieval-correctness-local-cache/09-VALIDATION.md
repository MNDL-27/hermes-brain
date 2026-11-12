---
phase: "09"
slug: retrieval-correctness-local-cache
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-09"
source_snapshot: "45c8ca2"
requirements: [RET-01, RET-02, RET-03]
---

# Phase 9 validation

This records completed validation for gap-closure plan `09-02`, after the audit found no original Phase 9 validation artifact. It does not claim a historical sampling record that was not observed.

## Infrastructure and commands

| Item | Value |
| --- | --- |
| Framework/configuration | pytest; `pyproject.toml`; default suite excludes the `network` marker |
| Task 1 | `.venv/bin/python -m pytest tests/test_prefetch_gap_closure.py tests/test_prefetch_hydration.py tests/test_brain_cache.py -q` |
| Task 2 | `.venv/bin/python -m pytest tests/test_prefetch_gap_closure.py tests/test_injection.py tests/test_answerability.py -q` |
| Combined independent check | `.venv/bin/python -m pytest tests/test_prefetch_gap_closure.py tests/test_prefetch_hydration.py tests/test_brain_cache.py tests/test_injection.py tests/test_answerability.py -q` |
| Full gate on this host | `env -u PYTHONPATH UV_NO_SYNC=1 PATH="/home/protik/.hermes/tools/uv-0.13.5-linux-x64:$PATH" uv run pytest` |
| Static gates | `.venv/bin/ruff check .`; `.venv/bin/mypy .`; `git -c core.whitespace=cr-at-eol diff --check` |

Combined independent check: **48 passed in 0.28s** before the final permission-error regression was added. After its fix, this independent named check passed **1 test in 0.13s**:

```sh
.venv/bin/python -m pytest tests/test_prefetch_gap_closure.py::test_unreadable_cache_does_not_block_cold_recall -q
```

Root's final full suite includes all these tests: **532 passed, 1 deselected in 6.39s**. Ruff, mypy (53 source files), and CRLF-aware whitespace check passed. Observed targeted feedback is below one second; the recorded full gate is below ten seconds.

## Per-task verification map

| Task | Wave | Requirements | Coverage | Failure detected | Result |
| --- | --- | --- | --- | --- | --- |
| 09-02-01: Populate cache from cold reads | 1 | RET-01, RET-02 | Gap-closure, hydration and cache tests | Missing offline content; repeated remote calls; empty/missing cache confusion; partial commits; inactive rows; overwritten accepted writes; failed usable recall after cache/body errors; unredacted stored/output text | GREEN |
| 09-02-02: Apply budget at every prefetch boundary | 1 | RET-03 | Gap-closure, injection and answerability tests | Disk/conflict output above lane/total caps; missing conflict excerpts; nondeterministic output; truncated background-sync arguments | GREEN |

Both tasks have explicit runnable automated commands in their plan `<verify>` fields. Tests exist and run without watch mode, network credentials or new dependencies. No Wave 0 infrastructure dependency is missing.

## Requirement-to-behavior evidence

| Behavior | Repository regression |
| --- | --- |
| Available body text and existing short output | `test_prefetch_renders_hydrated_body`; existing hydration suite |
| Cold hydrated content persists offline with redaction | `test_cold_hydrated_read_is_available_to_new_offline_provider` |
| Empty success is a hit; failed remote read is a miss | `test_successful_empty_read_is_cached_but_failed_read_is_not` |
| Schema-only/rolled-back initialization is a miss | `test_uninitialized_cache_file_is_a_miss`; `test_read_population_is_atomic_and_failed_initialization_remains_miss` |
| Inactive remote rows never hydrate/cache/render | `test_remote_inactive_rows_are_excluded_before_hydration_and_caching` |
| Empty cached content does not trigger body calls | `test_cached_empty_content_never_fetches_body`; `test_hydration_failure_still_creates_offline_cache_hit` |
| Cache failures preserve remote recall | `test_cache_population_failure_keeps_cold_recall`; `test_unreadable_cache_does_not_block_cold_recall` |
| Accepted writes survive population | `test_read_population_preserves_concurrent_accepted_write`; `test_empty_read_population_preserves_existing_accepted_rows` |
| Disk budget retains full sync payload | `test_disk_context_budget_does_not_truncate_background_sync_payload` |
| Contradictions retain signal and both excerpts within budget | `test_conflict_notices_share_budget_and_keep_both_value_snippets` |
| Normal facts/pinned kinds/overflow remain deterministic | `test_lane_budgets_and_combined_hard_cap`; `test_overflow_drops_from_lane_end_in_order`; remaining injection tests |

## Independent boundary probes

The verifier also ran a bounded Python probe using `TemporaryDirectory`, SQLite triggers, `unittest.mock.patch` and `Thread`/`Event`. All six groups passed:

1. Abort initialization-marker insertion after inserting rows: no rows or marker survive, and the cache remains a miss.
2. Remove the marker from a populated legacy cache: accepted content remains readable.
3. Attempt population into schema 999: version stays unchanged and no memory table is created.
4. Pause cold fetching, accept a newer same-ID row and a separate row, finish population: both accepted writes and the remote-only row are recalled by a fresh offline provider.
5. Supply Content, Summary-only and duplicate empty-body rows: precedence is retained, empty body fetch occurs once, and the later provider needs no remote calls.
6. Render six empty/single-lane/mixed/boundary disk cases with mixed whitespace: each lane stays within 400 and total within 800, including the marker, deterministically.

The failed `fb7ec04` probes (1,505-unit disk output, 2,094-unit conflicts, missing read-through cache, returned Superseded row) remain recorded in [09-VERIFICATION.md](09-VERIFICATION.md). Root also observed the permission-error regression fail before applying the read-open fallback fix.

## Performance evidence

The committed-source [09-BENCHMARK.json](09-BENCHMARK.json) records 120 fresh providers over ten hydrated rows: **median 1.012 ms, p95 1.349 ms, zero warm query/body calls**. Initial population used one query and ten body reads; warm output was asserted non-empty. Both observed statistics meet the `<5ms` success criterion and `<2ms` narrative target on this host.

This measures existing-cache prefetch, excluding provider initialization and missing-cache remote retrieval. Performance measurement is separate from correctness tests to avoid timing-dependent CI failures.

## Sampling and sign-off

- [x] Both implementation tasks have runnable automated verification commands.
- [x] No sequence of three implementation tasks lacks automated verification; this plan contains two tasks.
- [x] All referenced tests and fixtures exist; no missing Wave 0 dependency remains.
- [x] No watch mode or live Notion operation is needed for correctness checks.
- [x] Targeted checks, independent probes and final repository gates are green.
- [x] Observed test-command feedback latency is below ten seconds.
- [x] Six must-haves and RET-01/RET-02/RET-03 have current evidence.

No manual-only check remains for this contract. Current validation is complete for `45c8ca2`; it does not mark missing historical execution records or Phase 10–15 gaps complete.

**Validated:** 2026-11-09 (Asia/Kolkata), independent verifier plus root's final gates and committed-source benchmark.
