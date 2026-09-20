"""Tests for the install.sh platform guard (PLAT-01, PLAT-02, PLAT-03).

Runs the real ``scripts/install.sh`` with a stub ``uname`` and asserts on
its output and exit code. No network, no package manager invocations —
the Darwin guard exits before any of that can happen.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.sh"

README_QUICKSTART_URL = "https://github.com/MNDL-27/hermes-brain#2-installation"


def run_install(
    uname_output: str, tmp_path: Path, monkeypatch: "object"
) -> subprocess.CompletedProcess[str]:
    """Run install.sh with a stubbed ``uname`` binary."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "uname"
    stub.write_text(f"#!/bin/sh\necho {uname_output}\n")
    stub.chmod(0o755)
    import os

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{Path(os.pathsep)}{env['PATH']}"
    return subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_darwin_prints_manual_setup_and_exits_zero(
    tmp_path: Path,
    monkeypatch: "object",
) -> None:
    """PLAT-01: Darwin prints manual instructions referencing README Quickstart and exits 0."""
    result = run_install("Darwin", tmp_path, monkeypatch)
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    combined = result.stdout
    assert "macOS detected" in combined
    assert README_QUICKSTART_URL in combined
    # Must NOT fail with Linux package manager errors or Hermes errors
    assert "apt-get" not in combined
    assert "Hermes agent not detected" not in combined


def test_linux_uname_continues_past_guard(
    tmp_path: Path,
    monkeypatch: "object",
) -> None:
    """PLAT-02: Linux uname does not trigger the Darwin guard or false-positive errors."""
    result = run_install("Linux", tmp_path, monkeypatch)
    combined = result.stdout
    # Should proceed past the guard (reaches Hermes check or beyond)
    assert "macOS detected" not in combined
    # Must not produce false-positive package manager errors
    assert "Unknown package manager" not in combined or result.returncode == 0
