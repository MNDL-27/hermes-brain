# Roadmap: hermes-brain

## Milestones

- ✅ **v1.0 Release Polish** — Phases 1-3 (shipped 2026-09-21)
- ✅ **v1.1 Distribution & Updates** — Phases 4-6 (shipped 2026-10-07)
- ✅ **v1.2 Update UX & Tooling Polish** — Phases 7-8 (shipped 2026-11-07)
- ✅ **v1.3 Brain Architecture & Freemium Foundation** — Phases 9-11 (shipped 2026-11-13)
- 🚧 **v1.4 Semantic Brain Layer** — Phases 12-15 (all phases verified; milestone closeout pending)

**Current route:** Close out v1.4. All four phases are implemented and verified, and the [v1.4 audit](v1.4-MILESTONE-AUDIT.md) passed (11/11 v1.4 requirements). No new implementation work is defined. Merge, tag/release and v1.5 scope remain separate decisions.

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

<details>
<summary>✅ v1.2 Update UX & Tooling Polish (Phases 7-8) — SHIPPED 2026-11-07</summary>

- [x] Phase 7: Update UX — Commit-Level Drift + Release-Notes Link (2/2 plans) — completed 2026-11-07
- [x] Phase 8: Developer Tooling & Test Reliability (2/2 plans) — completed 2026-11-07

Full phase details archived to: [.planning/milestones/v1.2-ROADMAP.md](.planning/milestones/v1.2-ROADMAP.md)

</details>

<details>
<summary>✅ v1.3 Brain Architecture & Freemium Foundation (Phases 9-11) — SHIPPED 2026-11-13</summary>

- [x] Phase 9: Retrieval Correctness & Local Read-Through Cache (1/1 plans) — completed 2026-11-09
- [x] Phase 10: Event-Driven Supersession & Truth Integrity (1/1 plans) — completed 2026-11-09
- [x] Phase 11: Storage Adapter Abstraction & Freemium Gate (1/1 plans) — completed 2026-11-12

Full phase details archived to: [.planning/milestones/v1.3-ROADMAP.md](.planning/milestones/v1.3-ROADMAP.md)

</details>

### v1.4 Semantic Brain Layer (Phases 12-15)

**Milestone goal:** Shift from raw note/table search to a deterministic semantic catalog, add user-certified vs inferred truth tiers, expose graph provenance across facts, and guard against hallucinations with an answerability gate.

- [x] Phase 12: Core Semantic Catalog (1/1 plans) — completed 2026-11-12
- [x] Phase 13: User-Gated Certification Flow (1/1 plans) — completed 2026-11-12
- [x] Phase 14: Graph Provenance & Relational Recall (1/1 plans) — completed 2026-11-12
- [x] Phase 15: Answerability Gate & Contradiction Detection (1/1 plans) — completed 2026-11-12

Verification: [v1.4-MILESTONE-AUDIT.md](v1.4-MILESTONE-AUDIT.md) — all four phases passed, Nyquist compliant, 11/11 v1.4 requirements satisfied.
