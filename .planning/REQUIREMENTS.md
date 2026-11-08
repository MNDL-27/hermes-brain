# Requirements: hermes-brain

**Defined:** 2026-09-19 (v1.0) — Last reset: 2026-10-08 (v1.2 selection from v1.1 carryover)
**Core Value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.

**Historical v1.2 intake:** Update UX & Tooling Polish (intake accepted via Paperclip interaction `5246bf23` at 2026-10-08T07:48Z; previously approved at the v1.1 milestone closeout as the next-milestone scope)

**Current work:** v1.3 Phase 10 gap planning after verified Phase 9 closure, followed by the remaining approved phases in order. v1.5 remains undefined.

## v1.2 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Update UX (UPD)

- [x] **UPD-06**: Commit-level drift detection between formal tags so git-clone installs see "behind N commits" alerts even when `__version__` is unchanged.
- [x] **UPD-07**: `notion_brain update` and the cached auto-update check render the link as the canonical release-notes URL `https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z`, copy-pasteable and derived from the same tag the drift check resolves.

### Developer Tooling (TOOL)

- [x] **TOOL-01**: An optional pre-push git hook runs `pytest -q` before remote push. Installation is opt-in; the hook fails fast on any failing test or pre-existing hang with the same gating the CI `test` job uses.
- [x] **TOOL-02**: A scheduled GitHub Actions workflow runs `pre-commit autoupdate` on a cron basis (e.g. weekly) and consumes the resulting hook-config update — via PR, workflow summary, or `git.autoUpdate` artifact — without manual intervention.

### Test Reliability (TEST)

- [x] **TEST-HANGS**: Investigate and resolve the three pre-existing offline test-suite hangs accepted as v1.1 known gaps — `test_coverage_gaps`, `test_migration_privacy_blockers`, and `test_provider` — so the full offline `pytest` run finishes within the existing CI timeout and remains a usable release gate. Pre-existing hangs must be **fixed**, not silently `@pytest.mark.skip`ed.

## v1.3 Requirements (Defined 2026-11-02 — gap closure active)

Audit follow-up 2026-11-09: unchecked boxes below mean GSD closure is unresolved, not that all implementation is absent. Phase 9 has current passing SUMMARY/VERIFICATION evidence; Phases 10–15 still await closure, with six requirements having concrete code gaps. See the [milestone audit](v1.4-MILESTONE-AUDIT.md).

Requirements derived from the competitive memory-landscape research (`.planning/research/2026-11-02-competitive-memory-landscape.md`).

### Retrieval Correctness (RET)

- [x] **RET-01**: Prefetch hydrates available text from `Content`, a `Summary` rich-text property or page body blocks, avoiding blank prefetch lines when source text exists. Rows without available source text retain the existing empty-content behavior.
- [x] **RET-02**: A local SQLite read-through cache mirrors active memory rows; turn-zero prefetch completes offline in <5ms with zero Notion API calls; the existing background worker drains writes to Notion.
- [x] **RET-03**: Prompt injection is hard-capped at 800 whitespace-token units split into Lane 1 (pinned identity/warnings/decisions, 400 units) and Lane 2 (dynamic per-turn context, 400 units), with deterministic overflow trimming. This retains the existing budget convention rather than model-tokenizer precision.

### Supersession (SUP)

- [ ] **SUP-01**: Memory rows carry a `Subject Key` logical slot (e.g. `device.daily_phone`, `preferences.engine_cc`); detection infers it from content with an explicit override parameter.
- [ ] **SUP-02**: Writing a fact whose `Subject Key` matches an existing active row marks the older row `Status: Superseded` (non-destructive; history preserved) instead of leaving contradictions.
- [ ] **SUP-03**: Superseded history stays queryable (recall-as-of / timeline listing) so past truths remain auditable.

### Storage Adapter & Freemium (ADAPT)

- [ ] **ADAPT-01**: A `StorageAdapter` protocol abstracts `search`, `remember`, `supersede`, `prefetch`, `health`.
- [ ] **ADAPT-02**: The current Notion code path is refactored behind `NotionAdapter` with no behavior change for existing users.
- [ ] **ADAPT-03**: A premium entitlement check (license token) gates non-free storage adapters; unentitled selection falls back to Notion with an upgrade notice.
- [ ] **ADAPT-04**: An `ObsidianVaultAdapter` premium adapter (markdown + SQLite index inside the user's vault) is specified and scaffolded behind the entitlement check; free tier remains Notion-only.

## v1.4 Requirements (Defined 2026-11-06 — implementation present, closure unverified)

Requirements derived from the Auto Ontology semantic-layer architecture study (github.com/NVIDIA/auto-ontology) and user-confirmed decisions of 2026-11-06. Builds on v1.3's StorageAdapter (ADAPT-01..04), local cache (RET-02), and supersession (SUP-01..03).

### Semantic Catalog (CAT)

- [ ] **CAT-01**: A provider-neutral semantic catalog model (Terms with description/synonyms, typed Entities, Relations) lives in core, independent of any StorageAdapter; both NotionAdapter and ObsidianVaultAdapter map the catalog into their backing store.
- [ ] **CAT-02**: The catalog is queryable deterministically (`resolve_term`, `list_entities`, `get_relations`) without LLM inference in the read path.
- [ ] **CAT-03**: Terms can map to concrete storage locations (Notion database/property, Obsidian note/section) so retrieval resolves through definitions instead of raw fuzzy search.

### Certification (CERT)

- [ ] **CERT-01**: Memories carry a truth status `inferred` (agent-written) vs `certified` (user-confirmed); retrieval prefers certified facts over inferred ones at equal recency.
- [ ] **CERT-02**: Only user confirmation promotes inferred → certified; agents may flag/suggest certification candidates but can never self-certify.
- [ ] **CERT-03**: A certified correction supersedes conflicting inferred rows immediately (integrates with SUP-02 status flipping).

### Provenance & Graph (PROV)

- [ ] **PROV-01**: Every recalled fact returns provenance: source (agent/session), timestamp, and current status/certification level.
- [ ] **PROV-02**: Supersession is stored as an explicit relation edge (`supersedes`) rather than only a status flag, keeping the historical chain auditable (extends SUP-03).
- [ ] **PROV-03**: Related entities are reachable by graph traversal (e.g. "decisions affecting project X") via stored links, not just text similarity.

### Answerability Gate (ANS)

- [ ] **ANS-01**: Before fuzzy retrieval, a coverage check resolves the question's entities/terms against the catalog; zero coverage reports that no known semantic terms were found and answerability cannot be verified, naming the missing terms. It blocks near-miss recall without claiming that no certified memory exists.
- [ ] **ANS-02**: Conflicting candidates (same subject, both active, divergent values) are surfaced as a contradiction instead of silently returning one row.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UPD-06 | Phase 7 | Completed |
| UPD-07 | Phase 7 | Completed |
| TOOL-01 | Phase 8 | Completed |
| TOOL-02 | Phase 8 | Completed |
| TEST-HANGS | Phase 8 | Completed |
| RET-01 | Phase 9 | Verified — 09-02 summary and current verification fingerprint |
| RET-02 | Phase 9 | Verified — 09-02 summary and current verification fingerprint |
| RET-03 | Phase 9 | Verified — 09-02 summary and current verification fingerprint |
| SUP-01 | Phase 10 | Gaps found — background ingestion does not infer subject keys |
| SUP-02 | Phase 10 | Gaps found — same-title overwrite loses history; cold fallback filtering fixed in 09-02 |
| SUP-03 | Phase 10 | Implementation observed — GSD closure unverified |
| ADAPT-01 | Phase 11 | Implementation observed — GSD closure unverified |
| ADAPT-02 | Phase 11 | Gaps found — provider operations bypass the adapter |
| ADAPT-03 | Phase 11 | Gaps found — runtime adapter selection/fallback is absent |
| ADAPT-04 | Phase 11 | Implementation observed — GSD closure unverified |
| CAT-01 | Phase 12 | Implementation observed — GSD closure unverified |
| CAT-02 | Phase 12 | Implementation observed — GSD closure unverified |
| CAT-03 | Phase 12 | Implementation observed — GSD closure unverified |
| CERT-01 | Phase 13 | Implementation observed — GSD closure unverified |
| CERT-02 | Phase 13 | Implementation observed — GSD closure unverified |
| CERT-03 | Phase 13 | Gaps found — provenance failure skips cache/remaining supersessions |
| PROV-01 | Phase 14 | Gaps found — cached metadata and prompt provenance are incomplete |
| PROV-02 | Phase 14 | Implementation observed — GSD closure unverified |
| PROV-03 | Phase 14 | Implementation observed — GSD closure unverified |
| ANS-01 | Phase 15 | Implementation observed — GSD closure unverified |
| ANS-02 | Phase 15 | Implementation observed — GSD closure unverified |

**Coverage:**
- v1.2 requirements: 5 total
- Shipped and verified: 5 (completed 2026-11-07)
- Mapped to phases: 5 ✓
- Dropped: 0
- Adjusted: 0
- Deferred to next milestone: 0
- v1.3 requirements: 10 total — 3 verified in Phase 9, 4 with concrete gaps, 3 with implementation observed but closure unverified
- v1.4 requirements: 11 total — 2 with concrete gaps; 9 with implementation observed but closure unverified
- Phase 9 now has current GSD summary, verification and validation evidence for RET-01/02/03. The missing original records for Phases 10–15 still require reconciliation.
- Current automated baseline: 532 passed, 1 deselected (6.39s); Ruff and mypy clean across 53 source files. Only specifically verified Phase 9 requirements are closed; later gaps remain open.
- Historical 2026-11-07 closeout report: 487 passed, 1 deselected, Ruff/mypy clean; its blanket completion claim is superseded by the 2026-11-09 audit

## Out of Scope (v1.2)

| Feature | Reason |
|---------|--------|
| New CLI subcommands beyond the drift UX rewrites UPD-06/07 require | Keeps the CLI surface the maintenance team owns small; "CLI ergonomics" can be its own milestone if needed |
| Notion schema changes | The 7-database schema shipped at v0.x; nothing in UPD-06/07/TOOL-01/02/TEST-HANGS requires a schema edit |
| Packaging rebuild | v1.1 (Phase 4) already modernized `pyproject.toml`, build-system floor, and offline packaging tests |
| New external integrations | TOOL-02 reuses the existing `.github/workflows/` surface; no new OAuth apps, no new services |
| Silent auto-mutation in `notion_brain update` | Carried from v1.1 UPD-05 detection + instruction-only contract |
| `@pytest.mark.skip` as the fix for any of the three TEST-HANGS files | Skipping silently removes the regression signal; the v1.1 closeout explicitly recorded these as TEST-HANGS *debt*, not as accepted removals |

---
*Requirements defined: 2026-10-08 (selected from `v1.1-REQUIREMENTS.md` §Future Requirements UPD-06/07, TOOL-01/02 and v1.1 `MILESTONES.md` known-gap #1).*
*Last updated: 2026-11-09 — audit reconciliation; Phase 9 verified; Phase 10 gap planning active and later approved work remains unverified.*
