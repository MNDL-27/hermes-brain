"""Offline unit tests for notion_brain.update (Phase 05).

Covers: SemVer parsing + integer-tuple ranking, pre-release ordering,
per-mode upgrade command generation, install-mode detection, JSON payload
shape, CLI exit codes for `--check` and `--check --json`, and the
UPD-05 no-mutation guarantee.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notion_brain import __main__ as cli  # noqa: E402
from notion_brain import update as update_mod  # noqa: E402

# ---------- SemVer parsing & comparison (UPD-03) ----------


def test_semver_integer_tuple_ranking():
    """1.10.0 must sort above 1.9.0 under tuple comparison (UPD-03)."""
    assert update_mod.parse_semver("1.10.0") > update_mod.parse_semver("1.9.0")
    assert update_mod.parse_semver("1.99.0") > update_mod.parse_semver("1.10.0")


def test_semver_release_above_prerelease():
    """Release ranks above any pre-release of the same base (UPD-03)."""
    assert update_mod.parse_semver("1.1.0") > update_mod.parse_semver("1.1.0b1")
    assert update_mod.parse_semver("1.1.0") > update_mod.parse_semver("1.1.0a1")
    assert update_mod.parse_semver("1.1.0") > update_mod.parse_semver("1.1.0rc1")


def test_semver_prerelease_ordering():
    """Pre-releases rank: a < b < rc, and numeric suffixes rank within."""
    assert update_mod.parse_semver("1.0.0a1") < update_mod.parse_semver("1.0.0b1")
    assert update_mod.parse_semver("1.0.0b1") < update_mod.parse_semver("1.0.0rc1")
    assert update_mod.parse_semver("1.0.0rc1") < update_mod.parse_semver("1.0.0")
    assert update_mod.parse_semver("1.0.0rc1") < update_mod.parse_semver("1.0.0rc2")


def test_semver_rejects_garbage():
    with pytest.raises(ValueError):
        update_mod.parse_semver("not-a-version")
    with pytest.raises(ValueError):
        update_mod.parse_semver("1.0")


def test_compare_versions_reflexive_and_antisymmetric():
    assert update_mod.compare_versions("1.0.0", "1.0.0") == 0
    assert update_mod.compare_versions("2.0.0", "1.0.0") == 1
    assert update_mod.compare_versions("1.0.0", "2.0.0") == -1
    assert update_mod.compare_versions("1.10.0", "1.9.0") == 1
    assert update_mod.compare_versions("1.0.0", "1.0.0b1") == 1


# ---------- Upgrade commands (UPD-02) ----------


def test_build_upgrade_command_uv():
    assert (
        update_mod.build_upgrade_command("uv", "1.2.3")
        == "uv pip install --upgrade hermes-brain==1.2.3"
    )


def test_build_upgrade_command_pip_venv():
    assert (
        update_mod.build_upgrade_command("pip_venv", "1.2.3")
        == "pip install --upgrade hermes-brain==1.2.3"
    )


def test_build_upgrade_command_pip_user():
    assert (
        update_mod.build_upgrade_command("pip_user", "1.2.3")
        == "pip install --user --upgrade hermes-brain==1.2.3"
    )


def test_build_upgrade_command_git_clone():
    cmd = update_mod.build_upgrade_command("git_clone", "1.2.3", repo_dir=Path("/tmp/repo"))
    assert cmd.startswith("git -C /tmp/repo fetch")
    assert "v1.2.3" in cmd


def test_build_upgrade_command_unknown_falls_back_to_pip():
    """Unknown mode returns the safe plain pip command (UPD-05: instruct only)."""
    cmd = update_mod.build_upgrade_command("unknown", "1.2.3")
    assert cmd == "pip install --upgrade hermes-brain==1.2.3"


# ---------- Install-mode detection ----------


def _pip_show_stdout(location: str, *, editable: str = "") -> str:
    """Build a `pip show` shaped stdout block."""
    lines = [
        "Name: hermes-brain",
        f"Location: {location}",
        "Version: 1.0.3",
    ]
    if editable:
        lines.append(f"Editable project location: {editable}")
    return "\n".join(lines)


def test_detect_install_mode_uv_when_location_under_uv_cache():
    out = _pip_show_stdout("/home/u/.cache/uv/archive-v0/venv/lib/python3.11/site-packages")
    with patch.object(
        subprocess,
        "run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=out, stderr=""),
    ):
        assert update_mod.detect_install_mode() == "uv"


def test_detect_install_mode_pip_user_when_location_under_local():
    home = str(Path.home())
    out = _pip_show_stdout(f"{home}/.local/lib/python3.11/site-packages")
    with patch.object(
        subprocess,
        "run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=out, stderr=""),
    ):
        assert update_mod.detect_install_mode() == "pip_user"


def test_detect_install_mode_git_clone_when_editable_matches_repo(tmp_path):
    repo = tmp_path / "hermes-brain"
    repo.mkdir()
    out = _pip_show_stdout(str(repo / "src"), editable=str(repo))
    with patch.object(
        subprocess,
        "run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=out, stderr=""),
    ):
        assert update_mod.detect_install_mode(repo_dir=repo) == "git_clone"


def test_detect_install_mode_pip_venv_default():
    out = _pip_show_stdout("/opt/hermes/venv/lib/python3.11/site-packages")
    with patch.object(
        subprocess,
        "run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=out, stderr=""),
    ):
        assert update_mod.detect_install_mode() == "pip_venv"


def test_detect_install_mode_unknown_when_pip_show_fails():
    """Any failure path returns 'unknown' (never raises)."""

    def _boom(*args, **kwargs):
        raise FileNotFoundError("pip not available")

    with patch.object(subprocess, "run", side_effect=_boom):
        assert update_mod.detect_install_mode() == "unknown"


# ---------- check_for_update ----------


def test_check_for_update_handles_network_failure():
    """A network error from bootstrap._find_latest_tag must not propagate."""
    from notion_brain import bootstrap

    with patch.object(bootstrap, "_find_latest_tag", side_effect=ConnectionError("offline")):
        result = update_mod.check_for_update()
    assert result["latest"] is None
    assert result["drift"] is False
    assert (
        "offline" in (result.get("error") or "").lower()
        or "network" in (result.get("error") or "").lower()
        or result.get("error") is not None
    )


def test_check_for_update_no_mutation_when_drift_detected():
    """UPD-05: check_for_update must never invoke pip or git subprocesses."""
    from notion_brain import bootstrap

    def _fail_on_subprocess(*args, **kwargs):
        raise AssertionError(
            f"UPD-05 violation: check_for_update invoked subprocess {args[0] if args else '?'}"
        )

    with (
        patch.object(subprocess, "run", side_effect=_fail_on_subprocess),
        patch.object(bootstrap, "_find_latest_tag", return_value="999.0.0"),
    ):
        result = update_mod.check_for_update()
    assert result["latest"] == "999.0.0"
    assert result["drift"] is True
    # upgrade_command must be a plain string (the printed instruction), not an executed call
    assert isinstance(result["upgrade_command"], str)
    assert result["upgrade_command"]  # non-empty when drift


def test_check_for_update_no_mutation_when_current():
    """UPD-05: also true on the happy path (current version)."""
    from notion_brain import bootstrap

    def _fail_on_subprocess(*args, **kwargs):
        raise AssertionError("subprocess invoked from check_for_update")

    with (
        patch.object(subprocess, "run", side_effect=_fail_on_subprocess),
        patch.object(bootstrap, "_find_latest_tag", return_value="1.0.3"),
    ):
        result = update_mod.check_for_update()
    assert result["drift"] is False
    assert result["upgrade_command"] == ""


# ---------- format_json ----------


def test_format_json_is_parseable_and_round_trips():
    sample = {
        "current": "1.0.3",
        "latest": "1.2.3",
        "drift": True,
        "install_mode": "uv",
        "upgrade_command": "uv pip install --upgrade hermes-brain==1.2.3",
        "release_url": "https://github.com/MNDL-27/hermes-brain/releases/tag/v1.2.3",
        "error": None,
    }
    out = update_mod.format_json(sample)
    parsed = json.loads(out)
    assert parsed == sample


def test_format_human_includes_drift_line_when_drift():
    result = {
        "current": "1.0.3",
        "latest": "1.2.3",
        "drift": True,
        "install_mode": "uv",
        "upgrade_command": "uv pip install --upgrade hermes-brain==1.2.3",
        "release_url": "https://github.com/MNDL-27/hermes-brain/releases/tag/v1.2.3",
        "error": None,
    }
    out = update_mod.format_human(result)
    assert "1.0.3" in out
    assert "1.2.3" in out
    assert "UPDATE AVAILABLE" in out
    assert "uv pip install" in out
    assert "releases/tag/v1.2.3" in out


def test_format_human_says_up_to_date_when_no_drift():
    result = {
        "current": "1.0.3",
        "latest": "1.0.3",
        "drift": False,
        "install_mode": "pip_venv",
        "upgrade_command": "",
        "release_url": "",
        "error": None,
    }
    out = update_mod.format_human(result)
    assert "up to date" in out
    assert "UPDATE AVAILABLE" not in out


# ---------- CLI: --check and --json exit codes (UPD-04) ----------


def _patch_check(current_ver: str, latest: str | None) -> None:
    """Monkeypatch check_for_update to return a deterministic result."""
    from notion_brain import update as u

    def _stub(*, repo_dir=None):
        drift = bool(latest) and latest != current_ver
        return {
            "current": current_ver,
            "latest": latest,
            "drift": drift,
            "install_mode": "unknown",
            "upgrade_command": "pip install --upgrade hermes-brain==" + latest if drift else "",
            "release_url": (
                f"https://github.com/MNDL-27/hermes-brain/releases/tag/v{latest}"
                if drift and latest
                else ""
            ),
            "error": None,
        }

    patcher = patch.object(u, "check_for_update", side_effect=_stub)
    patcher.start()
    # Store on the module so we can stop later (pytest fixtures handle this via finalizer normally)
    _patch_check._patcher = patcher  # type: ignore[attr-defined]


def test_cmd_update_check_exits_0_when_current(capsys):
    _patch_check(current_ver="1.0.3", latest="1.0.3")
    try:
        rc = cli.main(["update", "--check"])
    finally:
        _patch_check._patcher.stop()  # type: ignore[attr-defined]
    assert rc == 0
    out = capsys.readouterr().out
    assert "up to date" in out


def test_cmd_update_check_exits_2_when_drift(capsys):
    _patch_check(current_ver="1.0.3", latest="1.2.3")
    try:
        rc = cli.main(["update", "--check"])
    finally:
        _patch_check._patcher.stop()  # type: ignore[attr-defined]
    assert rc == 2
    out = capsys.readouterr().out
    assert "UPDATE AVAILABLE" in out


def test_cmd_update_check_json_exits_2_and_prints_json(capsys):
    _patch_check(current_ver="1.0.3", latest="1.2.3")
    try:
        rc = cli.main(["update", "--check", "--json"])
    finally:
        _patch_check._patcher.stop()  # type: ignore[attr-defined]
    assert rc == 2
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["drift"] is True
    assert parsed["current"] == "1.0.3"
    assert parsed["latest"] == "1.2.3"


def test_cmd_update_check_json_exits_0_when_current(capsys):
    _patch_check(current_ver="1.0.3", latest="1.0.3")
    try:
        rc = cli.main(["update", "--check", "--json"])
    finally:
        _patch_check._patcher.stop()  # type: ignore[attr-defined]
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["drift"] is False


def test_cmd_update_no_flags_does_not_invoke_pip_or_git(capsys, monkeypatch):
    """Bare `update` must still be detect+instruct only (UPD-05)."""
    from notion_brain import update as u

    def _fail(*args, **kwargs):
        raise AssertionError("subprocess invoked from bare update")

    captured: dict = {}

    def _stub(*, repo_dir=None):
        captured["called"] = True
        return {
            "current": "1.0.3",
            "latest": "1.2.3",
            "drift": True,
            "install_mode": "uv",
            "upgrade_command": "uv pip install --upgrade hermes-brain==1.2.3",
            "release_url": "https://github.com/MNDL-27/hermes-brain/releases/tag/v1.2.3",
            "error": None,
        }

    monkeypatch.setattr(u, "check_for_update", _stub)
    monkeypatch.setattr(subprocess, "run", _fail)
    rc = cli.main(["update"])
    assert rc == 2
    assert captured.get("called") is True
