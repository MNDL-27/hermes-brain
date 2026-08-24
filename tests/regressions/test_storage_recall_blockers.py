"""Strict regression contracts for storage and recall blockers."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest

from notion_brain import NotionBrainProvider, bootstrap, store
from notion_brain import schema as S
from notion_brain.helpers import _paragraph_blocks


def _raw_page(page_id: str, title: str) -> dict[str, Any]:
    return {
        "object": "page",
        "id": page_id,
        "properties": {
            "title": {
                "type": "title",
                "title": [
                    {
                        "type": "text",
                        "text": {"content": title},
                        "plain_text": title,
                    }
                ],
            }
        },
    }


def _paragraph(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": text},
                    "plain_text": text,
                }
            ]
        },
    }


def _notion_database_properties(database_key: str) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for name, specification in bootstrap._PROPS[database_key].items():
        property_type = next(iter(specification))
        properties[name] = {
            "type": property_type,
            property_type: deepcopy(specification[property_type]),
        }
    return properties


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_network(*args: object, **kwargs: object) -> None:
        raise RuntimeError("storage/recall regressions must not make network calls")

    monkeypatch.setattr(store.requests, "request", unexpected_network)


def test_search_entries_retrieves_complete_page_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method == "POST" and path == "/search":
            return {"results": [_raw_page("page-1", "Recall target")]}

        if method == "GET" and path.startswith("/blocks/page-1/children"):
            cursor = (json_body or {}).get("start_cursor")
            if cursor is None and "start_cursor=" not in path:
                return {
                    "results": [_paragraph("First body paragraph.")],
                    "has_more": True,
                    "next_cursor": "body-cursor-2",
                }
            if cursor == "body-cursor-2" or "start_cursor=body-cursor-2" in path:
                return {
                    "results": [_paragraph("Second body paragraph.")],
                    "has_more": False,
                    "next_cursor": None,
                }

        raise RuntimeError(f"unexpected fake Notion request: {method} {path}")

    monkeypatch.setattr(store, "_request", fake_request)

    entries = store.search_entries("Recall target")

    assert len(entries) == 1
    entry = entries[0]
    body = entry.get("content") or entry.get("properties", {}).get("Content")
    assert isinstance(body, str) and body, "search result did not expose its page body"
    assert [line for line in body.splitlines() if line.strip()] == [
        "First body paragraph.",
        "Second body paragraph.",
    ]


def test_database_filtered_search_honors_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matching = _raw_page("matching-page", "Needle protocol")
    unrelated = _raw_page("unrelated-page", "Quarterly lunch menu")

    def fake_request(
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method != "POST" or path != "/databases/db-memory/query":
            raise RuntimeError(f"unexpected fake Notion request: {method} {path}")

        serialized_request = json.dumps(json_body or {}).lower()
        results = [matching] if "needle" in serialized_request else [matching, unrelated]
        return {"results": results, "has_more": False, "next_cursor": None}

    monkeypatch.setattr(store, "_request", fake_request)
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db-memory"}

    response = provider.handle_tool_call(
        "notion_brain_search",
        {"query": "needle", "database": "memory", "max_results": 8},
    )
    items = json.loads(response)["items"]

    assert [item["title"] for item in items] == ["Needle protocol"]


def test_query_database_returns_all_paginated_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_bodies: list[dict[str, Any]] = []

    def fake_request(
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method != "POST" or path != "/databases/db-memory/query":
            raise RuntimeError(f"unexpected fake Notion request: {method} {path}")

        body = deepcopy(json_body or {})
        request_bodies.append(body)
        if len(request_bodies) == 1:
            return {
                "results": [_raw_page("page-1", "First page record")],
                "has_more": True,
                "next_cursor": "database-cursor-2",
            }
        if body.get("start_cursor") == "database-cursor-2":
            return {
                "results": [_raw_page("page-2", "Second page record")],
                "has_more": False,
                "next_cursor": None,
            }
        raise RuntimeError(f"unexpected pagination body: {body}")

    monkeypatch.setattr(store, "_request", fake_request)

    entries = store.query_database("db-memory", page_size=100)

    assert [entry["id"] for entry in entries] == ["page-1", "page-2"]
    assert len(request_bodies) == 2
    assert request_bodies[1]["start_cursor"] == "database-cursor-2"


def test_paragraph_blocks_preserve_every_non_empty_line() -> None:
    source_lines = [f"preserved line {number}" for number in range(1, 13)]

    blocks = _paragraph_blocks("\n".join(source_lines))
    emitted_lines = [
        "".join(
            fragment.get("plain_text")
            or fragment.get("text", {}).get("content", "")
            for fragment in block["paragraph"]["rich_text"]
        )
        for block in blocks
    ]

    assert emitted_lines == source_lines


def test_domain_writes_emit_only_values_declared_by_bootstrap_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = NotionBrainProvider()
    database_ids = {key: f"db-{key}" for key in S.DATABASES}
    provider._db_ids = database_ids
    database_keys_by_id = {database_id: key for key, database_id in database_ids.items()}
    captured_properties: dict[str, dict[str, Any]] = {}

    def fake_get_database(database_id: str) -> dict[str, Any]:
        database_key = database_keys_by_id[database_id]
        return {
            "id": database_id,
            "properties": _notion_database_properties(database_key),
        }

    def fake_create_database_page(
        database_id: str,
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        captured_properties[database_id] = deepcopy(properties)
        return {"id": f"page-for-{database_id}"}

    monkeypatch.setattr(store, "get_database", fake_get_database)
    monkeypatch.setattr(store, "create_database_page", fake_create_database_page)

    for domain in S.DOMAINS:
        database_key = S.database_for_domain(domain)
        provider._write_entry_raw(
            domain=domain,
            title=f"Entry for {domain}",
            content="Payload capture",
            status="active",
            confidence="medium",
            db_id=database_ids[database_key],
        )

    assert set(captured_properties) == set(database_ids.values())

    mismatches: list[str] = []
    for database_id, properties in captured_properties.items():
        database_key = database_keys_by_id[database_id]
        bootstrap_properties = bootstrap._PROPS[database_key]
        for property_name, payload in properties.items():
            emitted_type = next(
                (property_type for property_type in ("select", "status") if property_type in payload),
                None,
            )
            if emitted_type is None:
                continue

            emitted_value = payload[emitted_type].get("name")
            specification = bootstrap_properties.get(property_name)
            if specification is None:
                mismatches.append(
                    f"{database_key}.{property_name} emitted {emitted_value!r} without a schema property"
                )
                continue

            schema_type = next(iter(specification))
            if emitted_type != schema_type:
                mismatches.append(
                    f"{database_key}.{property_name} emitted type {emitted_type!r}; schema uses {schema_type!r}"
                )
                continue

            allowed_values = {
                option.get("name")
                for option in specification[schema_type].get("options", [])
                if option.get("name")
            }
            if emitted_value not in allowed_values:
                mismatches.append(
                    f"{database_key}.{property_name} emitted {emitted_value!r}; "
                    f"allowed values are {sorted(allowed_values)!r}"
                )

    assert not mismatches, "\n".join(mismatches)
