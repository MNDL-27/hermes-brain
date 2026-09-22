# Roadmap: hermes-brain

## Milestones

- ✅ **v1.0 Release Polish** — Phases 1-3 (shipped 2026-09-21)
- 🚧 **v1.1 Distribution & Updates** — Phases 4-6 (in planning)

## Phases

- [ ] **Phase 4: Build Metadata Modernization & PyPI Publishing** — PEP 639 license, setuptools floor, OIDC publish workflow, manual twine runbook
- [ ] **Phase 5: CLI Update Drift Detection** — `notion_brain update` detects drift, instructs per-environment upgrade commands, machine-readable flags
- [ ] **Phase 6: Cached Non-Blocking Auto-Update Check** — sub-ms cached startup, background TTL refresh on daemon worker, health report reads cache

## Phase Details

### Phase 4: Build Metadata Modernization & PyPI Publishing

**Goal:** hermes-brain ships as a clean, modernly-packaged PyPI distribution with tokenless automated publishing and a documented manual fallback.
**Depends on**: v1.0 (Phases 1-3)
**Requirements**: META-01, META-02, DIST-01, DIST-02, DIST-03
**Success Criteria** (what must be TRUE):

  1. `pyproject.toml` declares `license = "MIT"` (PEP 639) with the deprecated `license = { text = "MIT" }` table removed, and `python -m build` + `twine check --strict` produce clean metadata with zero deprecation warnings on Python 3.11, 3.12, and 3.13 (META-01, META-02)
  2. Pushing a `v*` git tag triggers a CI workflow that builds wheel + sdist and uploads to PyPI via OIDC trusted publishing — no static PyPI API token exists in CI secrets (DIST-01)
  3. The publish workflow separates build and publish jobs, gates on `refs/tags/v*`, and configures `environment: pypi` with `id-token: write` so the OIDC token exchange succeeds (DIST-02)
  4. A maintainer can perform an offline/emergency release by following the documented twine runbook (build → `twine check` → `twine upload dist/*`) without any GitHub Actions involvement (DIST-03)

**Plans**: 2 plans
Plans:
**Wave 1**

- [ ] 04-01-PLAN.md — Modernize pyproject.toml to PEP 639 SPDX + setuptools>=77.0.3 and add offline packaging tests (META-01, META-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 04-02-PLAN.md — Author tag-triggered OIDC publish workflow (DIST-01, DIST-02) and maintainer release runbook with manual twine fallback (DIST-03)

### Phase 5: CLI Update Drift Detection

**Goal:** Users running hermes-brain from any install mode (uv, pip venv, pip user, git clone) can check for newer releases and get exact, copy-pasteable upgrade instructions — without the tool ever modifying their environment.
**Depends on**: Nothing (independent of Phase 4; both can execute in any order)
**Requirements**: UPD-01, UPD-02, UPD-03, UPD-04, UPD-05
**Success Criteria** (what must be TRUE):

  1. `notion_brain update` prints the installed version and the latest GitHub release version, clearly showing drift when a newer release exists (UPD-01)
  2. The printed upgrade command is exact and copy-pasteable for the detected environment: `uv` / pip venv / pip user / git clone each get their correct command, using the `hermes-brain` PyPI distribution name for wheel/pip installs (UPD-02)
  3. Version comparison uses integer-tuple SemVer with pre-release ranking — `1.10.0` sorts above `1.9.0`, and `1.1.0` sorts above `1.1.0b1` (UPD-03)
  4. `notion_brain update --check` exits 0 when current and 2 when an update is available; `--json` emits a machine-readable payload parseable by scripts and CI (UPD-04)
  5. The command only detects and instructs — running it never executes `pip install`, `git pull`, or any other mutation of the running environment (UPD-05)

**Plans**: TBD

### Phase 6: Cached Non-Blocking Auto-Update Check

**Goal:** The agent provider learns about new releases in the background with zero startup cost and zero network on the startup path.
**Depends on**: Phase 5 (reuses the update-check engine and cache format from the drift detection work)
**Requirements**: CHK-01, CHK-02, CHK-03, CHK-04, CHK-05
**Success Criteria** (what must be TRUE):

  1. Provider init reads `$HERMES_HOME/.update_cache.json` synchronously in under 1ms with zero network calls — verified with and without a network connection (CHK-01)
  2. When the cache TTL (default 24h, configurable) is expired, a refresh is dispatched to the existing `notion-brain-sync-worker` background queue and stale data is served until the refresh lands — no startup stall (CHK-02)
  3. Cache writes are atomic (tempfile + `os.replace`, mode `0o600`) and a corrupt or interrupted cache file degrades silently — startup never crashes with `JSONDecodeError` (CHK-03)
  4. `health_report()` shows cached update status instead of performing its own synchronous network update check (CHK-04)
  5. The background refresh queries the GitHub API unauthenticated with a ~2.5s timeout, redacts secrets from all error/log paths, and when offline no exception escapes to the worker (CHK-05)

**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 4. Build Metadata Modernization & PyPI Publishing | 0/2 | Planned | - |
| 5. CLI Update Drift Detection | 0/? | Not started | - |
| 6. Cached Non-Blocking Auto-Update Check | 0/? | Not started | - |

## Milestone Archive

<details>
<summary>✅ v1.0 Release Polish (Phases 1-3) — SHIPPED 2026-09-21</summary>

- [x] Phase 1: Config Schema Test Infrastructure (1/1 plans) — completed 2026-09-20
- [x] Phase 2: Pre-Commit Quality Gates & Tooling Parity (1/1 plans) — completed 2026-09-20
- [x] Phase 3: Platform Portability & Installation Guard (1/1 plans) — completed 2026-09-20

Full phase details archived to: [.planning/milestones/v1.0-ROADMAP.md](.planning/milestones/v1.0-ROADMAP.md)

</details>
