"""Offline packaging tests for META-01, META-02, version sync, and clean build.

Validates PEP 639 SPDX metadata, setuptools>=77.0.3 floor, version consistency,
and zero-deprecation offline build + twine check.

NOTE: test_offline_build_and_twine_check needs real network — PEP517 build
isolation fetches setuptools/wheel from PyPI — so it is marked
@pytest.mark.network and deselected by default. Run it with:
``uv run pytest -m network``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_pyproject_metadata_conforms_to_pep_639() -> None:
    """META-01: license is str 'MIT'; license-files == ['LICENSE']; setuptools>=77.0.3."""
    data = tomllib.load(PYPROJECT.open("rb"))

    license_val = data["project"]["license"]
    assert isinstance(license_val, str), f"license is {type(license_val)}, expected str"
    assert license_val == "MIT", f"license is {license_val!r}, expected 'MIT'"

    # license-files bundles the LICENSE file
    assert data["project"]["license-files"] == ["LICENSE"], (
        f"license-files is {data['project']['license-files']!r}, expected ['LICENSE']"
    )

    # Build-system floor is setuptools>=77.0.3 (exact token)
    build_requires = data["build-system"]["requires"]
    assert any(req == "setuptools>=77.0.3" for req in build_requires), (
        f"build-system.requires missing 'setuptools>=77.0.3': {build_requires!r}"
    )


def test_no_legacy_license_table() -> None:
    """Regression guard: [project] does NOT contain legacy dict license table."""
    data = tomllib.load(PYPROJECT.open("rb"))

    license_val = data["project"].get("license")
    assert isinstance(license_val, str), (
        f"license is {type(license_val).__name__}, expected str (not deprecated table)"
    )

    # Extra: no TOML [[project.license]] table with "text" key
    for key, val in data["project"].items():
        assert not (isinstance(val, dict) and "text" in val), (
            f"project.{key} is a dict with 'text' key — looks like legacy license table"
        )


def test_version_strings_match() -> None:
    """Version in notion_brain.__version__ equals pyproject.toml [project].version exactly."""
    import notion_brain

    data = tomllib.load(PYPROJECT.open("rb"))
    pyproject_version = data["project"]["version"]
    assert notion_brain.__version__ == pyproject_version, (
        f"notion_brain.__version__ ({notion_brain.__version__}) != "
        f"pyproject.toml version ({pyproject_version})"
    )


@pytest.mark.network
def test_offline_build_and_twine_check(tmp_path: Path) -> None:
    """META-02: python -m build produces clean artifacts; twine check --strict passes."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    env = {**os.environ, "PYTHONNOUSERSITE": "1"}
    build_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--wheel",
            "--outdir",
            str(dist_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert build_result.returncode == 0, (
        f"python -m build failed (exit {build_result.returncode}):\n"
        f"stdout:\n{build_result.stdout}\nstderr:\n{build_result.stderr}"
    )

    stderr_lower = build_result.stderr.lower()
    assert "deprecationwarning" not in stderr_lower, (
        f"DeprecationWarning in build stderr:\n{build_result.stderr}"
    )
    assert "deprecated" not in stderr_lower, (
        f"'deprecated' found in build stderr:\n{build_result.stderr}"
    )

    artifacts = sorted(dist_dir.iterdir())
    names = [artifact.name for artifact in artifacts]
    assert len(artifacts) == 2, f"Expected 2 artifacts in {dist_dir}, got {len(artifacts)}: {names}"
    wheels = [artifact for artifact in artifacts if artifact.name.endswith(".whl")]
    sdists = [artifact for artifact in artifacts if artifact.name.endswith(".tar.gz")]
    assert len(wheels) == 1, f"Expected 1 wheel, got {len(wheels)}"
    assert len(sdists) == 1, f"Expected 1 sdist, got {len(sdists)}"

    twine_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "twine",
            "check",
            "--strict",
            *[str(artifact) for artifact in artifacts],
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert twine_result.returncode == 0, (
        f"twine check --strict failed (exit {twine_result.returncode}):\n"
        f"stdout:\n{twine_result.stdout}\nstderr:\n{twine_result.stderr}"
    )
    assert "Checking distribution" in twine_result.stdout or "Checking" in twine_result.stdout, (
        f"twine check did not report checking the distributions:\n{twine_result.stdout}"
    )
