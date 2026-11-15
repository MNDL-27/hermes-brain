---
phase: "13"
slug: user-gated-certification-flow
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-12"
plan: "13-01"
requirements: [CERT-01, CERT-02, CERT-03]
validated: "2026-11-12"
---

# Phase 13 validation strategy

Gap-closure validation for CERT-03 failure isolation. CERT-01 and CERT-02 were already demonstrated; this phase adds failing-before/passing-after regressions for the accepted-Truth-write boundary.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest with monkeypatched store, catalog and cache collaborators |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_certification.py -q` |
| Scoped command | `.venv/bin/python -m pytest tests/test_certification.py tests/test_supersession.py tests/test_write_provenance.py -q` |
| Full gate | `env -u PYTHONPATH UV_NO_SYNC=1 .venv/bin/python -m pytest -q` |
| Static gates | `.venv/bin/python -m ruff check notion_brain tests`; `.venv/bin/python -m mypy notion_brain` |

## Per-task verification map

| Task | Requirements | Behavior | Command | Status |
| --- | --- | --- | --- | --- |
| 13-01-01 | CERT-03 | Accepted Truth flip is isolated from optional predecessor metadata, catalog and cache work; peers continue | `.venv/bin/python -m pytest tests/test_certification.py -q` | Pass |
| 13-01-02 | CERT-03 | Failure injection proves isolation and the rejected-Truth boundary | `.venv/bin/python -m pytest tests/test_certification.py tests/test_supersession.py tests/test_write_provenance.py -q` | Pass |

## Required observations

| Behavior | Test setup and assertion |
| --- | --- |
| Catalog failure | `Catalog.save` raises with a secret-bearing message; assert both peers flip status, both predecessor cache rows are superseded, the return is `Certified: ...`, and the log is redacted. |
| Metadata failure | `Superseded Page ID` write raises; assert both peer status flips still occur and the certification succeeds. |
| Truth failure | The Truth update raises; assert the error return and no status, metadata, graph or cache work. |
| Existing boundaries | All existing confirmation, ranking, schema-evolution and certified-predecessor tests remain green. |

## Sampling and final gate

- Certification suite: **25 passed in 0.21s**.
- Scoped suite: **63 passed in 0.47s**.
- Full repository gate: **573 passed, 1 deselected in 7.66s**; ruff, mypy and whitespace clean.
- No live Notion call or external confirmation UI required.

## Sign-off

- [x] Every task has an executable automated command.
- [x] Failure-injection regressions fail against the previous single-try ordering.
- [x] Scoped and full repository gates pass.
- [x] Static gates pass.
- [x] Summary and verification fingerprint exist in `13-01-SUMMARY.md` and `13-VERIFICATION.md`.

**Validation status:** validated. No human-only check applies to these deterministic backend contracts.
