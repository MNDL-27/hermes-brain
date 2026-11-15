# Phase 07: Update UX — Commit-Level Drift + Release-Notes Link - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-15
**Phase:** 07-update-ux-commit-level-drift-release-notes-link
**Areas discussed:** Commit Drift Comparison Target, CLI Exit Codes on Commit-Only Drift, Banner & Release Notes Presentation, Offline / Rate-Limit Degradation & Cache

---

## Commit Drift Comparison Target

| Option | Description | Selected |
|--------|-------------|----------|
| Remote default branch (`main`) | Compare local HEAD against remote main. Detects unpulled commits pushed to main between releases. | ✓ |
| Latest release tag commit | Compare local HEAD against the commit SHA of latest release tag. | |
| Upstream tracking branch | Compare against remote tracking branch if set; fall back to GitHub default branch main. | |

**User's choice:** Remote default branch (`main`).
**Follow-up questions:**
- Method: Local git command first (`git rev-list --count HEAD..origin/main`), falling back to GitHub API compare endpoint (`compare/{local_sha}...main`).
- Branch check: Only evaluate when local checked-out branch is `main`.
- Ahead/behind: Divergence format ("ahead by N, behind by M").

---

## CLI Exit Codes on Commit-Only Drift

| Option | Description | Selected |
|--------|-------------|----------|
| Exit code 0 (Informational notice only) | Version is up to date, so exit 0. Print notice in human/JSON output. | ✓ |
| Exit code 2 (Treat commit drift as drift) | Any drift (version or commit) exits 2. | |
| Exit code 3 (Dedicated exit code) | Exit 0 clean, 2 version drift, 3 commit-only drift. | |

**User's choice:** Exit code 0 for commit-only drift.
**Reconciliation with JSON:** In JSON output, `drift: true` is emitted with `drift_type: "commit"`. CLI inspects `drift_type` to return 0 when `drift_type == "commit"`, and 2 when version drift exists.

---

## Claude's Discretion

- Version drift takes precedence over commit drift when both exist.
- Single-line concise banner format linking to release notes (`https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z`).
- Cache persistence in `$HERMES_HOME/.update_cache.json` with silent degradation on offline / rate limits.

## Deferred Ideas

- None.
