# hermes-brain

## What This Is

hermes-brain replaces local flat markdown memory files (`MEMORY.md` / `USER.md`) with a structured, multi-database Notion workspace under a single **Hermes Brain** parent page. Instead of an agent forgetting decisions or cluttering a single text file across long sessions, context is classified into dedicated databases with typed properties, status tracking, confidence scoring, and tag indexing for the Hermes AI agent ecosystem.

## Core Value

Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.

## Current Work: v1.3 Phase 9 Gap Closure

**Goal:** Complete and verify the already-approved v1.3 foundation before closing v1.4. The semantic catalog, certification boundary, graph and answerability implementations are present; the 2026-11-09 [audit](v1.4-MILESTONE-AUDIT.md) found remaining integration gaps and missing original GSD closure artifacts. Start with Phase 9 cache population, current-memory filtering and the total injection budget.

**Shipped in v1.1 (Phases 4-6):**
- ✓ `pyproject.toml` migrated to PEP 639 SPDX `license = "MIT"` and `setuptools>=77.0.3` floor — v1.1 (META-01/02)
- ✓ Tag-triggered OIDC PyPI publish workflow (`.github/workflows/publish.yml`) with `environment: pypi` + `id-token: write` and zero static PyPI tokens — v1.1 (DIST-01/02)
- ✓ Documented maintainer runbook (`docs/RELEASES.md`) covering automated release, one-time Trusted Publisher setup, manual twine fallback, and recovery — v1.1 (DIST-03)
- ✓ `notion_brain update` CLI subcommand with per-mode upgrade commands, integer-tuple SemVer ranking, `--check`/`--json` flags, no-mutation guarantee — v1.1 (UPD-01..05)
- ✓ `$HERMES_HOME/.update_cache.json` with atomic writes (tempfile + `os.replace`, `0o600`), synchronous <1ms startup read, background TTL refresh on existing sync worker — v1.1 (CHK-01..03, CHK-05)
- ✓ `health_report()` reads cache instead of performing synchronous network update check — v1.1 (CHK-04)

**Milestone history and current status (user-confirmed order: v1.2 → v1.3 → v1.4, no skipping):**
- ✅ **v1.2 Update UX & Tooling Polish** (Phases 7-8) — shipped 2026-11-07: UPD-06/07 commit drift + release URL; TOOL-01/02 pre-push hook + autoupdate workflow; TEST-HANGS fixes.
- **v1.3 Brain Architecture & Freemium Foundation** (Phases 9–11) — implementation committed, but RET-02/03, SUP-01/02 and ADAPT-02/03 have gaps. Phase 9 is active; formal closure remains unverified.
- **v1.4 Semantic Brain Layer** (Phases 12–15) — semantic catalog, certification, graph and answerability implementation committed, including review fixes in `fb7ec04`. CERT-03 and PROV-01 still have integration gaps. Original phase SUMMARY/VERIFICATION artifacts are absent; no verified completion or release is claimed.

**Next action:** `/gsd-plan-phase 9 --gaps`, then close remaining approved phases in order. Prerequisite branch integration and the user-authorized push are pending.

**Next Milestone Goals:** v1.5 is undefined; this gap-closure work does not introduce a new milestone scope.

## Requirements

### Validated

- ✓ Seven structured Notion databases (`Memory`, `Tasks`, `Projects`, `Content`, `Research`, `Career`, `Entities`) — existing
- ✓ Heuristic & optional local LLM turn classification and extraction (`notion_brain/extract.py`) — existing
- ✓ 5 core Hermes tool schemas (`notion_brain_search`, `notion_brain_remember`, `notion_brain_task`, `notion_brain_content`, `notion_brain_research`) — existing
- ✓ Non-blocking background sync worker with thread-safe queue and graceful shutdown — existing
- ✓ Strict secret redaction for API keys, tokens, and exception boundaries (`raise ... from None`) — existing
- ✓ CLI utilities for setup wizard, health diagnostic, schema repair, database wiping, and markdown import — existing
- ✓ Full multi-block page body hydration and chunked paragraph writes for Notion limits — existing
- ✓ Complete unit test suite for `notion_brain/config_schema.py` (5 tests, 100% statement + branch coverage, offline host stubs) — v1.0 (SCHEMA-01/02/03, #51)
- ✓ `.pre-commit-config.yaml` wiring ruff lint/format, mypy typechecking, and whitespace/EOF hooks mirroring CI — v1.0 (HOOK-01/02/03/04, #52)
- ✓ `scripts/install.sh` Darwin detection with manual setup guidance and exit 0; Linux paths regression-free — v1.0 (PLAT-01/02/03, #53)
- ✓ `pyproject.toml` PEP 639 SPDX license + setuptools>=77.0.3 floor + offline packaging tests (4 tests) — v1.1 (META-01/02)
- ✓ OIDC PyPI publish workflow + maintainer runbook (tokenless, OIDC trusted publishing) — v1.1 (DIST-01/02/03)
- ✓ `notion_brain update` CLI with semver, per-mode commands, --check/--json, no-mutation (26 tests) — v1.1 (UPD-01..05)
- ✓ `$HERMES_HOME/.update_cache.json` + provider init sync load + background TTL refresh on sync worker (20 tests) — v1.1 (CHK-01..05)

### v1.2 Closeout History

- [x] **UPD-06**: Commit-level drift detection between formal tags so git-clone users see "behind N commits" alerts
- [x] **UPD-07**: Update banner links directly to release notes URL
- [x] **TOOL-01**: Optional pre-push git hook running `pytest -q` before remote push
- [x] **TOOL-02**: Scheduled GitHub Action for automated `pre-commit autoupdate` verification
- [x] **TEST-HANGS**: Investigate and resolve the three pre-existing test-suite hangs (`test_coverage_gaps`, `test_migration_privacy_blockers`, `test_provider`) blocking full-suite runs

### Active Gap Closure

- [ ] **Phase 9 / RET-02, RET-03:** populate the cache after a cold Notion read, exclude superseded fallback rows, and budget every injection path including disk fallback and contradictions.
- [ ] **Phase 10 / SUP-01, SUP-02:** infer subject keys on background writes and preserve same-title history.
- [ ] **Phase 11 / ADAPT-02, ADAPT-03:** route provider operations through the adapter and wire runtime entitlement/fallback selection.
- [ ] **Phase 13 / CERT-03:** keep cache and remaining supersessions progressing when certification provenance writes fail.
- [ ] **Phase 14 / PROV-01:** retain provenance in cache and expose the required metadata in prompt recall.
- [ ] Reconstruct honest verification/summary evidence for Phases 9–15 from actual work; preserve historical reports without treating them as proof of completion.

### Out of Scope

- Automated Homebrew package bootstrap on macOS — manual installation instructions in README Step 2 are sufficient for release polish (#53); validated at v1.0
- Silent automatic self-modification in `notion_brain update` — modifying running virtual environments silently causes corruption; detect + instruct is standard
- Real-time cloud vector database integrations — local Notion workspace remains primary storage backend
- Live Notion API mocks in `test_config_schema.py` — schema is pure declarative metadata; network mocks add latency and failure modes
- Automatic staging of hook fixes (`git add`) — working tree changes must be reviewed and staged manually
- Synchronous network calls on runtime boot — adds 200–2500ms to every CLI/agent start; replaced by stale-while-revalidate cache (v1.1)
- Long-lived PyPI API tokens in CI secrets — leak risk, no automatic expiry; replaced by OIDC trusted publishing (v1.1)
- Bundling update cache in `notion_brain.json` — conflates package distribution state with Notion DB IDs; dedicated file (v1.1)

## Context

- **Ecosystem**: Python 3.11–3.13 plugin package for Hermes Agent ecosystem (`hermes-agent`).
- **Storage Layer**: Notion REST API (`api.notion.com/v1`) using internal integration tokens (`NOTION_API_KEY`).
- **Quality Gates**: Ruff linting and formatting, Mypy strict type checking, Pytest test suite with branch coverage tracking, and local pre-commit hooks (7 hooks) mirroring the CI `quality-debt` job.
- **Current State (audit 2026-11-09)**: semantic follow-up fixes committed in `fb7ec04`; 519 offline tests pass (1 deselected, 7.17s), Ruff and mypy are clean across 52 source files. This automated baseline does not cover all approved requirements. Phase 9 gap closure is active; v1.3/v1.4 push, merge and release are not yet recorded. The 2026-11-07 report of 487 passing tests and completed milestones is historical and superseded by the current audit.
- **Distribution**: `hermes-brain` wheel/sdist builds clean via `python -m build` + `twine check` (PEP 639 SPDX, setuptools>=77.0.3). PyPI publishing via GitHub Actions OIDC trusted publishing (no static token). Manual `docs/RELEASES.md` twine fallback maintained.
- **Update UX**: Remote version source of truth is the GitHub repository (latest tag/commit via public API), chosen over PyPI JSON API so git-installed users also get update notifications without PyPI lag. Detection is read-only; users run the printed upgrade command themselves. Cached status loads in <1ms on startup, refreshes in the background on the existing sync worker.

## Constraints

- **Compatibility**: Must support Python 3.11, 3.12, and 3.13 without deprecation warnings.
- **Security**: Redact all sensitive tokens (OpenAI, Notion, GitHub, Anthropic, Bearer tokens) across all input, output, and exception vectors.
- **CI Reliability**: Unit tests must run offline without requiring live Notion API credentials or a live Hermes daemon.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Isolated unit tests for `config_schema.py` | Schema declaration is pure Python; pure unit tests verify Desktop compatibility without network mocks | ✓ Good — v1.0: 5 tests, 100% coverage, offline-clean |
| Match `.pre-commit-config.yaml` to CI | Ensures local contributor commits pass the exact same ruff and mypy checks as GitHub Actions | ✓ Good — v1.0: 7 hooks, same ruff/mypy versions; note mypy wired via `repo: local` + `uv run` (not `mirrors-mypy` repo) |
| Clean exit 0 with guidance for Darwin in `install.sh` | Prevents package manager script failure on macOS while guiding developers to supported pip/symlink workflows | ✓ Good — v1.0: Step 0 guard before root/distro checks, Linux paths regression-free |
| PEP 639 SPDX string `license = "MIT"` | Modern packaging standard, zero deprecation warnings on Python 3.11–3.13 | ✓ Good — v1.1: META-01/02 verified, 4 offline packaging tests pass |
| OIDC trusted publishing over static PyPI API token | No long-lived credential in CI secrets, automatic expiry, passes modern security audits | ✓ Good — v1.1: DIST-01/02 verified, `id-token: write` job-scoped, `environment: pypi` |
| Documented twine runbook for offline/emergency releases | OIDC can fail or be unavailable; maintainers need a documented fallback | ✓ Good — v1.1: DIST-03 verified, four-section `docs/RELEASES.md` |
| Detect + instruct, never auto-mutate, for `notion_brain update` | Mutating the running venv silently causes `ImportError`/corruption/PEP 668 races | ✓ Good — v1.1: UPD-05 verified, four no-mutation subprocess-guard tests |
| Integer-tuple SemVer with pre-release ranking over string comparison | `1.10.0 > 1.9.0` and `1.1.0 > 1.1.0b1` must come out right | ✓ Good — v1.1: UPD-03 verified, 26 tests cover all four modes |
| GitHub API as remote source of truth over PyPI JSON | Git-clone users get update notifications without PyPI lag, single source of truth | ✓ Good — v1.1: UPD-01 verified, unauthenticated `urlopen` with bounded timeout |
| Stale-while-revalidate cache for update check | Synchronous cache read on startup (<1ms), background refresh on existing sync worker | ✓ Good — v1.1: CHK-01/02 verified, 20 tests; zero network on startup path |
| Dedicated `$HERMES_HOME/.update_cache.json` over bundling in `notion_brain.json` | Keeps package distribution state separate from Notion DB IDs; survives `reset --force` | ✓ Good — v1.1: CHK-03 verified, atomic tempfile + `os.replace` + `0o600` |
| Atomic write with `os.replace` + `fsync` + `0o600` | Survives crashes mid-write, no permission leak, no `JSONDecodeError` at startup | ✓ Good — v1.1: CHK-03 verified, corrupt/empty file tests pass |
| Bare `except Exception` + `redact_secrets` in `update_cache.refresh` | Worker thread never crashes; secrets never reach logs | ✓ Good — v1.1: CHK-05 verified, AWS-format token redaction test |
| Wall-clock timeout check after the call (not inside `_find_latest_tag`) | Preserves the upstream signature contract per plan prohibitions while bounding network exposure to ~2.5s | ✓ Good — v1.1: CHK-05 verified (WR-01 fix from code review) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-09 after the GSD completion audit reopened Phase 9 and recorded later verification debt.*
