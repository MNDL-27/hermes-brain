# Hermes Brain v1.0.1 — Remediation Status

**Target release:** v1.0.1
**Source of findings:** `docs/superpowers/specs/2026-07-25-v1.0.1-production-readiness-design.md` (lines 28-40) + install-script security review
**Created:** 2026-08-19
**Last updated:** 2026-08-19

---

## Status Legend

- `CONFIRMED` — finding is accurate and needs fixing
- `FALSE_POSITIVE` — finding does not match actual code (with justification)
- `ACCEPTED_RISK` — valid finding, deferred with human approval (logged below)
- `FIXED` — fix applied and verified
- `IN_PROGRESS` — fix being applied

## Findings Registry

| ID | Severity | Description | File:Line | Status | Wave |
|---|---|---|---|---|---|
| AUD-RELIABLE-01 | P1 | Recall does not reliably retrieve full page bodies | `notion_brain/store.py` (search_entries) | CONFIRMED | Wave 2 |
| AUD-RELIABLE-02 | P1 | Schema values and write payloads are inconsistent | `notion_brain/provider.py` (_write_entry) | CONFIRMED | Wave 2 |
| AUD-RELIABLE-03 | P1 | Schema repair may archive databases without migrating their pages | `notion_brain/bootstrap.py` (reset_databases) | CONFIRMED | Wave 2 |
| AUD-RELIABLE-04 | P1 | Writes can report success without durable persistence | `notion_brain/provider.py` (handle_tool_call) | CONFIRMED | Wave 2 |
| AUD-RELIABLE-05 | P1 | Background daemon threads can race and may not flush all writes | `notion_brain/provider.py` (daemon threads) | CONFIRMED | Wave 2 |
| AUD-RELIABLE-06 | P1 | Some updates create duplicate pages instead of updating existing pages | `notion_brain/provider.py` (_write_entry) | CONFIRMED | Wave 2 |
| AUD-RELIABLE-07 | P1 | Database-filtered search can ignore the query | `notion_brain/provider.py` (handle_tool_call → search) | CONFIRMED | Wave 2 |
| AUD-SEC-01 | P0 | Secret (NOTION_API_KEY) leaked to shell profile ($SHELL_RC) | `scripts/install.sh` (lines 258-273) | FIXED | Wave 1 |
| AUD-SEC-02 | P0 | Redaction does not cover every write path | `notion_brain/provider.py`, `notion_brain/store.py` | CONFIRMED | Wave 1 |
| AUD-PKG-01 | P2 | Built wheel does not provide verified Hermes plugin discovery | `plugin.yaml`, `scripts/install.sh` | CONFIRMED | Wave 3 |
| AUD-LINT-01 | P1 | Ruff fails on production code | repo-wide | CONFIRMED | Wave 2 |
| AUD-LINT-02 | P1 | Mypy fails on production and test code | repo-wide | CONFIRMED | Wave 2 |
| AUD-COV-01 | P2 | Branch-aware package coverage is 67%, below 80% release gate | tests/ | CONFIRMED | Wave 3 |
| AUD-TEST-01 | P2 | Real Hermes and live Notion integration are not sufficiently tested | tests/ | CONFIRMED | Wave 3 |
| AUD-STATE-01 | N/A | Current working tree contains uncommitted user changes that must be preserved | git status | FALSE_POSITIVE (preserved, not a code fix) | — |

---

## Waves

### Wave 1 — P0 Security / Financial Integrity

| ID | Fix | Status |
|---|---|---|
| AUD-SEC-01 | Remove NOTION_API_KEY export from shell profile; keep only in `~/.hermes/.env` | FIXED |
| AUD-SEC-02 | Ensure redaction covers every write path in provider and store | IN_PROGRESS |

### Wave 2 — P1 Reliability / Correctness

| ID | Fix | Status |
|---|---|---|
| AUD-RELIABLE-01 | Implement full page body retrieval with pagination | — |
| AUD-RELIABLE-02 | Normalize schema values and write payloads consistently | — |
| AUD-RELIABLE-03 | Schema repair must migrate pages before archiving old DB | — |
| AUD-RELIABLE-04 | Writes must confirm durable persistence before reporting success | — |
| AUD-RELIABLE-05 | Replace daemon threads with serialized worker | — |
| AUD-RELIABLE-06 | Updates must use Notion patch/update, not create-new | — |
| AUD-RELIABLE-07 | Database-filtered search must honor the query parameter | — |
| AUD-LINT-01 | Make Ruff pass | — |
| AUD-LINT-02 | Make Mypy pass | — |

### Wave 3 — P2 Quality / Coverage / Packaging

| ID | Fix | Status |
|---|---|---|
| AUD-PKG-01 | Add Hermes plugin discovery shim to wheel | — |
| AUD-COV-01 | Raise coverage to 80%+ | — |
| AUD-TEST-01 | Add live Notion and Hermes integration tests | — |

---

## Human Decisions Log

| Date | Decision | Reasoning | Approved By |
|---|---|---|---|
| 2026-08-19 | AUD-SEC-01 fix: remove NOTION_API_KEY from shell profile, keep in `.env` only | Shell profiles are world-readable in many setups; `.env` is chmod 600 and scoped to Hermes home | remediation orchestrator |
| 2026-08-19 | AUD-STATE-01 classified as FALSE_POSITIVE | Uncommitted changes are user state to preserve, not a code defect to fix | remediation orchestrator |

---

## Production Readiness Checklist

- [ ] All P0 findings FIXED + VERIFIED (or FALSE_POSITIVE / ACCEPTED_RISK)
- [ ] All P1 findings FIXED + VERIFIED
- [ ] Regression tests pass
- [ ] Build passes
- [ ] Typecheck passes
- [ ] Lint passes
- [ ] Security re-audit performed
- [ ] Coverage >= 80%
- [ ] Production Readiness Score >= 7.5/10

**Current score:** TBD after Wave 1 completes

---

## Remediation Summary (to be filled at end)

*What was fixed, what was rejected, what was accepted as risk, before/after scores, remaining known issues.*
