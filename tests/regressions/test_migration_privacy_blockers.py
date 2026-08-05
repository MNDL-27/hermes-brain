"""Strict regression contracts for migration and privacy blockers."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import notion_brain.__main__ as cli
from notion_brain import NotionBrainProvider, bootstrap
from notion_brain import schema as S


MIGRATION_XFAIL = pytest.mark.xfail(
    strict=True,
    raises=Exception,
    reason="Workstream 6: non-destructive migration is not implemented",
)
PRIVACY_XFAIL = pytest.mark.xfail(
    strict=True,
    raises=Exception,
    reason="Workstream 4: centralized privacy processing is not implemented",
)


def _notion_database(key: str, database_id: str) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for name, spec in bootstrap._PROPS[key].items():
        property_type = next(iter(spec))
        properties[name] = {
            "type": property_type,
            property_type: deepcopy(spec[property_type]),
        }
    return {"id": database_id, "properties": properties}


def _mismatched_database(key: str, database_id: str) -> dict[str, Any]:
    database = _notion_database(key, database_id)
    database["properties"]["Status"]["status"]["options"].append(
        {"name": "legacy-status"}
    )
    return database


def _write_complete_cache(tmp_path: Path, *, schema_version: int) -> tuple[Path, dict[str, Any]]:
    cached = {
        "parent_page_id": "parent-id",
        "schema_version": schema_version,
        **{f"db_{key}": f"original-{key}" for key in S.DATABASES},
    }
    cache_path = tmp_path / S.CACHE_FILE
    cache_path.write_text(json.dumps(cached), encoding="utf-8")
    return cache_path, cached


def _database_properties() -> dict[str, Any]:
    return {
        "title": {"type": "title", "title": {}},
        "Domain": {"type": "select", "select": {}},
        "Status": {
            "type": "status",
            "status": {
                "options": [
                    {"name": "active"},
                    {"name": "done"},
                    {"name": "needs_review"},
                ]
            },
        },
        "Tags": {"type": "multi_select", "multi_select": {}},
        "Confidence": {"type": "select", "select": {}},
        "Kind": {"type": "select", "select": {}},
        "Entities": {"type": "rich_text", "rich_text": {}},
    }


def _initialized_provider(tmp_path: Path) -> NotionBrainProvider:
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._session_id = "session-regression"
    provider._parent_page_id = "parent-id"
    provider._db_ids = {key: f"db-{key}" for key in S.DATABASES}
    return provider


@MIGRATION_XFAIL
def test_startup_does_not_reset_databases_for_stale_local_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cached = _write_complete_cache(
        tmp_path, schema_version=bootstrap.SCHEMA_VERSION - 1
    )
    databases = {
        database_id: _notion_database(key, database_id)
        for key in S.DATABASES
        for database_id in [cached[f"db_{key}"]]
    }
    databases[cached["db_tasks"]] = _mismatched_database(
        "tasks", cached["db_tasks"]
    )
    databases["replacement-tasks"] = _notion_database(
        "tasks", "replacement-tasks"
    )
    archived: list[str] = []
    recreated: list[str] = []

    def get_database(database_id: str) -> dict[str, Any]:
        try:
            return deepcopy(databases[database_id])
        except KeyError as exc:
            raise RuntimeError(f"unexpected mocked database id: {database_id}") from exc

    def find_or_create_database(
        parent_page_id: str, title: str, properties: dict[str, Any]
    ) -> str:
        if parent_page_id != cached["parent_page_id"] or title != S.DATABASES["tasks"]:
            raise RuntimeError("startup attempted an unexpected database creation")
        recreated.append("tasks")
        return "replacement-tasks"

    def archive_database(database_id: str) -> dict[str, str]:
        archived.append(database_id)
        return {"id": database_id}

    monkeypatch.setattr(bootstrap.store, "get_page", lambda page_id: {"id": page_id})
    monkeypatch.setattr(bootstrap.store, "get_database", get_database)
    monkeypatch.setattr(bootstrap.store, "archive_database", archive_database)
    monkeypatch.setattr(bootstrap, "_find_or_create_database", find_or_create_database)

    result = bootstrap.ensure_brain(tmp_path)
    if not result.get("parent_page_id"):
        raise RuntimeError("the startup fixture did not reach a usable cache result")

    if archived or recreated or result.get("db_tasks") != cached["db_tasks"]:
        raise AssertionError(
            "startup destructively reset a database solely while handling stale schema metadata"
        )


@MIGRATION_XFAIL
def test_health_is_read_only_when_schema_mismatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path, cached = _write_complete_cache(
        tmp_path, schema_version=bootstrap.SCHEMA_VERSION
    )
    before = cache_path.read_bytes()
    databases = {
        cached[f"db_{key}"]: _notion_database(key, cached[f"db_{key}"])
        for key in S.DATABASES
    }
    databases[cached["db_tasks"]] = _mismatched_database(
        "tasks", cached["db_tasks"]
    )
    mutation_attempts: list[str] = []

    monkeypatch.setattr(bootstrap.store, "get_api_key", lambda: "synthetic-test-key")
    monkeypatch.setattr(
        bootstrap.store,
        "get_database",
        lambda database_id: deepcopy(databases[database_id]),
    )
    monkeypatch.setattr(bootstrap, "health_report", lambda home: "health: inspected")

    def reset_databases(*args: Any, **kwargs: Any) -> list[str]:
        mutation_attempts.append("reset_databases")
        return ["tasks"]

    monkeypatch.setattr(bootstrap, "reset_databases", reset_databases)

    result = cli.main(["--home", str(tmp_path), "health"])
    if result != 0:
        raise RuntimeError("the health fixture did not complete successfully")

    if mutation_attempts or cache_path.read_bytes() != before:
        raise AssertionError("health attempted to mutate a mismatched workspace")


@MIGRATION_XFAIL
def test_incompatible_migration_preserves_original_when_replacement_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path, cached = _write_complete_cache(
        tmp_path, schema_version=bootstrap.SCHEMA_VERSION
    )
    original_id = cached["db_tasks"]
    databases = {
        cached[f"db_{key}"]: _notion_database(key, cached[f"db_{key}"])
        for key in S.DATABASES
    }
    databases[original_id] = _mismatched_database("tasks", original_id)
    archived: list[str] = []

    class ReplacementUnavailable(RuntimeError):
        pass

    monkeypatch.setattr(bootstrap.store, "get_page", lambda page_id: {"id": page_id})
    monkeypatch.setattr(
        bootstrap.store,
        "get_database",
        lambda database_id: deepcopy(databases[database_id]),
    )
    def archive_database(database_id: str) -> dict[str, str]:
        archived.append(database_id)
        return {"id": database_id}

    monkeypatch.setattr(bootstrap.store, "archive_database", archive_database)

    def fail_replacement(*args: Any, **kwargs: Any) -> str:
        raise ReplacementUnavailable("simulated replacement failure")

    monkeypatch.setattr(bootstrap, "_find_or_create_database", fail_replacement)

    try:
        bootstrap.reset_databases(tmp_path, only={"tasks"})
    except ReplacementUnavailable:
        pass

    after = json.loads(cache_path.read_text(encoding="utf-8"))
    if original_id in archived or after.get("db_tasks") != original_id:
        raise AssertionError(
            "an incompatible migration discarded the original before replacement could be verified"
        )


@PRIVACY_XFAIL
def test_all_major_write_paths_apply_the_same_secret_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _initialized_provider(tmp_path)
    monkeypatch.setattr(
        provider,
        "_database_properties",
        lambda database_id, entry: _database_properties(),
    )

    detected_secret = "sk-" + "A" * 24
    current_path = {"name": ""}
    writes: dict[str, dict[str, Any]] = {}

    def capture_write(*args: Any, **kwargs: Any) -> dict[str, str]:
        path = current_path["name"]
        if not path:
            raise RuntimeError("write occurred without a path label")
        if args:
            raise RuntimeError("unexpected positional write arguments")
        writes[path] = deepcopy(kwargs)
        return {"id": f"page-{path}"}

    monkeypatch.setattr(bootstrap.store, "create_database_page", capture_write)

    def invoke(path: str, operation: Any) -> None:
        current_path["name"] = path
        operation()
        if path not in writes:
            raise RuntimeError(f"the {path} fixture did not reach its write boundary")

    invoke(
        "task",
        lambda: provider.handle_tool_call(
            "notion_brain_task",
            {
                "action": "create",
                "title": f"private task {detected_secret}",
                "project": f"private project {detected_secret}",
            },
        ),
    )
    invoke(
        "content",
        lambda: provider.handle_tool_call(
            "notion_brain_content",
            {
                "action": "create",
                "title": f"private content {detected_secret}",
                "body": f"private body {detected_secret}",
            },
        ),
    )
    invoke(
        "research",
        lambda: provider.handle_tool_call(
            "notion_brain_research",
            {
                "action": "save",
                "title": f"private research {detected_secret}",
                "content": f"private findings {detected_secret}",
            },
        ),
    )
    invoke(
        "session_summary",
        lambda: provider.on_session_end(
            [
                {
                    "role": "user",
                    "content": f"Discuss private planning details {detected_secret}",
                },
                {"role": "assistant", "content": "Acknowledged"},
            ]
        ),
    )
    invoke(
        "mirror",
        lambda: provider.on_memory_write(
            "add", "memory", f"private mirrored memory {detected_secret}"
        ),
    )

    leaking_paths = [
        path
        for path, payload in writes.items()
        if detected_secret in json.dumps(payload, sort_keys=True)
    ]
    if leaking_paths:
        raise AssertionError(
            "secret policy was bypassed by write paths: " + ", ".join(leaking_paths)
        )


@pytest.mark.parametrize(
    "sample",
    [
        "AKIA" + "A1B2C3D4E5F6G7H8",
        "Authorization: Bearer " + "eyJhbGciOiJIUzI1NiJ9.synthetic.signature",
        "https://synthetic-user:synthetic-password@example.invalid/private",
        "-----BEGIN PRIVATE KEY-----",
    ],
    ids=[
        "aws_access_key",
        "bearer_token",
        "credential_bearing_url",
        "private_key_header",
    ],
)
def test_secure_default_redacts_expanded_secret_classes(sample: str) -> None:
    normalized = S.BrainEntry(
        domain="memory",
        title="synthetic privacy sample",
        content=sample,
    ).normalized()
    if sample in normalized.content:
        raise AssertionError("the secure default did not redact an expanded secret class")


@pytest.mark.xfail(
    strict=False,
    reason="Workstream 4: centralized privacy processing is not implemented",
)
def test_write_failure_logs_exclude_user_content_and_detected_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _initialized_provider(tmp_path)
    monkeypatch.setattr(
        provider,
        "_database_properties",
        lambda database_id, entry: _database_properties(),
    )

    private_user_content = "synthetic confidential acquisition plan"
    detected_secret = "sk-" + "Z" * 24

    def fail_write(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        raise RuntimeError("synthetic backend rejected payload: " + payload)

    monkeypatch.setattr(bootstrap.store, "create_database_page", fail_write)

    messages: list[str] = []

    class ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(self.format(record))

    handler = ListHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    target_logger = logging.getLogger("notion_brain")
    previous_handlers = list(target_logger.handlers)
    previous_level = target_logger.level
    previous_propagate = target_logger.propagate
    previous_disabled = target_logger.disabled
    target_logger.handlers = [handler]
    target_logger.setLevel(logging.DEBUG)
    target_logger.propagate = False
    target_logger.disabled = False
    try:
        provider.handle_tool_call(
            "notion_brain_remember",
            {
                "title": f"{private_user_content} {detected_secret}",
                "content": f"{private_user_content}\n{detected_secret}",
            },
        )
    finally:
        target_logger.handlers = previous_handlers
        target_logger.setLevel(previous_level)
        target_logger.propagate = previous_propagate
        target_logger.disabled = previous_disabled

    if not messages:
        raise RuntimeError("the failure fixture did not emit a provider log record")
    rendered_logs = "\n".join(messages)
    leaked = private_user_content in rendered_logs or detected_secret in rendered_logs
    messages.clear()
    rendered_logs = ""
    if leaked:
        raise AssertionError(
            "write failure logging exposed private user content or a detected secret"
        )
