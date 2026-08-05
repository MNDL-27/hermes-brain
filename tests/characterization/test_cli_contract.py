"""Characterize the command-line interface without contacting Notion."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from notion_brain import schema
from notion_brain import __main__ as cli


@pytest.fixture(autouse=True)
def _configured_offline_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_request(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("characterization tests must not call the Notion API")

    monkeypatch.setattr(cli.bootstrap.store, "get_api_key", lambda: "test-token")
    monkeypatch.setattr(cli.bootstrap.store.requests, "request", unexpected_request)


def test_python_module_help_is_callable() -> None:
    project_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.pop("NOTION_API_KEY", None)

    completed = subprocess.run(
        [sys.executable, "-m", "notion_brain", "--help"],
        cwd=project_root,
        env=environment,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "usage: notion_brain" in completed.stdout
    assert "--home" in completed.stdout
    for command in ("health", "url", "reset"):
        assert command in completed.stdout


def test_health_command_accepts_home_and_prints_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observed_homes: list[str] = []
    monkeypatch.setattr(cli.bootstrap, "_load_cache", lambda path: {})

    def health_report(home: str) -> str:
        observed_homes.append(home)
        return "offline health report"

    monkeypatch.setattr(cli.bootstrap, "health_report", health_report)

    exit_code = cli.main(["--home", str(tmp_path), "health"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "offline health report\n"
    assert captured.err == ""
    assert observed_homes == [str(tmp_path)]


def test_url_command_supports_all_database_urls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observed: list[tuple[str, bool]] = []

    def get_url(home: str, db: bool = False) -> str:
        observed.append((home, db))
        return "https://www.notion.so/parent\nhttps://www.notion.so/memory"

    monkeypatch.setattr(cli.bootstrap, "get_url", get_url)

    exit_code = cli.main(["--home", str(tmp_path), "url", "--all"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == (
        "https://www.notion.so/parent\nhttps://www.notion.so/memory\n"
    )
    assert captured.err == ""
    assert observed == [(str(tmp_path), True)]


def test_reset_dry_run_parses_only_without_touching_notion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observed: dict[str, Any] = {}

    def reset_databases(
        home: str, *, only: set[str], dry_run: bool, force: bool
    ) -> list[str]:
        observed.update(
            home=home,
            only=only,
            dry_run=dry_run,
            force=force,
        )
        return ["memory", "tasks"]

    monkeypatch.setattr(cli.bootstrap, "reset_databases", reset_databases)

    exit_code = cli.main(
        [
            "--home",
            str(tmp_path),
            "reset",
            "--only",
            "memory,tasks",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "would reset 2 DB(s): memory, tasks\n"
    assert captured.err == ""
    assert observed == {
        "home": str(tmp_path),
        "only": {"memory", "tasks"},
        "dry_run": True,
        "force": False,
    }
    assert observed["only"] <= set(schema.DATABASES)
