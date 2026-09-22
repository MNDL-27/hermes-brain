# Phase 04: Build Metadata Modernization & PyPI Publishing - Pattern Map

**Mapped:** 2026-09-22
**Files analyzed:** 5
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pyproject.toml` | config | transform | `pyproject.toml` | exact |
| `.github/workflows/publish.yml` | config | event-driven | `.github/workflows/ci.yml` | exact |
| `tests/test_packaging.py` | test | batch | `tests/test_install_guard.py` | role-match |
| `docs/RELEASES.md` | config | request-response | `docs/troubleshooting.md` | role-match |
| `notion_brain/__init__.py` | model | transform | `notion_brain/__init__.py` | exact |

---

## Pattern Assignments

### `pyproject.toml` (config, transform)

**Analog:** `pyproject.toml`

**Current build-system declaration** (lines 1-3):
```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```

**Target PEP 639 pattern**:
Bump build floor to `setuptools>=77.0.3` to support PEP 639 string syntax and remove deprecated license table:
```toml
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

**Dependency management pattern** (lines 33-43):
Dev tools pinned in `[project.optional-dependencies] dev`, installed via `uv sync --locked --extra dev`:
```toml
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

---

### `.github/workflows/publish.yml` (config, event-driven)

**Analog:** `.github/workflows/ci.yml`

**Trigger and permissions pattern** (`.github/workflows/ci.yml` lines 3-10):
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
```

**Publish trigger adaptation**:
Trigger on `v*` tags with concurrency serialize group:
```yaml
on:
  push:
    tags:
      - 'v*'

concurrency:
  group: publish
  cancel-in-progress: false
```

**Test matrix pattern** (`.github/workflows/ci.yml` lines 13-34):
```yaml
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Set up uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - name: Install locked dependencies
        run: uv sync --locked --extra dev
      - name: Run tests
        run: uv run --no-sync pytest -q
```

**Lint and static analysis pattern** (`.github/workflows/ci.yml` lines 54-71):
```yaml
  lint:
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
      - name: Lint current package and tests
        run: uv run --no-sync ruff check notion_brain tests
      - name: Type-check current package and tests
        run: uv run --no-sync mypy notion_brain tests
```

**Build & verify distribution pattern** (`.github/workflows/ci.yml` lines 72-87):
```yaml
  package:
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
      - name: Build distributions
        run: uv run --no-sync python -m build
      - name: Validate distribution metadata
        run: uv run --no-sync twine check dist/*
```

**Publish job adaptation (OIDC & PyPI Environment)**:
```yaml
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
```

---

### `tests/test_packaging.py` (test, batch)

**Analog:** `tests/test_install_guard.py` (lines 8-16) and `tests/test_config_schema.py` (lines 1-16)

**Imports & path resolution pattern**:
```python
from __future__ import annotations

from pathlib import Path
import tomllib

import notion_brain

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
```

**Metadata assertion pattern**:
```python
def test_pyproject_metadata_conforms_to_pep_639() -> None:
    """Verifies pyproject.toml license is SPDX string and build floor is setuptools>=77.0.3."""
    with PYPROJECT_PATH.open("rb") as f:
        data = tomllib.load(f)

    # META-01: license string
    license_val = data.get("project", {}).get("license")
    assert isinstance(license_val, str), f"Expected license string, got {type(license_val)}"
    assert license_val == "MIT"

    # license-files declared
    assert data.get("project", {}).get("license-files") == ["LICENSE"]

    # META-02: setuptools floor bumped
    build_requires = data.get("build-system", {}).get("requires", [])
    assert any("setuptools>=77.0.3" in req for req in build_requires), (
        f"Missing setuptools>=77.0.3 floor in build-system.requires: {build_requires}"
    )


def test_version_strings_match() -> None:
    """Verifies notion_brain.__version__ equals pyproject.toml version."""
    with PYPROJECT_PATH.open("rb") as f:
        data = tomllib.load(f)

    toml_ver = data["project"]["version"]
    assert notion_brain.__version__ == toml_ver
```

**Subprocess / build verification pattern** (analogous to `run_install` in `tests/test_install_guard.py:19-38`):
```python
def test_offline_build_and_twine_check(tmp_path: Path) -> None:
    """Verifies build and twine check execute cleanly without deprecation warnings."""
    # Runs python -m build --outdir and twine check --strict in isolated tmp_path
    ...
```

---

### `docs/RELEASES.md` (config, request-response)

**Analog:** `docs/troubleshooting.md`

**Structure pattern** (lines 1-28):
Numbered operational walkthrough with prerequisites, shell snippets, cause/fix diagnosis, and recovery procedures:
```markdown
# Release Runbook: hermes-brain

Procedures for releasing `hermes-brain` to PyPI via automated GitHub Actions OIDC Trusted Publishing and manual fallback.

## 1. Automated Release (Standard)

1. Ensure working directory on `main` branch is clean.
2. Bump version in `pyproject.toml` and `notion_brain/__init__.py`.
3. Commit release:
   ```bash
   git commit -am "chore: release vX.Y.Z"
   ```
4. Tag commit:
   ```bash
   git tag vX.Y.Z
   ```
5. Push commit and tag:
   ```bash
   git push origin main --tags
   ```

## 2. One-Time PyPI Trusted Publisher Setup
...

## 3. Emergency Manual Release (Fallback)
```bash
rm -rf dist/ build/ *.egg-info
python -m build
twine check --strict dist/*
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-..."
twine upload dist/*
```

## 4. Release Recovery & Troubleshooting
...
```

---

### `notion_brain/__init__.py` (model, transform)

**Analog:** `notion_brain/__init__.py`

**Version export pattern** (lines 11-17):
```python
from __future__ import annotations

import json
import os

__version__ = "1.0.3"
```
Must maintain string equality with `[project] version` in `pyproject.toml`.

---

## Shared Patterns

### Runner & Dependency Bootstrap
**Source:** `.github/workflows/ci.yml:21-32, 75-82`
**Apply to:** All jobs in `.github/workflows/publish.yml`
```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- uses: astral-sh/setup-uv@v6
  with:
    enable-cache: true
- run: uv sync --locked --extra dev
```

### Python Type Hints and Module Header
**Source:** `notion_brain/__init__.py:11`, `tests/test_config_schema.py:1`
**Apply to:** All Python test and source modules (`tests/test_packaging.py`)
```python
from __future__ import annotations
```

### Repository Root Resolution
**Source:** `tests/test_install_guard.py:13`
**Apply to:** `tests/test_packaging.py`
```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
```

### Clean Artifact Generation Gate
**Source:** `pyproject.toml:35, 41`, `.github/workflows/ci.yml:83-86`
**Apply to:** Build steps in `.github/workflows/publish.yml` and `docs/RELEASES.md`
```bash
rm -rf dist/ build/ *.egg-info
python -m build
twine check --strict dist/*
```

---

## No Analog Found

None. All files have direct or role-matched analogs in the codebase.

---

## Metadata

**Analog search scope:** `pyproject.toml`, `.github/workflows/`, `tests/`, `docs/`, `notion_brain/`
**Files scanned:** 12
**Pattern extraction date:** 2026-09-22
