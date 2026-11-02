# Requirements: hermes-brain

**Defined:** 2026-09-19 (v1.0) — Last reset: 2026-10-08 (v1.2 selection from v1.1 carryover)
**Core Value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.

**Milestone:** v1.2 — Update UX & Tooling Polish (intake accepted via Paperclip interaction `5246bf23` at 2026-10-08T07:48Z; previously approved at the v1.1 milestone closeout as the next-milestone scope)

## v1.2 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Update UX (UPD)

- [ ] **UPD-06**: Commit-level drift detection between formal tags so git-clone installs see "behind N commits" alerts even when `__version__` is unchanged.
- [ ] **UPD-07**: `notion_brain update` and the cached auto-update check render the link as the canonical release-notes URL `https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z`, copy-pasteable and derived from the same tag the drift check resolves.

### Developer Tooling (TOOL)

- [ ] **TOOL-01**: An optional pre-push git hook runs `pytest -q` before remote push. Installation is opt-in; the hook fails fast on any failing test or pre-existing hang with the same gating the CI `test` job uses.
- [ ] **TOOL-02**: A scheduled GitHub Actions workflow runs `pre-commit autoupdate` on a cron basis (e.g. weekly) and consumes the resulting hook-config update — via PR, workflow summary, or `git.autoUpdate` artifact — without manual intervention.

### Test Reliability (TEST)

- [ ] **TEST-HANGS**: Investigate and resolve the three pre-existing offline test-suite hangs accepted as v1.1 known gaps — `test_coverage_gaps`, `test_migration_privacy_blockers`, and `test_provider` — so the full offline `pytest` run finishes within the existing CI timeout and remains a usable release gate. Pre-existing hangs must be **fixed**, not silently `@pytest.mark.skip`ed.

## v1.3 Requirements (Defined 2026-11-02 — queued behind v1.2)

Requirements derived from the competitive memory-landscape research (`.planning/research/2026-11-02-competitive-memory-landscape.md`).

### Retrieval Correctness (RET)

- [ ] **RET-01**: Prefetch hydrates non-empty summary text per row by reading a `Summary` rich-text property or hydrating page body blocks; no more blank `- [kind] Title: ` prefetch lines.
- [ ] **RET-02**: A local SQLite read-through cache mirrors active memory rows; turn-zero prefetch completes offline in <5ms with zero Notion API calls; the existing background worker drains writes to Notion.
- [ ] **RET-03**: Prompt injection is hard-capped at 800 tokens split into Lane 1 (pinned identity/warnings/decisions, 400 tok) and Lane 2 (dynamic per-turn context, 400 tok), with deterministic overflow trimming.

### Supersession (SUP)

- [ ] **SUP-01**: Memory rows carry a `Subject Key` logical slot (e.g. `device.daily_phone`, `preferences.engine_cc`); detection infers it from content with an explicit override parameter.
- [ ] **SUP-02**: Writing a fact whose `Subject Key` matches an existing active row marks the older row `Status: Superseded` (non-destructive; history preserved) instead of leaving contradictions.
- [ ] **SUP-03**: Superseded history stays queryable (recall-as-of / timeline listing) so past truths remain auditable.

### Storage Adapter & Freemium (ADAPT)

- [ ] **ADAPT-01**: A `StorageAdapter` protocol abstracts `search`, `remember`, `supersede`, `prefetch`, `health`.
- [ ] **ADAPT-02**: The current Notion code path is refactored behind `NotionAdapter` with no behavior change for existing users.
- [ ] **ADAPT-03**: A premium entitlement check (license token) gates non-free storage adapters; unentitled selection falls back to Notion with an upgrade notice.
- [ ] **ADAPT-04**: An `ObsidianVaultAdapter` premium adapter (markdown + SQLite index inside the user's vault) is specified and scaffolded behind the entitlement check; free tier remains Notion-only.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UPD-06 | Phase 7 | Pending |
| UPD-07 | Phase 7 | Pending |
| TOOL-01 | Phase 8 | Pending |
| TOOL-02 | Phase 8 | Pending |
| TEST-HANGS | Phase 8 | Pending |
| RET-01 | Phase 9 | Defined |
| RET-02 | Phase 9 | Defined |
| RET-03 | Phase 9 | Defined |
| SUP-01 | Phase 10 | Defined |
| SUP-02 | Phase 10 | Defined |
| SUP-03 | Phase 10 | Defined |
| ADAPT-01 | Phase 11 | Defined |
| ADAPT-02 | Phase 11 | Defined |
| ADAPT-03 | Phase 11 | Defined |
| ADAPT-04 | Phase 11 | Defined |

**Coverage:**
- v1.2 requirements: 5 total
- Mapped to phases: 5 ✓
- Dropped: 0
- Adjusted: 0
- Deferred to next milestone: 0

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
*Last updated: 2026-10-08 — milestone intake accepted (Paperclip interaction `5246bf23`).*
