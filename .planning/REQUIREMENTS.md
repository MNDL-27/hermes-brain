# Requirements: hermes-brain

**Defined:** 2026-09-21
**Core Value:** Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.

**Milestone:** v1.1 — Distribution & Updates

## v1.1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### PyPI Publishing (DIST)

- [x] **DIST-01**: A `v*` tag push automatically builds wheel + sdist and uploads to PyPI via OIDC trusted publishing — no static PyPI API tokens in CI secrets
- [x] **DIST-02**: The publish workflow uses separate build and publish jobs, gated on `refs/tags/v*`, with `environment: pypi` and `id-token: write` so the OIDC token exchange succeeds
- [x] **DIST-03**: A documented manual twine runbook (build → `twine check` → `twine upload dist/*`) exists for offline/emergency releases when GitHub Actions or the OIDC exchange is unavailable

### Build Metadata (META)

- [x] **META-01**: `pyproject.toml` declares the PEP 639 SPDX string `license = "MIT"` and the deprecated `license = { text = "MIT" }` table is removed
- [x] **META-02**: Build-system floor is bumped to `setuptools>=77.0.3`; `python -m build` + `twine check` produce clean metadata with zero deprecation warnings on Python 3.11, 3.12, and 3.13

### CLI Update Command (UPD)

- [x] **UPD-01**: `notion_brain update` detects drift against the latest GitHub release and prints the installed version vs. the latest version
- [x] **UPD-02**: The command prints an exact, copy-pasteable upgrade command matching the detected environment (uv / pip venv / pip user / git clone)
- [x] **UPD-03**: Version comparison uses integer-tuple SemVer with pre-release ranking — `1.10.0` sorts above `1.9.0` and `1.1.0` sorts above `1.1.0b1`
- [x] **UPD-04**: `--check` exits 0 when current and 2 when an update is available; `--json` emits a machine-readable payload
- [x] **UPD-05**: The command is detect + instruct only — it never mutates the running environment (no `pip install`, `git pull`, or virtualenv modification)

### Auto Update Check (CHK)

- [x] **CHK-01**: Provider init reads `$HERMES_HOME/.update_cache.json` synchronously in <1ms with zero network calls on the startup path
- [x] **CHK-02**: When the cache TTL (default 24h, configurable) is expired, a refresh is dispatched to the existing `notion-brain-sync-worker` background queue and stale data is served until the refresh lands
- [x] **CHK-03**: Cache writes are atomic (tempfile + `os.replace`, mode `0o600`) with a `JSONDecodeError` guard so a corrupt or interrupted cache degrades silently and never crashes startup
- [x] **CHK-04**: `health_report()` no longer performs its own synchronous network update check and instead reads the cached update status
- [x] **CHK-05**: The refresh queries the GitHub API unauthenticated with a short timeout (~2.5s), redacts secrets from all error/log paths, and is offline-safe (no exception escapes when the network is down)

## Future Requirements

Deferred. Tracked but not in the current roadmap.

### Update Enhancements

- **UPD-06**: Commit-level drift detection between formal tags so git-clone users see "behind N commits" alerts even when `__version__` is unchanged
- **UPD-07**: Update banner links directly to the release notes URL (`https://github.com/MNDL-27/hermes-brain/releases/tag/vX.Y.Z`)

### Developer Tooling (TOOL)

- **TOOL-01**: Optional pre-push git hook running `pytest -q` before remote push
- **TOOL-02**: Scheduled GitHub Action for automated `pre-commit autoupdate` verification

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Silent automatic self-update (in-process `pip install`) | Mutates bytecode/shared libraries in the active interpreter; causes `ImportError`, corruption, PEP 668 crashes, and races with the daemon worker. Detect + instruct is the chosen pattern. |
| Synchronous network calls on runtime boot | Adds 200–2500ms to every CLI/agent start and hangs when offline. Replaced by stale-while-revalidate cache. |
| Long-lived PyPI API tokens in CI secrets | Leak risk, no automatic expiry, fails modern security audits. Replaced by OIDC trusted publishing. |
| Bundling the update cache in `notion_brain.json` | Conflates package distribution state with Notion database IDs; `reset --force` would wipe it and it breaks when Notion is unconfigured. Dedicated file instead. |
| Color output without TTY/`NO_COLOR` check | Mangles piped or logged output. `--json` and non-TTY paths must stay plain. |
| Automated Homebrew formula | Manual macOS install instructions sufficient (validated at v1.0, #53). |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| META-01 | Phase 4 | Complete |
| META-02 | Phase 4 | Complete |
| DIST-01 | Phase 4 | Complete |
| DIST-02 | Phase 4 | Complete |
| DIST-03 | Phase 4 | Complete |
| UPD-01 | Phase 5 | Complete |
| UPD-02 | Phase 5 | Complete |
| UPD-03 | Phase 5 | Complete |
| UPD-04 | Phase 5 | Complete |
| UPD-05 | Phase 5 | Complete |
| CHK-01 | Phase 6 | Complete |
| CHK-02 | Phase 6 | Complete |
| CHK-03 | Phase 6 | Complete |
| CHK-04 | Phase 6 | Complete |
| CHK-05 | Phase 6 | Complete |

**Coverage:**

- v1.1 requirements: 15 total
- Mapped to phases: 15 ✓
- Unmapped: 0

---
*Requirements defined: 2026-09-21*
*Last updated: 2026-09-21 — traceability populated for v1.1 roadmap (Phases 4-6)*
