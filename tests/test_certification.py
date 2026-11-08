from __future__ import annotations

import json
from copy import deepcopy

import pytest

from notion_brain import bootstrap, store
from notion_brain.provider import NotionBrainProvider
from notion_brain.schema import BrainEntry
from notion_brain.schemas import ALL_TOOL_SCHEMAS


def test_agent_remember_defaults_truth_to_inferred(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db1"}
    captured = []
    monkeypatch.setattr(provider, "_store_entry", captured.append)
    provider._tool_remember({"title": "Fact", "content": "A value", "truth": "certified"})
    assert captured[0].truth == "inferred"
    monkeypatch.setattr(store, "get_database", lambda *_: {"properties": {"Truth": {"type": "select"}}})
    assert provider._database_properties("db1", captured[0])["Truth"] == {"select": {"name": "inferred"}}


@pytest.mark.parametrize("confirmation", [False, None, 0, 1, "true", "false", [], [True], {"confirmed": True}])
def test_certify_requires_exact_user_confirmation(monkeypatch, confirmation):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db1"}
    monkeypatch.setattr(store, "query_database", lambda *a, **k: pytest.fail("Unconfirmed call read memory"))
    result = json.loads(provider.handle_tool_call(
        "notion_brain_certify", {"memory_id": "p1"}, user_confirmed=confirmation
    ))
    assert "orchestrator confirmation" in result["result"]


def test_certify_schema_does_not_expose_confirmation():
    schema = next(s for s in ALL_TOOL_SCHEMAS if s["name"] == "notion_brain_certify")
    assert "user_confirmed" not in schema["parameters"]["properties"]


def test_certify_tool_args_cannot_self_certify(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db1"}
    calls = []
    monkeypatch.setattr(store, "update_page", lambda *a, **k: calls.append((a, k)))
    result = json.loads(provider.handle_tool_call(
        "notion_brain_certify", {"memory_id": "p1", "user_confirmed": True}
    ))
    assert "orchestrator confirmation" in result["result"]
    assert calls == []


def test_initialize_cannot_grant_certification_permission(monkeypatch):
    provider = NotionBrainProvider()
    monkeypatch.setattr(bootstrap, "ensure_brain", lambda *_: {"db_memory": "db1"})
    monkeypatch.setattr(store, "query_database", lambda *a, **k: pytest.fail("Unconfirmed call read memory"))
    provider.initialize(session_id="s", user_confirmed=True)
    result = json.loads(provider.handle_tool_call("notion_brain_certify", {"memory_id": "p1"}))
    assert "orchestrator confirmation" in result["result"]


def test_confirmation_applies_only_to_one_certification_call(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db1"}
    rows = [
        {"id": "approved", "title": "Approved fact", "properties": {}},
        {"id": "unapproved", "title": "Another fact", "properties": {}},
    ]
    monkeypatch.setattr(store, "query_database", lambda *a, **k: rows)
    writes = []
    monkeypatch.setattr(store, "update_page", lambda page_id, properties, **kwargs: writes.append((page_id, properties)))

    result = json.loads(provider.handle_tool_call(
        "notion_brain_certify", {"memory_id": "approved"}, user_confirmed=True
    ))
    assert result["result"] == "Certified: Approved fact"
    for memory_id in ("approved", "unapproved"):
        result = json.loads(provider.handle_tool_call("notion_brain_certify", {"memory_id": memory_id}))
        assert "orchestrator confirmation" in result["result"]
    assert writes == [("approved", {"Truth": {"select": {"name": "certified"}}})]


def test_confirmation_is_not_forwarded_to_other_tool_handlers(monkeypatch):
    provider = NotionBrainProvider()
    received = []
    monkeypatch.setattr(provider, "_tool_remember", lambda arguments: received.append(arguments) or "Remembered")
    arguments = {"title": "A fact", "content": "A value"}
    result = json.loads(provider.handle_tool_call("notion_brain_remember", arguments, user_confirmed=True))
    assert result["result"] == "Remembered"
    assert received == [arguments]
    result = json.loads(provider.handle_tool_call("notion_brain_certify", {"memory_id": "p1"}))
    assert "orchestrator confirmation" in result["result"]


def test_certify_promotes_and_supersedes_same_subject_inferred(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db1"}
    rows = [
        {"id": "new", "title": "Current car", "properties": {"Subject Key": "vehicle.car", "Truth": "inferred", "Status": "active"}},
        {"id": "old", "title": "Old car", "properties": {"Subject Key": "vehicle.car", "Truth": "inferred", "Status": "active"}},
    ]
    calls = []
    monkeypatch.setattr(store, "query_database", lambda *a, **k: rows)
    monkeypatch.setattr(store, "get_database", lambda *_: {"properties": {"Status": {"type": "status", "status": {"options": [{"name": "active"}, {"name": "Superseded"}]}}}})
    monkeypatch.setattr(store, "update_page", lambda page_id, properties, **kwargs: calls.append((page_id, properties)))
    assert provider._tool_certify({"memory_id": "new"}, user_confirmed=True) == "Certified: Current car"
    assert calls[0][1] == {"Truth": {"select": {"name": "certified"}}}
    assert calls[1][0] == "old"
    assert calls[1][1] == {"Status": {"status": {"name": "Superseded"}}}


def test_search_and_prefetch_tiebreak_equal_recency_by_truth(monkeypatch):
    provider = NotionBrainProvider()
    entries = [
        {"id": "i", "title": "Inferred", "last_edited_time": "2026-01-01", "properties": {"Truth": "inferred", "Content": "x"}},
        {"id": "c", "title": "Certified", "last_edited_time": "2026-01-01", "properties": {"Truth": "certified", "Content": "x"}},
    ]
    provider._db_ids = {"memory": "db1"}
    monkeypatch.setattr(store, "query_database", lambda *a, **k: entries)
    result = provider._tool_search({"query": "", "database": "memory", "max_results": 2})
    assert result[1]["items"][0]["title"] == "Certified"
    assert [e["title"] for e in provider._prefetch_entries()] == ["Certified", "Inferred"]


def test_memory_schema_match_accepts_truth_select_superset():
    expected = bootstrap._PROPS["memory"]
    db = {"properties": {name: {"type": next(iter(spec)), next(iter(spec)): deepcopy(spec[next(iter(spec))])} for name, spec in expected.items()}}
    db["properties"]["Truth"]["select"]["options"].append({"name": "custom"})
    assert bootstrap._database_schema_matches(db, expected)


def test_truth_is_normalized_to_inferred_for_agent_entries():
    assert BrainEntry(domain="memory", title="x", content="y", truth="bogus").normalized().truth == "inferred"
