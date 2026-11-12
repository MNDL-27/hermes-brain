---
phase: "12"
slug: semantic-catalog
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-12"
plan: "12-01"
requirements: [CAT-01, CAT-02, CAT-03]
validated: "2026-11-12"
---

# Phase 12 validation strategy

Verification-only contract. No implementation gap was found, so validation measures the existing catalog behavior and its provider consumption rather than new code.

## Infrastructure

| Item | Value |
| --- | --- |
| Framework | Existing pytest, temporary catalog/vault directories, existing provider monkeypatches |
| Configuration | `pyproject.toml`; default suite excludes the network marker |
| Quick command | `.venv/bin/python -m pytest tests/test_catalog.py tests/test_catalog_home.py tests/test_catalog_search.py tests/test_answerability.py -q` |
| Full gate | `env -u PYTHONPATH UV_NO_SYNC=1 .venv/bin/python -m pytest -q` |
| Static gates | `.venv/bin/python -m ruff check notion_brain tests`; `.venv/bin/python -m mypy notion_brain` |

## Per-criterion verification map

| Criterion | Requirement | Behavior | Evidence | Status |
| --- | --- | --- | --- | --- |
| 1 | CAT-01 | Terms/synonyms, typed entities, relations and provider-neutral storage refs round-trip through redacted atomic JSON | `tests/test_catalog.py`; persistence and redaction tests; probe | Pass |
| 2 | CAT-02 | `resolve_term`, `list_entities`, `get_relations` and `match_definitions` are deterministic; no LLM/network dependency | `tests/test_catalog.py`, `tests/test_catalog_search.py`; import scan probe | Pass |
| 3 | CAT-03 | Notion page/database ids and Obsidian in-vault note paths resolve from refs; provider selects referenced rows without textual equality, including referenced vault notes | `tests/test_catalog.py` resolve tests, `tests/test_catalog_search.py` selection + Obsidian ref-recall tests, `tests/test_adapters.py` `get_note` safety test; probe | Pass |

## Required observations

| Behavior | Setup and assertion |
| --- | --- |
| Provider neutrality | `catalog.py` imports `schema` only; `store`/`bootstrap`/`adapters` are not catalog dependencies. |
| Deterministic resolution | Exact, case-insensitive and synonym hits; unknown names return `None`; entity and relation filters are case-insensitive. |
| Persistence scope | Catalog saves/loads under `$HERMES_HOME`; session-scoped writes do not leak into the default location. |
| Notion reference mapping | Valid 32/36-character page and database ids are accepted; junk, URLs and non-Notion adapter names are rejected. |
| Obsidian reference mapping | Relative and absolute in-vault `.md` paths resolve; `..` traversal, non-`.md` and non-Obsidian refs are rejected. |
| Provider selection | A definition's resolved page id selects a row whose title does not contain the query; a database ref selects only rows from that database and cannot escape an explicit `database` filter. |
| Obsidian reference recall | A premium vault definition's resolved note path selects that note through `get_note` even when its title/body do not contain the query; unrelated notes stay excluded and out-of-store paths return `None`. |
| Superseded targets | A resolved reference does not recall a superseded row. |

## Sampling and final gate

- Targeted catalog suite: **58 passed in 0.28s**; adapter suite: **14 passed**.
- Full repository gate: **570 passed, 1 deselected in 5.44s** (Phase 11 baseline was 568; the two new regressions account for the delta).
- Ruff clean; mypy clean.
- Probe executed outside pytest: all checks passed.
- No live Notion or vault mutation, new dependency or external setup.

## Sign-off

- [x] Every criterion has executable evidence.
- [x] Existing tests were not modified to manufacture closure.
- [x] Full repository and static gates pass.
- [x] Independent probe covers CAT-01, CAT-02 and CAT-03 directly.
- [x] Summary and verification fingerprint exist in `12-01-SUMMARY.md` and `12-VERIFICATION.md`.

**Validation status:** validated. No human-only check applies to these deterministic backend contracts.
