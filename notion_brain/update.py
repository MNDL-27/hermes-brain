"""Update drift detection and per-environment upgrade-command generation.

Public surface: `parse_semver`, `compare_versions`, `detect_install_mode`,
`build_upgrade_command`, `check_for_update`, `format_human`, `format_json`.

Strictly detect+instruct. Never runs `pip install`, `git pull`, or any other
mutation of the running environment — see UPD-05 in REQUIREMENTS.md.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_DEFAULT = "MNDL-27/hermes-brain"

# Pre-release rank ordering. Lower index = earlier (alpha), higher = closer to release.
# Release itself is encoded separately as the empty pre-release tuple — Python's
# tuple ordering puts () below any non-empty tuple, which is what we want.
_PRE_RANK: dict[str, int] = {"a": 0, "b": 1, "rc": 2}

_VERSION_RE = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$",
    re.IGNORECASE,
)


def parse_semver(version: str) -> tuple:
    """Return a comparable tuple for a SemVer-ish version string.

    Encoding: (MAJOR, MINOR, PATCH, pre_rank_or_inf).
    A release (no pre-release suffix) gets `float('inf')` for the pre slot so
    any pre-release of the same base sorts strictly below it. Pre-releases
    rank as a tuple `(rank, n)` where rank is `_PRE_RANK[kind]` and `n` is
    the integer suffix.

    `1.10.0` -> `(10, 10, 0, inf)` and `(1, 9, 0, inf)` -> correct ordering.
    `1.1.0`  -> `(1, 1, 0, inf)`  and `(1, 1, 0, (1, 1))` for `1.1.0b1` -> correct.
    """
    m = _VERSION_RE.match(version.strip())
    if not m:
        raise ValueError(f"not a valid SemVer version: {version!r}")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    kind = m.group(4)
    n = int(m.group(5)) if m.group(5) else 0
    if kind is None:
        pre_slot: tuple = (float("inf"),)
    else:
        pre_slot = (_PRE_RANK[kind.lower()], n)
    return (major, minor, patch, pre_slot)


def compare_versions(a: str, b: str) -> int:
    """Return -1, 0, or 1 like `cmp`. Pre-release < release of same base."""
    pa, pb = parse_semver(a), parse_semver(b)
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def detect_install_mode(repo_dir: Path | None = None) -> str:
    """Detect how `hermes-brain` is currently installed.

    Returns one of: 'git_clone', 'uv', 'pip_user', 'pip_venv', 'unknown'.
    Never raises — any error path returns 'unknown'.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "show", "hermes-brain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return "unknown"
        info: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                info[k.strip().lower()] = v.strip()
        location = info.get("location", "")
        editable = info.get("editable project location", "")
        if not location:
            return "unknown"
        if editable and repo_dir is not None:
            try:
                if Path(editable).resolve() == Path(repo_dir).resolve():
                    return "git_clone"
            except OSError:
                pass
        loc = location.replace("\\", "/")
        home = str(Path.home()).replace("\\", "/")
        if "/uv/" in loc or "/.cache/uv/" in loc:
            return "uv"
        if loc.startswith(home + "/.local/lib/") or "/.local/lib/" in loc:
            return "pip_user"
        # Anything inside a venv site-packages (no /site-packages/ heuristic — venvs can sit anywhere).
        if loc.endswith("/site-packages") or loc.endswith("/site-packages/"):
            return "pip_venv"
        return "pip_venv"
    except Exception:
        return "unknown"


def build_upgrade_command(
    mode: str,
    target_version: str,
    *,
    repo_dir: Path | None = None,
) -> str:
    """Return a copy-pasteable upgrade command for the detected mode."""
    if mode == "uv":
        return f"uv pip install --upgrade hermes-brain=={target_version}"
    if mode == "pip_user":
        return f"pip install --user --upgrade hermes-brain=={target_version}"
    if mode == "git_clone":
        rd = str(repo_dir) if repo_dir else "<repo_dir>"
        return (
            f"git -C {rd} fetch --tags && "
            f"git -C {rd} checkout v{target_version} && "
            f"{sys.executable} -m pip install --upgrade --force-reinstall {rd}"
        )
    # pip_venv or unknown — fall back to plain pip
    return f"pip install --upgrade hermes-brain=={target_version}"


def check_for_update(*, repo_dir: Path | None = None) -> dict[str, Any]:
    """Detect drift between installed and latest release.

    Returns a dict with: `current`, `latest`, `drift`, `install_mode`,
    `upgrade_command`, `release_url`, `error`. Never mutates the environment.
    """
    from . import __version__ as current_ver
    from . import bootstrap

    result: dict[str, Any] = {
        "current": current_ver,
        "latest": None,
        "drift": False,
        "install_mode": "unknown",
        "upgrade_command": "",
        "release_url": "",
        "error": None,
    }
    try:
        latest = bootstrap._find_latest_tag()
    except Exception as exc:  # noqa: BLE001 — surfacing as field, not raising
        result["error"] = f"network: {type(exc).__name__}"
        return result

    if latest:
        result["latest"] = latest
        try:
            result["drift"] = compare_versions(latest, current_ver) > 0
        except ValueError:
            result["drift"] = latest != current_ver

    mode = detect_install_mode(repo_dir=repo_dir)
    result["install_mode"] = mode
    if result["drift"] and result["latest"]:
        result["upgrade_command"] = build_upgrade_command(mode, result["latest"], repo_dir=repo_dir)
        result["release_url"] = (
            f"https://github.com/{_REPO_DEFAULT}/releases/tag/v{result['latest']}"
        )
    return result


def format_human(result: dict[str, Any]) -> str:
    """Format the check result for human reading."""
    lines: list[str] = []
    cur = result.get("current", "?")
    latest = result.get("latest")
    mode = result.get("install_mode", "unknown")
    lines.append(f"installed: {cur}")
    if latest is None:
        if result.get("error"):
            lines.append(f"latest:    unknown ({result['error']})")
        else:
            lines.append("latest:    unknown")
    elif result.get("drift"):
        lines.append(f"latest:    {latest}  (UPDATE AVAILABLE)")
    else:
        lines.append(f"latest:    {latest}  (up to date)")
    lines.append(f"install:   {mode}")
    cmd = result.get("upgrade_command") or ""
    if cmd:
        lines.append(f"upgrade:   {cmd}")
    url = result.get("release_url") or ""
    if url:
        lines.append(f"release:   {url}")
    return "\n".join(lines)


def format_json(result: dict[str, Any]) -> str:
    """Serialize the check result as JSON."""
    return json.dumps(result, indent=2, sort_keys=True)
