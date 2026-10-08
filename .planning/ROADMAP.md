# Roadmap: hermes-brain

## Milestones

- ✅ **v1.0 Release Polish** — Phases 1-3 (shipped 2026-09-21)
- ✅ **v1.1 Distribution & Updates** — Phases 4-6 (shipped 2026-10-07)
- 🚧 **v1.2 Update UX & Tooling Polish** — Phases 7-8 (defined 2026-10-08, in progress)

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

- [ ] **Phase 7: Update UX — Commit-Level Drift + Release-Notes Link** - Git-clone installs behind `main` by N commits learn about it from `notion_brain update` and the cached auto-update check; the printed link lands on the release notes page
- [ ] **Phase 8: Developer Tooling & Test Reliability** - Opt-in pre-push pytest hook, weekly `pre-commit autoupdate` workflow, and the three TEST-HANGS files cleared

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

**Plans**: TBD

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

**Plans**: 2 plans

Plans:
- [ ] 08-01-PLAN.md — commit TEST-HANGS hermetic infra + audit suite-count in PROJECT/STATE/REQUIREMENTS
- [ ] 08-02-PLAN.md — opt-in `scripts/pre-push` hook + `.github/workflows/pre-commit-autoupdate.yml` (TOOL-01, TOOL-02)

---

### Quick tasks already landed (not phases)

- `260927-p1q` — hermetic offline unit suite (autouse socket-deny fixture, `network` marker registration + deselection, `test_offline_build_and_twine_check` marked network, `test_search_dispatches` mock-target fix, init-refresh network-leak fix) — commits `06fcec8..9bc661a` on worktree branch `claude/mystifying-einstein-d76cf0`; content mirrored to the main worktree as uncommitted changes pending commit
- `260928-mli` — top-level `permissions: contents: read` block on `publish.yml` (CodeQL medium fix) — commits `56e467b`, `cddde1b` on the same branch; content mirrored to the main worktree as uncommitted changes pending commit
