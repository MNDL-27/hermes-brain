---
phase: 09-retrieval-correctness-local-cache
verified: "2026-11-09"
status: gaps_found
score: "1/3 scoped requirements demonstrated"
source_snapshot: "fb7ec04"
re_verification: false
overrides_applied: 0
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/dispatch-phase09.md
  - .planning/phases/09-retrieval-correctness-local-cache/09-01-WORK-ORDER.md
  - notion_brain/provider.py
  - notion_brain/brain_cache.py
  - notion_brain/injection.py
  - tests/test_prefetch_hydration.py
  - tests/test_brain_cache.py
  - tests/test_injection.py
baseline:
  observed_by: "root agent, independent full-suite run"
  passed: 519
  deselected: 1
  duration_seconds: 7.17
  interpretation: "Regression baseline only; known uncovered gaps remain"
nyquist:
  validation_file: missing
  compliant: false
gaps:
  - truth: "Every provider prefetch result obeys the deterministic two-lane 800-token budget."
    status: failed
    requirements: [RET-03]
    reason: "Disk fallback is assigned directly to _prefetch_cache; contradiction detail is appended after render_injection. Probes returned 1505 and 2094 whitespace tokens."
    artifacts:
      - path: notion_brain/provider.py
        issue: "initialize disk fallback at line 149 and contradiction append at lines 218–226 bypass the final budget."
      - path: tests/test_injection.py
        issue: "Tests cover renderer lane limits, not all provider output branches."
    missing:
      - "Route disk fallback and contradiction explanations through a final bounded rendering path."
      - "Preserve an explicit conflict signal while bounding its details."
      - "Add provider-level oversized disk and conflict regressions, checking total and lane budgets."
  - truth: "A successful cold retrieval populates the local cache for later offline recall."
    status: failed
    requirements: [RET-02]
    reason: "_prefetch_entries returns Notion results without caching them. An isolated successful read left brain_cache.db absent. Cache hits are available only for previously mirrored writes or externally seeded cache rows."
    artifacts:
      - path: notion_brain/provider.py
        issue: "Remote fallback at lines 631–637 has no cache population step; hydration at lines 193–210 is also not persisted."
      - path: notion_brain/brain_cache.py
        issue: "Cache primitives exist but are not connected to the remote read/hydration path."
      - path: tests/test_brain_cache.py
        issue: "Utility round-trip tests do not demonstrate cold provider read followed by a new offline provider."
    missing:
      - "Persist successfully retrieved/hydrated active rows without making cache failures fail usable recall."
      - "Verify a new provider can recall cached content with remote query and body access disabled."
      - "Keep an intentionally empty cache distinguishable from a missing or unreadable cache."
      - "Record an appropriate cache-hit latency measurement before asserting the less-than-5ms criterion."
  - truth: "The remote fallback feeding the cache and injected context excludes superseded rows."
    status: failed
    requirements: [RET-02, SUP-02]
    reason: "The local cache filters active rows, but _prefetch_entries remote fallback does not. An isolated probe returned a Superseded row."
    artifacts:
      - path: notion_brain/provider.py
        issue: "Remote query results are sorted and returned without the local cache's status restriction."
      - path: notion_brain/brain_cache.py
        issue: "list_active correctly filters status='active'; fallback behavior is inconsistent with it."
    missing:
      - "Filter superseded remote rows before rendering and read-through cache population."
      - "Add a cold-cache provider regression proving historical rows are not injected."
---

# Phase 9 verification: retrieval correctness and local cache

**Status: gaps_found.** Hydration is implemented, but the full read-through and injection-budget contracts are not satisfied. This is the first discovered Phase 9 verification report; no original execution SUMMARY or Nyquist VALIDATION file was present. It records current evidence, not retroactive successful execution.

The parent/root independently ran the full offline suite: **519 passed, 1 deselected in 7.17s**. Existing tests passing is a regression baseline. The failures below were demonstrated using isolated temporary-directory/mocked-storage probes and source traces; no live Notion request was needed.

## Observable truths

| Requirement | Expected behavior | Result | Evidence |
| --- | --- | --- | --- |
| RET-01 | Retrieved rows use available Content/Summary or page-body text. | **Demonstrated** | `provider.py:193–210`; hydration tests cover source selection, duplicate fetches and errors. Empty underlying sources can still produce empty text. |
| RET-02 | Read-through cache provides offline recall after successful retrieval, with a recorded `<5ms` cache-hit result. | **Partial** | Cached writes can be recalled, but cold remote retrieval does not create/populate SQLite. No performance measurement was found. |
| RET-03 | Every prefetch output respects 400/400 lane budgets and an 800-token total. | **Partial / failed boundary** | Renderer tests pass, but initialized disk text and appended contradiction explanations bypass it. |

The integration check also identified a Phase 10 contract affecting Phase 9's fallback: superseded Notion rows are returned even though `brain_cache.list_active` excludes them.

## Required artifacts and connections

| Artifact / connection | Status | Evidence |
| --- | --- | --- |
| `brain_cache.py` cache primitives | Present and substantive | SQLite schema, active filtering, round-trip tests and safe failure handling exist. |
| `injection.py` two-lane renderer | Present and substantive | Deterministic trimming and lane tests exist; token convention is whitespace-delimited words. |
| Notion write → cache mirror → cached prefetch | WIRED | `_mirror_memory_cache` writes accepted memory rows; `_prefetch_entries` reads cache hits. |
| Notion read/body hydration → cache population | **BROKEN / BLOCKER** | Fallback returns fetched rows without writing the cache; rendered hydrated content is not persisted. |
| Disk initialization → bounded prefetch | **BROKEN / BLOCKER** | `_prefetch_cache` receives `combined[:4000]` directly and `prefetch` returns it immediately. |
| Contradiction details → bounded prefetch | **BROKEN / BLOCKER** | Conflict strings are appended after `render_injection`. |
| Remote fallback → active-only recall | **BROKEN / BLOCKER** | No status filtering before remote rows are returned. |
| Original `09-*-SUMMARY.md` | Missing | Work order and dispatch brief are not execution evidence. |
| Original `09-VERIFICATION.md` | Missing before this report | This report records failure, not a passing phase closure. |
| `09-VALIDATION.md` | Missing | Nyquist validation cannot be marked compliant. |

## Behavioral observations

| Probe | Setup | Actual outcome |
| --- | --- | --- |
| Disk budget | Mock bootstrap/disk reads; initialize with 1,500 words; call real `prefetch`. | **1,505 whitespace tokens**, including the disk-context marker. |
| Conflict budget | Mock `_prefetch_entries` with two active same-subject rows, each containing 1,000 words. | **2,094 whitespace tokens** after conflict details are appended. |
| Read-through persistence | Empty temporary home; mock successful remote query; call `_prefetch_entries`. | `brain_cache.db` **does not exist** afterward. |
| Historical fallback | Empty temporary home; mock one row with `Status: Superseded`. | `_prefetch_entries` **returns the old row**. |

These are failures even under the implementation's own whitespace-token estimator; no model-tokenizer assumption is needed to demonstrate the cap violations.

## Gap-closure acceptance tests

1. Oversized initialized disk memory remains within the final budget, including any context marker; repeated prefetch returns the same bounded text.
2. Oversized conflicting memories preserve an explicit contradiction signal while total output and lane allocation stay within their caps.
3. A cold successful read, including required body hydration, persists usable active content; a new provider recalls it with all remote access disabled.
4. An intentionally empty cache remains a cache hit; a missing/unreadable cache follows the defined fallback behavior.
5. Superseded rows from the remote fallback are neither injected nor introduced as active cached facts.
6. Cache-write and body-hydration failures preserve available recall without silently making every cache hit require network access.
7. Measure the supported cache-hit path before claiming the `<5ms` criterion; keep wall-clock benchmarking distinct from correctness assertions.

After implementation, rerun the relevant provider/cache/injection regressions and full repository gates, then update this report with actual results. Do not turn the current passing baseline into proof that these missing branches have been fixed.
