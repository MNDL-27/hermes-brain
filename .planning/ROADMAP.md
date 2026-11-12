# Roadmap: hermes-brain

## Milestones

- ✅ **v1.0 Release Polish** — Phases 1-3 (shipped 2026-09-21)
- ✅ **v1.1 Distribution & Updates** — Phases 4-6 (shipped 2026-10-07)
- ✅ **v1.2 Update UX & Tooling Polish** — Phases 7-8 (shipped 2026-11-07)
- **v1.3 Brain Architecture & Freemium Foundation** — Phases 9–11 (defined 2026-11-02; Phase 9 verified; Phase 10 gap planning active after audit 2026-11-09)
- **v1.4 Semantic Brain Layer** — Phases 12–15 (defined 2026-11-06; implementation present, gaps and GSD verification debt remain)

**Current route:** `/gsd-plan-phase 10 --gaps`. Phase 9 plan 09-02 is verified and pushed as `45c8ca2`. Close the earliest unfinished approved phase before advancing. The 2026-11-07 v1.3/v1.4 completion report is superseded by the [milestone audit](v1.4-MILESTONE-AUDIT.md); no new v1.5 scope is defined. Push, merge and release are separate from implementation and verification.

## Phases

<details>
<summary>✅ v1.0 Release Polish (Phases 1-3) — SHIPPED 2026-09-21</summary>

- [x] Phase 1: Config Schema Test Infrastructure (1/1 plans) — completed 2026-09-20
- [x] Phase 2: Pre-Commit Quality Gates & Tooling Parity (1/1 plans) — completed 2026-09-20
- [x] Phase 3: Platform Portability & Installation Guard (1/1 plans) — completed 2026-09-20

Full phase details archived to: [.planning/milestones/v1.0-ROADMAP.md](.planning/milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Distribution & Updates (Phases 4-6) — SHIPPED 2026-10-07</summary>

- [x] Phase 4: Build Metadata Modernization & PyPI Publishing (2/2 plans) — completed 2026-09-26
- [x] Phase 5: CLI Update Drift Detection (1/1 plans) — completed 2026-09-29
- [x] Phase 6: Cached Non-Blocking Auto-Update Check (1/1 plans) — completed 2026-10-07

Full phase details archived to: [.planning/milestones/v1.1-ROADMAP.md](.planning/milestones/v1.1-ROADMAP.md)

</details>

### v1.2 Update UX & Tooling Polish (Phases 7-8)

**Milestone goal:** Close the three loose ends called out at the v1.1 closeout — commit-level drift detection with release-notes links for git-clone installs, an opt-in pre-push pytest hook plus scheduled `pre-commit autoupdate` for contributors, and clearing the three pre-existing offline test-suite hangs so `pytest -q` is a usable release gate again. No new CLI surface beyond the drift UX rewrites, no Notion schema changes, no packaging rebuild, no new external integrations.

- [x] **Phase 7: Update UX — Commit-Level Drift + Release-Notes Link** (2/2 plans) — completed 2026-11-07
- [x] **Phase 8: Developer Tooling & Test Reliability** (2/2 plans) — completed 2026-11-07

### v1.3 Brain Architecture & Freemium Foundation (Phases 9-11)

**Milestone goal:** Evolve hermes-brain from a naive Notion REST caller into a competitive, metabolic memory engine. Fix the prefetch schema blind spot, add a local-first SQLite read-through cache to decouple turn latency from Notion API limits, implement subject_key supersession to eliminate truth contradictions, cap injection at 800 tokens (two-lane architecture), and lay the foundation for the Obsidian adapter gated for premium users while free users remain Notion-only.

- [x] **Phase 9: Retrieval Correctness & Local Read-Through Cache** — verified 2026-11-09 (`45c8ca2`): hydrated cold reads populate the offline cache, active rows only, and every injection path obeys the 400/400 budget. GSD closure evidence: 09-02 summary, verification and validation.
- [ ] **Phase 10: Event-Driven Supersession & Truth Integrity** — Gaps found: SUP-01/SUP-02; original GSD closure unverified (implementation history `7ceaafb`) - Add `Subject Key` tracking across Memory rows; incoming facts mark older conflicting facts as `status: superseded` rather than accumulating contradictions; historical versions remain auditable
- [ ] **Phase 11: Storage Adapter Abstraction & Freemium Gate** — Gaps found: ADAPT-02/ADAPT-03; original GSD closure unverified (implementation history `71e7122`) - Refactor backend behind a pluggable `StorageAdapter` interface (NotionAdapter = default/free; ObsidianVaultAdapter = premium stub with license entitlement verification)

### v1.4 Semantic Brain Layer (Phases 12-15)

**Milestone goal:** Borrow NVIDIA Auto Ontology's semantic context layer architecture: shift from raw note/table search to a deterministic Semantic Catalog, add User-Certified vs Inferred truth tiers, expose rich Graph Provenance across facts, and guard against hallucinations with an Answerability Gate.

- [ ] **Phase 12: Core Semantic Catalog** — Implementation observed; original GSD closure unverified (implementation history `da6b1d4`) - Provider-neutral catalog model for Terms (synonyms/descriptions), Entities, and Relations; deterministically maps terms to backing store locations without LLM in the read path
- [ ] **Phase 13: User-Gated Certification Flow** — Gaps found: CERT-03; original GSD closure unverified (implementation history `700221c`) - Distinguish `inferred` vs `certified` status; user confirmation promotes; retrieval prefers certified facts; certified corrections immediately supersede contradictory inferred memories
- [ ] **Phase 14: Graph Provenance & Relational Recall** — Gaps found: PROV-01; original GSD closure unverified (implementation history `c5e829e`) - Return provenance (source/session/timestamp/status) per memory; replace binary supersession with explicit `supersedes` relation edges; graph traversal for related memories
- [ ] **Phase 15: Answerability Gate & Contradiction Detection** — Implementation observed; original GSD closure unverified (implementation history `6208569`) - Pre-retrieval catalog coverage check; report missing semantic terms and unverified answerability when uncovered; surface contradictory candidates as explicit conflicts rather than picking arbitrarily

## Phase Details

### Phase 7: Update UX — Commit-Level Drift + Release-Notes Link

**Goal**: A git-clone install behind `main` by N commits learns about it from `notion_brain update` and from the cached auto-update check; the printed link lands on the release notes page, not the repo root.
**Depends on**: v1.1 (Phases 4-6)
**Requirements**: UPD-06, UPD-07
**Success Criteria** (what must be TRUE):

  1. A git-clone install at a commit N behind the latest tag on `main` reports "behind by N commits" through `notion_brain update` even when `__version__` matches the latest tag's version (UPD-06).
  2. The same commit-drift signal flows into the cached auto-update check's banner and health report, with the same offline-tolerance contract as CHK-01..05 (no network on startup; failures degrade silently) (UPD-06).
  3. The update banner prints `https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z` (release notes), derived from the same tag the drift check resolves — copy-pasteable in every mode (UPD-07).
  4. No mutation: the command still never executes `pip install`, `git pull`, or any environment change (carried UPD-05 contract).

**Plans**: 2/2 plans — completed 2026-11-07

### Phase 8: Developer Tooling & Test Reliability

**Goal**: Contributors get an opt-in pre-push hook running the full offline test suite, the pre-commit hook config stays current via a scheduled `pre-commit autoupdate` workflow, and the three pre-existing offline test-suite hangs are cleared so `pytest -q` is a usable release gate again.
**Depends on**: Nothing (independent of Phase 7; can execute in either order)
**Requirements**: TOOL-01, TOOL-02, TEST-HANGS
**Success Criteria** (what must be TRUE):

  1. Running the provided opt-in install command registers a pre-push git hook that runs `pytest -q` before a remote push and blocks the push on test failure (TOOL-01).
  2. The pre-push hook honors the same offline contract as CI (hermetic tests, network-marked tests deselected) and fails fast rather than hanging on the three known TEST-HANGS files (TOOL-01, TEST-HANGS).
  3. A scheduled GitHub Actions workflow runs `pre-commit autoupdate` on a weekly cron and opens an automated maintenance PR (or posts a workflow summary listing available hook updates) when updates exist; the workflow declares least-privilege `permissions` (TOOL-02).
  4. The full offline `pytest` run completes with zero hangs: `test_coverage_gaps`, `test_migration_privacy_blockers`, and `test_provider` each finish or fail within the CI timeout, with a root-cause note for each (TEST-HANGS).
  5. Total suite count does not shrink silently — any reclassified tests (e.g. network-marked) are counted and named; nothing is skipped without a recorded reason (TEST-HANGS).

**Plans**: 2/2 plans — completed 2026-11-07

Plans:
- [x] 08-01-PLAN.md — commit TEST-HANGS hermetic infra + audit suite-count in PROJECT/STATE/REQUIREMENTS
- [x] 08-02-PLAN.md — opt-in `scripts/pre-push` hook + `.github/workflows/pre-commit-autoupdate.yml` (TOOL-01, TOOL-02)

---

### Phase 9: Retrieval Correctness & Local Read-Through Cache

**Goal**: Fix the prefetch schema blind spot so memories actually display their text summaries, back the memory store with a local SQLite read-through cache (`<5ms` cached prefetch, zero Notion calls on cache hits), and enforce an 800-token two-lane injection budget.
**Depends on**: v1.2 (Phase 8)
**Requirements**: RET-01 (prefetch text hydration), RET-02 (SQLite local cache mirror), RET-03 (two-lane 800-token context cap)
**Success Criteria**:
  1. `provider.py` prefetch surfaces available source text from `Content`, a `Summary` property or page body blocks; rows with no available text retain the existing empty-content behavior.
  2. A local SQLite cache (`~/.hermes/brain_cache.db`) mirrors active memory rows; prefetch executes in `<5ms` offline with zero network calls.
  3. Context injection is hard-capped at 800 whitespace-token units split between Lane 1 (pinned/critical, 400 units) and Lane 2 (dynamic context, 400 units), retaining the existing budget convention.

**Implementation history**: `7b78b98` (2026-11-07); semantic follow-up fixes in `fb7ec04` (2026-11-09).
**Verification**: Passed 09-02: 6/6 must-haves and RET-01/02/03, with current GSD fingerprint. Full suite 532 passed; cached prefetch median 1.012ms / p95 1.349ms. See [09-VERIFICATION.md](phases/09-retrieval-correctness-local-cache/09-VERIFICATION.md).
**Next action**: `/gsd-plan-phase 10 --gaps` against `phases/10-event-driven-supersession/10-VERIFICATION.md`.

### Phase 10: Event-Driven Supersession & Truth Integrity

**Goal**: Implement `subject_key` logical slots so new facts supersede old conflicting facts rather than piling up contradictory memories.
**Depends on**: Phase 9
**Requirements**: SUP-01 (subject_key schema & detection), SUP-02 (non-destructive status flipping: active -> superseded), SUP-03 (historical timeline / recall-as-of)
**Success Criteria**:
  1. Updating a fact on the same subject (e.g. `device.daily_phone` from S24 to S21 FE) marks the older row `Status: Superseded` in Notion.
  2. Queries filter to `Status: Active` by default so the agent never hallucinates from contradictory historical state.

**Implementation history**: `7ceaafb` (2026-11-07); semantic follow-up fixes in `fb7ec04` (2026-11-09); gap closure in `f9c589b` (2026-11-09).
**Verification**: Passed 10-02: 3/3 scoped contracts and SUP-01/SUP-02/SUP-03 closed; full suite 561 passed with a current fingerprint. See [10-VERIFICATION.md](phases/10-event-driven-supersession/10-VERIFICATION.md).

### Phase 11: Storage Adapter Abstraction & Freemium Gate

**Goal**: Decouple the memory engine from Notion REST into a pluggable `StorageAdapter` hierarchy, enabling the free tier (Notion-only) and laying the premium entitlement path for an Obsidian Vault adapter.
**Depends on**: Phase 10
**Requirements**: ADAPT-01 (`StorageAdapter` protocol), ADAPT-02 (NotionAdapter refactor), ADAPT-03 (Premium entitlement / license check stub), ADAPT-04 (ObsidianAdapter architecture)
**Success Criteria**:
  1. Core agent memory operations (`search`, `remember`, `supersede`, `prefetch`) call a generic `StorageAdapter` interface.
  2. Free tier defaults to `NotionAdapter`.
  3. Attempting to select `ObsidianAdapter` checks an entitlement token/license; if unentitled, it gracefully explains the upgrade requirement and falls back to Notion.

**Implementation history**: `71e7122` (2026-11-07); semantic follow-up fixes in `fb7ec04` (2026-11-09); provider wiring and entitlement flow closure on 2026-11-12 (uncommitted working tree on top of `f9c589b`).
**Verification**: Passed 11-01: 3/3 success criteria verified for read and selection paths; full suite 568 passed, ruff and mypy clean. The Memory write path remains on `store.*` as an explicit ADAPT-02 ceiling because certification/provenance/graph semantics exceed the generic protocol. See [11-VERIFICATION.md](phases/11-storage-adapters/11-VERIFICATION.md).

### Phase 12: Core Semantic Catalog

**Goal**: Create provider-neutral, deterministic semantic definitions that map user vocabulary to memory entities, relationships, and backing store locations.
**Depends on**: Phase 11
**Requirements**: CAT-01, CAT-02, CAT-03
**Success Criteria**:
  1. Core catalog types represent terms, synonyms, entities, relations, and provider-neutral storage references.
  2. Deterministic catalog APIs resolve terms and enumerate entities/relations without LLM calls in the retrieval path.
  3. Notion and Obsidian adapters map catalog references to their respective storage locations.

**Implementation history**: `da6b1d4` (2026-11-07); semantic follow-up fixes in `fb7ec04` (2026-11-09).
**Verification**: Implementation observed; original GSD closure unverified. Original phase SUMMARY/VERIFICATION artifacts were not recorded; see the [milestone audit](v1.4-MILESTONE-AUDIT.md).

### Phase 13: User-Gated Certification Flow

**Goal**: Make user-confirmed knowledge more trusted than agent inference, without letting agents self-certify.
**Depends on**: Phase 12
**Requirements**: CERT-01, CERT-02, CERT-03
**Success Criteria**:
  1. Agent-written memories default to inferred; explicit user confirmation is the only promotion path to certified.
  2. Retrieval ranks certified over inferred facts at equal recency and surfaces certification status.
  3. Certified corrections supersede conflicting inferred facts while retaining historical records.

**Implementation history**: `700221c` (2026-11-07); semantic follow-up fixes in `fb7ec04` (2026-11-09).
**Verification**: Gaps found: CERT-03; original GSD closure unverified. Original phase SUMMARY/VERIFICATION artifacts were not recorded; see the [milestone audit](v1.4-MILESTONE-AUDIT.md).

### Phase 14: Graph Provenance & Relational Recall

**Goal**: Make every recalled fact auditable and traverse explicit memory relationships, including supersession history.
**Depends on**: Phase 13
**Requirements**: PROV-01, PROV-02, PROV-03
**Success Criteria**:
  1. Recall results expose source, session, timestamp, and truth status for each fact.
  2. Supersession writes an explicit relation edge while preserving historical recall.
  3. Related facts can be traversed by typed relation edges, with tests proving path and cycle handling.

**Implementation history**: `c5e829e` (2026-11-07); semantic follow-up fixes in `fb7ec04` (2026-11-09).
**Verification**: Gaps found: PROV-01; original GSD closure unverified. Original phase SUMMARY/VERIFICATION artifacts were not recorded; see the [milestone audit](v1.4-MILESTONE-AUDIT.md).

### Phase 15: Answerability Gate & Contradiction Detection

**Goal**: Fail explicitly when the semantic catalog cannot ground a query; report contradictory candidates rather than arbitrarily selecting a truth.
**Depends on**: Phase 14
**Requirements**: ANS-01, ANS-02
**Success Criteria**:
  1. Catalog coverage check runs before fuzzy recall and returns deterministic unsupported-term output when coverage is zero.
  2. Multiple active conflicting values for one subject are returned as a conflict, not silently ranked into a single answer.
  3. Provenance and certification are included in supported, unsupported, and conflict responses.

**Implementation history**: `6208569` (2026-11-07); semantic follow-up fixes in `fb7ec04` (2026-11-09).
**Verification**: Implementation observed; original GSD closure unverified. Original phase SUMMARY/VERIFICATION artifacts were not recorded; see the [milestone audit](v1.4-MILESTONE-AUDIT.md).

---

### Quick tasks already landed (not phases)

- `260927-p1q` — hermetic offline unit suite (autouse socket-deny fixture, `network` marker registration + deselection, `test_offline_build_and_twine_check` marked network, `test_search_dispatches` mock-target fix, init-refresh network-leak fix) — commits `06fcec8..9bc661a` on worktree branch `claude/mystifying-einstein-d76cf0`; content mirrored to the main worktree as uncommitted changes pending commit
- `260928-mli` — top-level `permissions: contents: read` block on `publish.yml` (CodeQL medium fix) — commits `56e467b`, `cddde1b` on the same branch; content mirrored to the main worktree as uncommitted changes pending commit
