---
phase: "15"
slug: answerability-gate-contradiction-detection
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-12"
plan: "15-01"
requirements: [ANS-01, ANS-02]
validated: "2026-11-12"
---

# Phase 15 validation strategy

Gap-closure validation for the ANS-02 notice bound. ANS-01 was already demonstrated; this phase makes the contradiction notice explicitly bounded and proves the structured payload stays complete.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest with provider monkeypatches and the real injection renderer |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_answerability.py tests/test_prefetch_gap_closure.py tests/test_injection.py -q` |
| Full gate | `env -u PYTHONPATH UV_NO_SYNC=1 .venv/bin/python -m pytest -q` |
| Static gates | `.venv/bin/python -m ruff check notion_brain tests`; `.venv/bin/python -m mypy notion_brain` |

## Per-task verification map

| Task | Requirements | Behavior | Command | Status |
| --- | --- | --- | --- | --- |
| 15-01-01 | ANS-02 | Notice caps rendered entries and reports the exact omitted count | `.venv/bin/python -m pytest tests/test_answerability.py tests/test_prefetch_gap_closure.py -q` | Pass |
| 15-01-02 | ANS-02 | Large-conflict bound, small-conflict completeness, payload completeness and redaction | `.venv/bin/python -m pytest tests/test_answerability.py tests/test_prefetch_gap_closure.py tests/test_injection.py -q` | Pass |

## Required observations

| Behavior | Test setup and assertion |
| --- | --- |
| Large conflict | Six divergent active values render at most four entry lines plus `… 2 more conflicting entries omitted`; warning lane ≤400 tokens and total ≤800. |
| Small conflict | Two values still render both values, timestamps and certification labels; no omitted marker. |
| Payload completeness | The search payload returns all six contradiction entries even though rendering is capped. |
| Redaction | A secret-bearing value renders `[REDACTED_SECRET]`. |
| Determinism | Repeating `prefetch()` yields identical output. |
| Existing contracts | Phase 9's two-entry budget regression stays green. |

## Sampling and final gate

- Answerability/budget suite: **37 passed in 0.27s**.
- Full repository gate: **582 passed, 1 deselected in 5.92s**; ruff, mypy and whitespace clean.
- No live Notion call required.

## Sign-off

- [x] Every task has an executable automated command.
- [x] Regressions cover the cap, overflow count, small conflicts, payload completeness and redaction.
- [x] Scoped and full repository gates pass.
- [x] Static gates pass.
- [x] Summary and verification fingerprint exist in `15-01-SUMMARY.md` and `15-VERIFICATION.md`.

**Validation status:** validated. No human-only check applies to these deterministic backend contracts.
