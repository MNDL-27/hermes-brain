from __future__ import annotations

from copy import deepcopy

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


def test_certify_requires_exact_user_confirmation(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db1"}
    assert "orchestrator confirmation" in provider._tool_certify({"memory_id": "p1"})
    assert "orchestrator confirmation" in provider._tool_certify({"memory_id": "p1", "user_confirmed": "true"})
    assert "notion_brain_certify" in {s["name"] for s in ALL_TOOL_SCHEMAS}


def test_certify_tool_args_cannot_self_certify(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db1"}
    calls = []
    monkeypatch.setattr(store, "update_page", lambda *a, **k: calls.append((a, k)))
    result = provider._tool_certify({"memory_id": "p1", "user_confirmed": True})
    assert "orchestrator confirmation" in result
    assert calls == []


def test_initialize_user_confirmed_orchestrator_channel():
    provider = NotionBrainProvider()
    provider.initialize("s")
    assert provider._user_confirmed is False
    provider.initialize(session_id="s", user_confirmed=True)
    assert provider._user_confirmed is True


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
    provider._user_confirmed = True
    assert provider._tool_certify({"memory_id": "new"}) == "Certified: Current car"
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
