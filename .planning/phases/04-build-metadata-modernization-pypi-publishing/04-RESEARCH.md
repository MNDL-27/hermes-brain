# Phase 04: Build Metadata Modernization & PyPI Publishing - Research

**Researched:** 2026-09-22
**Domain:** Python packaging (PEP 639), PyPI OIDC Trusted Publishing, GitHub Actions CI/CD
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Version & Tag Discipline
- **D-01:** Enforce git tag strictly matches `pyproject.toml` version — build job validates tag matches version and fails early on mismatch. — **Reversibility:** costly — changing tag matching convention affects CI workflows and release scripts.
- **D-02:** Use standard `v*` tag format (`v1.1.0`), stripping leading `v` to validate against `pyproject.toml` version.
- **D-03:** Publish all `v*` tags including pre-releases (`v1.1.0b1`, `v1.1.0rc1`) to PyPI. PyPI automatically flags pre-releases so standard pip users won't receive them without `--pre`.
- **D-04:** Publish workflow automatically generates a matching GitHub Release with release notes linking the git tag and commit diff upon successful PyPI upload.
- **D-05:** Release version bumping is manual: maintainer updates version in `pyproject.toml`, commits `chore: release vX.Y.Z`, and pushes git tag `vX.Y.Z`.
- **D-06:** Document release recovery in runbook: if workflow fails before publish, fix and re-tag; if bad package is already published to PyPI, yank release via PyPI UI / twine (PyPI forbids re-uploading existing version numbers).

#### Runbook Placement & Content
- **D-07:** Create dedicated maintainer guide `docs/RELEASES.md` covering automated OIDC release lifecycle, PyPI one-time setup, and manual twine emergency fallback. Keeps user-facing `README.md` clean.
- **D-08:** Include full step-by-step walkthrough in `docs/RELEASES.md` for configuring PyPI Trusted Publishing (PyPI account → Publishing → Add publisher for `MNDL-27/hermes-brain` / `publish.yml` / `pypi` environment) before the first tag push.
- **D-09:** Document emergency manual uploads using PyPI API token via `TWINE_PASSWORD` environment variable or `~/.pypirc`.
- **D-10:** Document explicit pre-build cleaning (`rm -rf dist/ build/ *.egg-info`) in runbook to prevent stale artifact re-upload attempts.

#### Publish Gate Behavior
- **D-11:** Fully automated publish on tag push without manual GitHub environment approval gate.
- **D-12:** Workflow verifies that the pushed tag points to a commit reachable from the `main` branch before building/publishing, blocking accidental releases from experimental branches.
- **D-13:** Run full test suite (`pytest`, `ruff`, `mypy`) across Python matrix in CI as a prerequisite job before the publish job runs. Never publish from a broken tag.
- **D-14:** Enable PyPI build provenance attestations (`attestations: true` in `pypa/gh-action-pypi-publish`).
- **D-15:** Standard GitHub Actions re-run for transient network/PyPI errors; no custom retry loops inside workflow.
- **D-16:** Use `concurrency: group: publish` to serialize tag publish runs and prevent racing GitHub releases.
- **D-17:** Strict PEP 440 / SemVer format validation of tag before initiating build.

#### Verification Depth
- **D-18:** Direct publication to production PyPI only; TestPyPI is omitted to minimize operational overhead.
- **D-19:** Artifact verification runs `twine check --strict` on both wheel and sdist in the build job before upload.
- **D-20:** Automated post-publish smoke install job in CI: polls PyPI for new release, installs in isolated container, and verifies `python -c "import notion_brain"`.
- **D-21:** Unit test packaging offline in `tests/test_packaging.py` asserting `pyproject.toml` SPDX license string, build-backend floor (`setuptools>=77.0.3`), and clean offline `build` + `twine check`. Preserves 100% offline test guarantee.

### Claude's Discretion
None — all key release workflow parameters explicitly selected during discussion.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed strictly within Phase 4 boundaries.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| META-01 | `pyproject.toml` declares the PEP 639 SPDX string `license = "MIT"` and the deprecated `license = { text = "MIT" }` table is removed | Setuptools 77.0.0+ implementation of PEP 639 replaces table with `license = "MIT"` and `license-files = ["LICENSE"]` [CITED: setuptools.pypa.io/en/latest/userguide/license_migration.html]. Validated clean build with 0 deprecation warnings [VERIFIED: python -m build execution]. |
| META-02 | Build-system floor is bumped to `setuptools>=77.0.3`; `python -m build` + `twine check` produce clean metadata with zero deprecation warnings on Python 3.11, 3.12, and 3.13 | Build backend requirement bumped in `pyproject.toml` `[build-system] requires`. Tested clean build and `twine check --strict dist/*` execution [VERIFIED: local build verification]. |
| DIST-01 | A `v*` tag push automatically builds wheel + sdist and uploads to PyPI via OIDC trusted publishing — no static PyPI API tokens in CI secrets | GitHub Actions OIDC token exchange via `pypa/gh-action-pypi-publish@release/v1` using ambient credentials, `id-token: write`, and no static secrets [CITED: docs.pypi.org/trusted-publishers/using-a-publisher]. |
| DIST-02 | The publish workflow uses separate build and publish jobs, gated on `refs/tags/v*`, with `environment: pypi` and `id-token: write` so the OIDC token exchange succeeds | Workflow architecture separates `test-and-lint`, `build`, `publish`, and `smoke-test` jobs with `environment: pypi` scoped strictly to the publish job [CITED: docs.pypi.org/trusted-publishers/using-a-publisher]. |
| DIST-03 | A documented manual twine runbook (build → `twine check` → `twine upload dist/*`) exists for offline/emergency releases when GitHub Actions or the OIDC exchange is unavailable | Maintainer runbook in `docs/RELEASES.md` documenting prerequisite cleaning (`rm -rf dist/ build/ *.egg-info`), artifact building, strict metadata checks, PyPI API token upload via `TWINE_PASSWORD`, and release recovery/yanking [VERIFIED: D-06, D-07, D-08, D-09, D-10]. |
</phase_requirements>

## Summary

Phase 4 establishes modern Python distribution standards for `hermes-brain`. Current configuration uses deprecated setuptools packaging syntax `license = { text = "MIT" }` with `requires = ["setuptools>=68.0"]` [VERIFIED: pyproject.toml:1-11], which emits a loud deprecation warning on every build (`SetuptoolsDeprecationWarning: project.license as a TOML table is deprecated... Both options available on setuptools>=77.0.0`). Transitioning to PEP 639 SPDX string declarations (`license = "MIT"` and `license-files = ["LICENSE"]`) combined with bumping the build-backend floor to `setuptools>=77.0.3` produces pristine wheel and sdist distributions that pass `twine check --strict` with zero warnings across Python 3.11, 3.12, and 3.13.

For automated publishing, the phase eliminates long-lived static PyPI API tokens in favor of OpenID Connect (OIDC) Trusted Publishing. A dedicated `.github/workflows/publish.yml` triggers exclusively on `v*` git tags. Before publishing, the workflow enforces a rigorous multi-tier gate: Python test matrix (`pytest 3.11, 3.12, 3.13`), static analysis (`ruff`, `mypy`), git ancestor verification (`git merge-base --is-ancestor HEAD origin/main`) ensuring the tag belongs to `main`, and tag SemVer format and equality checks against `pyproject.toml`.

Artifacts are built once, strictly checked with `twine check --strict`, and uploaded using `pypa/gh-action-pypi-publish@release/v1` within a PyPI-scoped GitHub environment (`environment: pypi`, `id-token: write`). Build provenance attestations (PEP 740) are automatically attached. Upon publish success, native GitHub CLI (`gh release create`) publishes release notes, and an isolated smoke test job polls PyPI CDN with exponential backoff to confirm `pip install hermes-brain` and module import operate smoothly in clean environments. All manual workflows, one-time PyPI configuration steps, and emergency fallback procedures are codified in `docs/RELEASES.md`.

**Primary recommendation:** Update `pyproject.toml` to declare `license = "MIT"` and `setuptools>=77.0.3`, implement `.github/workflows/publish.yml` with separate `test`, `build`, `publish`, and `smoke-test` jobs using `pypa/gh-action-pypi-publish@release/v1`, add offline unit packaging checks in `tests/test_packaging.py`, and author `docs/RELEASES.md`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PEP 639 License Metadata | Build System (`pyproject.toml`) | Package Metadata (`PKG-INFO`) | Source of truth for build backend (`setuptools.build_meta`) when generating distribution wheels and sdists. |
| Tag & Ancestor Validation | CI/CD Orchestration (`publish.yml`) | Version Control (`git`) | Blocks unauthorized, malformed, or experimental branch tags from triggering builds before network resources are committed. |
| Quality & Test Gate | CI Runner (`pytest`, `ruff`, `mypy`) | Matrix Runtime (`3.11-3.13`) | Guarantees code parity and test success before any artifact is considered for release. |
| Distribution Packaging | Build Tooling (`python -m build`) | Artifact Storage (`actions/upload-artifact`) | Generates reproducible sdist tarballs and binary wheels in clean, isolated environments. |
| Pre-Publish Inspection | Package Validator (`twine check --strict`) | CI Build Job | Fails fast on malformed package descriptions, invalid licenses, or invalid distribution metadata. |
| OIDC Token Exchange & Upload | PyPI Identity (`pypa/gh-action-pypi-publish`) | PyPI API (`api.pypi.org`) | Short-lived cryptographic JWT authentication without static credential storage. Attaches PEP 740 provenance attestations. |
| Release Notification & Artifacts | GitHub API (`gh release create`) | Release Assets | Publishes release notes with commit logs and links built distributions to GitHub releases. |
| Post-Publish Verification | Smoke Test Container (`pip install`) | PyPI CDN (Fastly) | Validates external user installation path and imports from PyPI after CDN propagation. |
| Emergency Fallback & Operations | Maintainer Runbook (`docs/RELEASES.md`) | Maintainer CLI (`twine upload`) | Standardizes manual packaging, token authorization, artifact cleanup, and release yanking runbooks. |

## Standard Stack

### Core
| Library / Action | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| `setuptools` | `>=77.0.3` [VERIFIED: PyPI] | Build backend specification | Native support for PEP 639 SPDX license string expressions (`license = "MIT"`) and `license-files` [CITED: setuptools.pypa.io/en/latest/userguide/license_migration.html]. |
| `build` | `1.5.0` (locked `1.5.0`, PyPI `1.6.1`) [VERIFIED: PyPI] | PEP 517 build frontend | Standard PyPA package builder creating both sdist and wheel distributions in an isolated environment. |
| `twine` | `6.2.0` (locked `6.2.0`, PyPI `7.0.0`) [VERIFIED: PyPI] | Package metadata checker and upload utility | PyPA official utility for checking distribution metadata integrity and uploading to PyPI. |
| `pypa/gh-action-pypi-publish` | `@release/v1` [CITED: docs.pypi.org/trusted-publishers/using-a-publisher] | GitHub Actions PyPI publishing action | Official PyPA action supporting OIDC Trusted Publishing, environment segregation, and automatic PEP 740 provenance attestations. |
| GitHub CLI (`gh`) | `v2.45+` [VERIFIED: runner CLI] | GitHub Release management | Native CLI pre-installed on GitHub Actions Ubuntu runners; generates GitHub releases with changelogs without third-party action dependencies. |

### Supporting
| Action / Tool | Version | Purpose | When to Use |
|---------------|---------|---------|-------------|
| `actions/checkout` | `v4` | Source repository checkout | Used across all CI jobs; configured with `fetch-depth: 0` in build job to support `git merge-base` history traversal. |
| `actions/setup-python` | `v5` | Python runtime configuration | Configures specified Python versions (`3.11`, `3.12`, `3.13`) in CI runners. |
| `astral-sh/setup-uv` | `v6` | Fast dependency resolution | Used to synchronize locked virtual environments (`uv sync --locked --extra dev`) in CI. |
| `actions/upload-artifact` | `v4` | Artifact retention between jobs | Uploads built `.whl` and `.tar.gz` from `build` job to pass to `publish` job. |
| `actions/download-artifact` | `v4` | Artifact consumption | Downloads built artifacts in `publish` job into `dist/` directory for PyPI upload. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PEP 639 string `license = "MIT"` | `license = { text = "MIT" }` | TOML table format is officially deprecated in setuptools 77.0.0+ and scheduled for complete removal by Feb 2027 [CITED: setuptools.pypa.io/en/latest/userguide/license_migration.html]. |
| OIDC Trusted Publishing | Static PyPI API token (`PYPI_API_TOKEN`) | Static tokens stored in GitHub Secrets never expire, pose security exposure risks if leaked, and lack cryptographic workflow provenance [CITED: docs.pypi.org/trusted-publishers/]. |
| Native `gh release create` | `softprops/action-gh-release@v2` | Native `gh` is pre-installed on runners, zero external action supply chain risk, native stdlib/platform first principle. |
| Direct Production PyPI (D-18) | TestPyPI + Production PyPI | TestPyPI adds separate credentials, registration overhead, and synchronization delays with minimal benefit given comprehensive local test and strict twine checks. |

**Installation:**
```bash
# Development dependencies are configured in pyproject.toml [project.optional-dependencies] dev
uv sync --extra dev
```

**Version verification:**
Verified against PyPI and local environment on 2026-09-22:
```bash
# Output from pip index versions / PyPI JSON query:
setuptools: 84.0.0 (minimum required: >=77.0.3)
build: 1.5.0 (locked), 1.6.1 (latest PyPI)
twine: 6.2.0 (locked), 7.0.0 (latest PyPI)
pypa/gh-action-pypi-publish: release/v1 (rolling release branch)
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `setuptools` | PyPI | 20+ yrs | High (>100M/mo) | https://github.com/pypa/setuptools | [OK] | Approved (core Python packaging standard) |
| `build` | PyPI | 5+ yrs | High (>30M/mo) | https://github.com/pypa/build | [OK] | Approved (PyPA standard build tool) |
| `twine` | PyPI | 10+ yrs | High (>40M/mo) | https://github.com/pypa/twine | [OK] | Approved (PyPA standard upload tool) |

**Packages removed due to [SLOP] verdict:** None.
**Packages flagged as suspicious [SUS]:** None. (Note: `gsd_run query package-legitimacy check` returned `SUS` solely due to unpopulated PyPI download counts in the local query provider; verified manually against official PyPA GitHub repositories and PyPI indexes).

## Architecture Patterns

### System Architecture Diagram

```text
Maintainer Tag Push (v1.1.0)
         |
         v
+-------------------------------------------------------------+
| GitHub Actions: .github/workflows/publish.yml               |
|                                                             |
|  [Job 1: test-and-lint]                                     |
|    - Matrix: Python 3.11, 3.12, 3.13                        |
|    - uv sync --locked --extra dev                           |
|    - pytest -q                                              |
|    - ruff check notion_brain tests                          |
|    - mypy notion_brain tests                                |
|         |                                                   |
|         v (success on all matrix legs)                      |
|  [Job 2: build]                                             |
|    - actions/checkout (fetch-depth: 0)                      |
|    - Guard 1: Tag format PEP 440 / SemVer (vX.Y.Z)          |
|    - Guard 2: Tag version == pyproject.toml version         |
|    - Guard 3: git merge-base --is-ancestor HEAD origin/main |
|    - rm -rf dist/ build/ *.egg-info                         |
|    - python -m build                                        |
|    - twine check --strict dist/*                            |
|    - actions/upload-artifact@v4 (path: dist/)               |
|         |                                                   |
|         v (artifacts verified & staged)                     |
|  [Job 3: publish]                                           |
|    - environment: pypi                                      |
|    - permissions: id-token: write                           |
|    - actions/download-artifact@v4 (path: dist/)             |
|    - pypa/gh-action-pypi-publish@release/v1                 |
|         |---> OIDC Token Exchange (PyPI)                    |
|         |---> PEP 740 Provenance Attestation                |
|         |                                                   |
|         v (upload confirmed on PyPI)                        |
|  [Job 4: release]                                           |
|    - permissions: contents: write                           |
|    - gh release create ${{ tag }} dist/* --generate-notes   |
|         |                                                   |
|         v                                                   |
|  [Job 5: smoke-test]                                        |
|    - Polling loop: pip install hermes-brain==${{ version }} |
|    - python -c "import notion_brain; print(...)"            |
+-------------------------------------------------------------+
```

### Recommended Project Structure
```text
hermes-brain/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # Existing PR and push CI
│       └── publish.yml             # New: Tag-triggered PyPI OIDC release workflow
├── docs/
│   └── RELEASES.md                 # New: Maintainer release runbook & manual fallback
├── notion_brain/
│   └── __init__.py                 # Contains __version__ = "1.0.3"
├── pyproject.toml                  # Modernized: license = "MIT", setuptools>=77.0.3
└── tests/
    └── test_packaging.py           # New: 100% offline packaging metadata & build tests
```

### Pattern 1: PEP 639 SPDX License Specification
**What:** Declare project license using standardized SPDX string expressions in `pyproject.toml`.
**When to use:** All Python projects targeting modern setuptools (77.0.0+).
**Example:**
```toml
# Source: https://setuptools.pypa.io/en/latest/userguide/license_migration.html
[build-system]
requires = ["setuptools>=77.0.3"]
build-backend = "setuptools.build_meta"

[project]
name = "hermes-brain"
version = "1.0.3"
description = "Persistent long-term memory for the Hermes AI agent ecosystem — turns Notion into a structured brain that never forgets."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.11,<3.14"
```

### Pattern 2: PyPI Trusted Publishing with OIDC and Attestations
**What:** Publishing to PyPI using cryptographic OpenID Connect tokens rather than long-lived API tokens.
**When to use:** Automated releases in GitHub Actions.
**Example:**
```yaml
# Source: https://docs.pypi.org/trusted-publishers/using-a-publisher
publish:
  name: Publish to PyPI
  needs: [build]
  runs-on: ubuntu-latest
  environment: pypi
  permissions:
    id-token: write
  steps:
    - name: Download distribution artifacts
      uses: actions/download-artifact@v4
      with:
        name: python-package-distributions
        path: dist/
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
```

### Pattern 3: Branch Ancestry & Version Consistency Guards
**What:** Strict validation scripts ensuring the pushed tag points to a commit on `main` and matches package metadata.
**When to use:** First step of release build job.
**Example:**
```bash
# Verify tag is an ancestor of main
git fetch origin main
git merge-base --is-ancestor HEAD origin/main || {
  echo "Error: Tag does not point to a commit on main branch." >&2
  exit 1
}

# Verify tag matches pyproject.toml and __version__
python3 -c '
import sys, tomllib, re

tag = sys.argv[1]
if not tag.startswith("v"):
    sys.exit(f"Tag {tag} missing leading v")
version = tag[1:]
if not re.match(r"^\d+\.\d+\.\d+([a-zA-Z0-9\.\-\+]+)?$", version):
    sys.exit(f"Tag version {version} is not valid SemVer/PEP 440")
with open("pyproject.toml", "rb") as f:
    pyproject = tomllib.load(f)
toml_ver = pyproject["project"]["version"]
if version != toml_ver:
    sys.exit(f"Tag version {version} does not match pyproject.toml version {toml_ver}")
print(f"Version consistency check passed: {version}")
' "${{ github.ref_name }}"
```

### Pattern 4: Post-Publish Smoke Test with CDN Propagation Retry
**What:** Polling PyPI with exponential backoff in a clean runner to confirm release availability and import viability.
**When to use:** Final verification step after PyPI upload.
**Example:**
```bash
VERSION="${GITHUB_REF_NAME#v}"
for attempt in $(seq 1 12); do
  echo "Attempt $attempt: checking for hermes-brain==$VERSION on PyPI..."
  if pip install --no-cache-dir "hermes-brain==$VERSION"; then
    echo "Package successfully installed."
    python -c "import notion_brain; print('Import OK:', notion_brain.__version__)"
    exit 0
  fi
  sleep 10
done
echo "Timeout waiting for hermes-brain==$VERSION to propagate on PyPI." >&2
exit 1
```

### Anti-Patterns to Avoid
- **Storing Static PyPI Tokens in GitHub Secrets:** Violates D-01/DIST-01 and security guidelines; leaks permit malicious package poisoning. Always use OIDC.
- **Publishing from Untested Tags:** Building and uploading immediately without running the full test matrix (`pytest`, `ruff`, `mypy`) across Python 3.11-3.13.
- **Ignoring Stale Build Artifacts:** Running `python -m build` or `twine upload dist/*` without running `rm -rf dist/ build/ *.egg-info` first. Old distributions will trigger PyPI immutable release collisions.
- **Permissive Workflow-Level OIDC Tokens:** Declaring `permissions: id-token: write` at the top level of `publish.yml` rather than scoping it exclusively to the `publish` job.
- **TestPyPI Complexity:** Introducing dual-target logic when the project decisions (D-18) explicitly dictate production-only publishing with strict pre-flight gates.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OIDC Token Minting | Custom bash `curl` to `https://pypi.org/_/oidc/mint-token` | `pypa/gh-action-pypi-publish@release/v1` | Handles token exchange, masking, error diagnosis, retry semantics, and PEP 740 digital attestations. |
| Wheel & Sdist Creation | Custom `setuptools` invocation or zip scripts | `python -m build` (PyPA `build`) | Correctly handles PEP 517 build isolation, metadata generation, and sdist/wheel formatting. |
| Metadata Validation | Custom regex parser for `PKG-INFO` | `twine check --strict` | Checks standard metadata fields, README rendering on PyPI, license syntax, and classifier validity. |
| GitHub Release Creation | Custom curl calls to GitHub REST API | Native `gh release create` | Native CLI handles auth, file attachments, and `--generate-notes` automatically. |
| Version Parsing | String splitting on `.` | Python stdlib `tomllib` + PEP 440 regex / `packaging.version` | Handles suffixes (`b1`, `rc1`, `post1`) without brittle indexing. |

## Runtime State Inventory

*Step 2.5: Runtime State Inventory is skipped — this phase is greenfield packaging metadata modernization and CI workflow authoring. No existing runtime databases, live service configs, OS-registered tasks, secrets, or installed packages require data migration.*

## Common Pitfalls

### Pitfall 1: Shallow Checkout Breaks Ancestry Check
**What goes wrong:** `git merge-base --is-ancestor HEAD origin/main` fails with `fatal: Not a valid object name origin/main` or reports FALSE.
**Why it happens:** Default `actions/checkout@v4` uses `fetch-depth: 1`, leaving out the git commit history needed to compute ancestry.
**How to avoid:** Configure `fetch-depth: 0` in `actions/checkout@v4` for the build job, followed by `git fetch origin main`.

### Pitfall 2: OIDC Permission Missing on Job Level
**What goes wrong:** `gh-action-pypi-publish` errors with `OpenID Connect token retrieval failed: missing id-token permission`.
**Why it happens:** GitHub Actions defaults to `id-token: none` unless explicitly granted.
**How to avoid:** Declare `permissions: { id-token: write, contents: read }` explicitly on the `publish` job.

### Pitfall 3: PyPI CDN Replication Delay in Smoke Test
**What goes wrong:** Post-publish smoke test fails immediately with `Could not find a version that satisfies the requirement hermes-brain==1.1.0`.
**Why it happens:** PyPI mirrors and Fastly CDN edges take 10 to 60 seconds to index and replicate new releases worldwide.
**How to avoid:** Implement a retry loop with `--no-cache-dir` and 10-second pauses (up to 2 minutes) in the smoke test job.

### Pitfall 4: Stale Artifact Re-upload Collision
**What goes wrong:** Maintainer running manual upload receives `HTTP 400 Bad Request: File already exists`.
**Why it happens:** PyPI releases are permanently immutable. If a previous version artifact remains in `dist/`, `twine upload dist/*` attempts to re-upload it.
**How to avoid:** Always execute `rm -rf dist/ build/ *.egg-info` prior to `python -m build`, and document this prominently in `docs/RELEASES.md`.

### Pitfall 5: Environment Name Mismatch in PyPI Configuration
**What goes wrong:** OIDC token exchange is rejected with `Invalid token: publisher not configured for this environment`.
**Why it happens:** PyPI trusted publisher configuration specifies environment `pypi`, but the GitHub Actions job uses a different name or omits `environment: pypi`.
**How to avoid:** Ensure exact agreement: `environment: pypi` in `publish.yml` and `pypi` in PyPI project settings.

## Code Examples

### 1. Modernized `pyproject.toml`
```toml
# Source: [VERIFIED: pyproject.toml:1-11] modernized per [CITED: setuptools.pypa.io/en/latest/userguide/license_migration.html]
[build-system]
requires = ["setuptools>=77.0.3"]
build-backend = "setuptools.build_meta"

[project]
name = "hermes-brain"
version = "1.0.3"
description = "Persistent long-term memory for the Hermes AI agent ecosystem — turns Notion into a structured brain that never forgets."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.11,<3.14"
classifiers = [
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]
dependencies = [
    "requests>=2.28",
]

[project.optional-dependencies]
dev = [
    "build==1.5.0",
    "mypy==2.3.0",
    "pre-commit>=4.1.0",
    "pytest==9.1.1",
    "pytest-cov==7.1.0",
    "ruff==0.16.0",
    "twine==6.2.0",
    "cryptography>=50.0.0",
]
```

### 2. GitHub Actions Publish Workflow (`.github/workflows/publish.yml`)
```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'

concurrency:
  group: publish
  cancel-in-progress: false

jobs:
  test:
    name: Test Matrix (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Set up uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - name: Install dependencies
        run: uv sync --locked --extra dev
      - name: Run unit test suite
        run: uv run --no-sync pytest -q

  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv sync --locked --extra dev
      - name: Ruff Check
        run: uv run --no-sync ruff check notion_brain tests
      - name: Mypy Check
        run: uv run --no-sync mypy notion_brain tests

  build:
    name: Build & Verify Distributions
    needs: [test, lint]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Verify Git Ancestry & Tag Match
        run: |
          git fetch origin main
          git merge-base --is-ancestor HEAD origin/main || {
            echo "Error: Tag commit is not reachable from main." >&2
            exit 1
          }
          python3 -c '
          import sys, tomllib, re
          tag = "${{ github.ref_name }}"
          if not tag.startswith("v"):
              sys.exit(f"Tag {tag} does not start with v")
          ver = tag[1:]
          if not re.match(r"^\d+\.\d+\.\d+([a-zA-Z0-9\.\-\+]+)?$", ver):
              sys.exit(f"Tag version {ver} is invalid SemVer/PEP 440")
          with open("pyproject.toml", "rb") as f:
              data = tomllib.load(f)
          toml_ver = data["project"]["version"]
          if ver != toml_ver:
              sys.exit(f"Tag version {ver} != pyproject.toml {toml_ver}")
          print(f"Tag {tag} matches pyproject.toml version {ver}")
          '

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Set up uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - run: uv sync --locked --extra dev

      - name: Clean stale artifacts
        run: rm -rf dist/ build/ *.egg-info

      - name: Build sdist and wheel
        run: uv run --no-sync python -m build

      - name: Strict twine check
        run: uv run --no-sync twine check --strict dist/*

      - name: Stash distribution artifacts
        uses: actions/upload-artifact@v4
        with:
          name: pypi-artifacts
          path: dist/
          retention-days: 1

  publish:
    name: Publish to PyPI via OIDC
    needs: [build]
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Download distribution artifacts
        uses: actions/download-artifact@v4
        with:
          name: pypi-artifacts
          path: dist/

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: dist/

  release:
    name: Create GitHub Release
    needs: [publish]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - name: Download distribution artifacts
        uses: actions/download-artifact@v4
        with:
          name: pypi-artifacts
          path: dist/
      - name: Create Release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create "${{ github.ref_name }}" dist/* \
            --title "Release ${{ github.ref_name }}" \
            --generate-notes

  smoke-test:
    name: Smoke Install Verification
    needs: [publish]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Verify PyPI Installation
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          for attempt in $(seq 1 12); do
            echo "Attempt $attempt: checking PyPI for hermes-brain==$VERSION..."
            if pip install --no-cache-dir "hermes-brain==$VERSION"; then
              echo "Package installed successfully from PyPI."
              python -c "import notion_brain; print('Import verified:', notion_brain.__version__)"
              exit 0
            fi
            sleep 10
          done
          echo "Failed to install hermes-brain==$VERSION from PyPI within timeout." >&2
          exit 1
```

### 3. Maintainer Runbook Pattern (`docs/RELEASES.md`)
```markdown
# Release Runbook: hermes-brain

## 1. Automated Release (Standard)
1. Ensure working directory is clean on `main` branch.
2. Update version in `pyproject.toml` and `notion_brain/__init__.py`.
3. Commit change: `git commit -am "chore: release vX.Y.Z"`.
4. Tag commit: `git tag vX.Y.Z`.
5. Push commit and tag: `git push origin main --tags`.
6. Monitor progress in GitHub Actions: `Publish to PyPI`.

## 2. One-Time PyPI Trusted Publisher Setup
Before pushing the first tag:
1. Log in to [pypi.org](https://pypi.org/).
2. Navigate to **Account Settings** -> **Publishing**.
3. Under **Add a publisher with a pending publisher**, choose **GitHub**:
   - PyPI Project Name: `hermes-brain`
   - Owner: `MNDL-27`
   - Repository name: `hermes-brain`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
4. In GitHub repository settings (`MNDL-27/hermes-brain`), verify or create the environment named `pypi`.

## 3. Emergency Manual Release (Fallback)
If GitHub Actions or OIDC token exchange is unavailable:
```bash
# 1. Clean workspace
rm -rf dist/ build/ *.egg-info

# 2. Build distributions
python -m build

# 3. Verify metadata strictly
twine check --strict dist/*

# 4. Upload using maintainer API token
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-AgEI..."
twine upload dist/*
```

## 4. Release Recovery
- If build/tests fail before upload: fix issue, commit, delete tag locally and remotely (`git push --delete origin vX.Y.Z`), re-tag, and re-push.
- If release uploaded with critical defect: PyPI prohibits re-uploading an existing version number. Immediately yank the release via the PyPI web UI (Project -> Releases -> Options -> Yank Release), then release a patch version (`vX.Y.Z+1`).
```

### 4. Offline Unit Test Pattern (`tests/test_packaging.py`)
```python
"""Tests verifying distribution packaging metadata and offline build integrity."""

from __future__ import annotations

import tomllib
from pathlib import Path

import notion_brain

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_metadata_conforms_to_pep_639() -> None:
    """Verify pyproject.toml uses SPDX string license and bumps setuptools floor."""
    pyproject_path = ROOT / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    # META-01: license is string "MIT", not dict table
    license_val = data.get("project", {}).get("license")
    assert isinstance(license_val, str), f"Expected license string, got {type(license_val)}"
    assert license_val == "MIT"

    # license-files declared
    license_files = data.get("project", {}).get("license-files")
    assert license_files == ["LICENSE"]

    # META-02: setuptools floor bumped
    build_requires = data.get("build-system", {}).get("requires", [])
    assert any("setuptools>=77.0.3" in req for req in build_requires), (
        f"Missing setuptools>=77.0.3 floor in build-system.requires: {build_requires}"
    )


def test_version_strings_match() -> None:
    """Verify notion_brain.__version__ exactly equals pyproject.toml version."""
    pyproject_path = ROOT / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    toml_version = data["project"]["version"]
    assert notion_brain.__version__ == toml_version
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `license = { text = "MIT" }` table in `pyproject.toml` | `license = "MIT"` SPDX expression (PEP 639) | `setuptools>=77.0.0` (Jan 2025) | Eliminates deprecation warnings; adheres to standard SPDX license identifiers in PyPI metadata. |
| Static `PYPI_API_TOKEN` stored in GitHub Secrets | OpenID Connect (OIDC) Trusted Publishing | PyPI GA (May 2023) | Short-lived tokens minted per workflow execution; eliminates credential theft risk and expiration management. |
| Custom PGP signing / detached signatures | Sigstore Digital Attestations (PEP 740) | PyPI (May 2024) | Cryptographic provenance automatically signed by GitHub and verifiable on PyPI without manual PGP key rings. |
| Single monolithic CI publish step | Multi-job gated release (`test` -> `build` -> `publish` -> `smoke`) | Best Practice | Guarantees uncompromised quality gate and prevents broken releases on partial test failures. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PyPI Trusted Publishing project name `hermes-brain` is available to owner `MNDL-27` | Standard Stack / Setup | If name is taken, package must be renamed or registered under a different namespace. Maintainer will discover during one-time setup. |

*All other packaging and workflow claims were verified against official documentation or directly executed via local test tools.*

## Open Questions (RESOLVED)

1. **First-time PyPI Registration Timing:** (RESOLVED — D-08 in CONTEXT.md locks documenting both paths)
   - What we know: Trusted Publishing allows registering a pending publisher for a new package before the first upload occurs.
   - What's unclear: Whether the maintainer prefers creating the project on PyPI manually beforehand or using the pending publisher workflow.
   - Recommendation: Document both paths in `docs/RELEASES.md` step-by-step so the maintainer can execute either without ambiguity.
   - **Resolution:** CONTEXT.md D-08 explicitly requires documenting both the manual project-creation path and the pending-publisher workflow. Plan 04-02 task "Author docs/RELEASES.md maintainer runbook (DIST-03)" implements this with two distinct setup sections.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime & Packaging | ✓ | 3.11, 3.12, 3.13 (via uv/system) | — |
| uv | Dependency Management | ✓ | 0.12.3 | Standard pip / virtualenv |
| git | Ancestry & Version Control | ✓ | 2.43.0 | — |
| gh | GitHub CLI (Releases) | ✓ | 2.45.0 (locally & in CI runners) | PyPI upload still succeeds; release note creation can fall back to GitHub UI |
| build | Distribution Builder | ✓ | 1.5.0 | `pip install build` |
| twine | Distribution Checker | ✓ | 6.2.0 | `pip install twine` |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 [VERIFIED: pyproject.toml:38] |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) [VERIFIED: pyproject.toml:48-52] |
| Quick run command | `uv run --no-sync pytest tests/test_packaging.py -q` |
| Full suite command | `uv run --no-sync pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| META-01 | SPDX `license = "MIT"` declared and table removed | Unit / Offline | `uv run --no-sync pytest tests/test_packaging.py::test_pyproject_metadata_conforms_to_pep_639` | ❌ Wave 0 |
| META-02 | Setuptools floor `>=77.0.3` and clean build / twine check | Unit / Offline | `uv run --no-sync pytest tests/test_packaging.py -k "metadata or build"` | ❌ Wave 0 |
| DIST-01 | OIDC Trusted Publishing without static secrets | CI Contract | Validated via `.github/workflows/publish.yml` syntax check & action lint | ❌ Wave 0 |
| DIST-02 | Separate build/publish jobs with `environment: pypi` | CI Contract | Validated via `.github/workflows/publish.yml` structure check | ❌ Wave 0 |
| DIST-03 | Documented manual twine runbook | Doc Audit | File existence and syntax check on `docs/RELEASES.md` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --no-sync pytest tests/test_packaging.py -q`
- **Per wave merge:** `uv run --no-sync pytest tests/test_packaging.py && uv run --no-sync ruff check . && uv run --no-sync mypy notion_brain tests`
- **Phase gate:** Offline packaging tests green, zero build deprecation warnings, `twine check --strict` passes, and CI workflow lint green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_packaging.py` — unit tests for META-01, META-02, and version synchronization
- [ ] `.github/workflows/publish.yml` — automated OIDC release workflow for DIST-01, DIST-02
- [ ] `docs/RELEASES.md` — maintainer runbook for DIST-03

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | OIDC token exchange with PyPI (`id-token: write`). Zero static tokens in repository secrets. |
| V3 Session Management | yes | Short-lived JWT minted dynamically by GitHub OIDC provider, scoped strictly to the publish job. |
| V4 Access Control | yes | GitHub environment `pypi` protection and branch ancestry check (`git merge-base --is-ancestor`) preventing releases from non-main branches. |
| V5 Input Validation | yes | Strict PEP 440 / SemVer regex validation of git tag strings before initiating builds. |
| V6 Cryptography | yes | Sigstore provenance attestations (PEP 740) attached to published wheel and sdist distributions. |

### Known Threat Patterns for Python Packaging

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Leaked PyPI Token | Information Disclosure / Spoofing | OIDC Trusted Publishing eliminates static PyPI API tokens from GitHub Secrets entirely. |
| Release from Malicious / Experimental Branch | Elevation of Privilege | Ancestry guard step (`git merge-base --is-ancestor HEAD origin/main`) halts build if tag commit is not on `main`. |
| Supply Chain Dependency Tampering | Tampering | Pinned dev dependencies in `pyproject.toml`, `--locked` uv installations in CI, and PyPI Sigstore attestations. |
| Broken / Corrupt Release Artifact | Repudiation / Denial of Service | Mandatory `twine check --strict` step fails build before upload; test matrix must pass before build job starts. |

## Sources

### Primary (HIGH confidence)
- `setuptools.pypa.io/en/latest/userguide/license_migration.html` — PEP 639 license declaration and `license-files` migration guide [CITED]
- `docs.pypi.org/trusted-publishers/using-a-publisher` — PyPI Trusted Publishing GitHub Actions configuration, environment specification, and OIDC token permissions [CITED]
- `docs.pypi.org/attestations/producing-attestations/` — PyPI Sigstore digital provenance attestations (PEP 740) generation guidelines [CITED]
- In-repo verification: `pyproject.toml:1-11`, `notion_brain/__init__.py:16`, `python -m build`, and `twine check --strict` output [VERIFIED]

### Secondary (MEDIUM confidence)
- `pypa/gh-action-pypi-publish` action inputs and release notes regarding automatic provenance generation and parameter structure.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Verified via PyPI registry, documentation, and local execution.
- Architecture: HIGH — Follows established PyPA OIDC publishing patterns and project decisions.
- Pitfalls: HIGH — Discovered through local test suite execution, Git shallow-clone dynamics, and PyPI CDN propagation characteristics.

**Research date:** 2026-09-22
**Valid until:** 2026-10-22 (30 days)
