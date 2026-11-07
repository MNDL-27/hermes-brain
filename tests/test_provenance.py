from __future__ import annotations

import json

from notion_brain import bootstrap, catalog, store
from notion_brain.provider import NotionBrainProvider


def test_search_returns_provenance(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    monkeypatch.setattr(store, "query_database", lambda *a, **k: [{
        "id": "m1", "title": "A fact", "created_time": "2026-01-01",
        "properties": {"Content": "value", "Truth": "certified", "Status": "active", "Source Session": "s1"},
    }])
    result = provider._tool_search({"query": "", "database": "memory"})
    assert result[1]["items"][0]["provenance"] == {
        "source_agent": "unknown", "session_id": "s1", "created_at": "2026-01-01",
        "truth": "certified", "status": "active",
    }


def test_prefetch_surfaces_provenance_tag(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    monkeypatch.setattr(provider, "_prefetch_entries", lambda: [{
        "id": "m1", "title": "Fact", "properties": {"Content": "value", "Truth": "certified"},
    }])
    result = provider.prefetch()
    assert "[fact:certified:unknown]" in result


def test_missing_provenance_uses_unknown_sentinels(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    monkeypatch.setattr(store, "query_database", lambda *a, **k: [{
        "id": "m2", "title": "A fact", "properties": {"Content": "value"},
    }])
    result = provider._tool_search({"query": "", "database": "memory"})
    provenance = result[1]["items"][0]["provenance"]
    assert provenance["source_agent"] == "unknown"
    assert provenance["source_agent"] != "hermes"
    assert provenance["created_at"] == "unknown"


def test_prefetch_missing_agent_uses_unknown_tag(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    monkeypatch.setattr(provider, "_prefetch_entries", lambda: [{
        "id": "m2", "title": "Fact", "properties": {"Content": "value", "Truth": "certified"},
    }])
    result = provider.prefetch()
    assert "[fact:certified:unknown]" in result
    assert "hermes" not in result


def test_graph_traverse_chain_cycles_and_depth():
    graph = catalog.Catalog()
    for source, target in (("A", "B"), ("B", "C")):
        graph.add_relation(catalog.Relation(source, "related", target, "edge"))
    assert graph.graph_traverse("A") == ["B", "C"]
    assert graph.graph_traverse("A", max_depth=1) == ["B"]
    graph.add_relation(catalog.Relation("C", "related", "A", "edge"))
    assert graph.graph_traverse("A") == ["B", "C"]


def test_supersession_creates_catalog_edge(monkeypatch, tmp_path):
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": "db"}
    rows = [
        {"id": "new", "title": "Current", "properties": {"Subject Key": "x", "Truth": "inferred", "Status": "active"}},
        {"id": "old", "title": "Previous", "properties": {"Subject Key": "x", "Truth": "inferred", "Status": "active"}},
    ]
    monkeypatch.setattr(store, "query_database", lambda *a, **k: rows)
    monkeypatch.setattr(store, "get_database", lambda *_: {"properties": {
        "Status": {"type": "status", "status": {"options": [{"name": "active"}, {"name": "Superseded"}]}},
        "Superseded Page ID": {"type": "rich_text"},
    }})
    calls = []
    monkeypatch.setattr(store, "update_page", lambda page_id, properties, **kwargs: calls.append((page_id, properties)))
    provider._user_confirmed = True
    assert provider._tool_certify({"memory_id": "new"}) == "Certified: Current"
    assert any(page_id == "new" and properties.get("Superseded Page ID", {}).get("rich_text") for page_id, properties in calls)
    payload = json.loads((tmp_path / "brain_catalog.json").read_text())
    assert {"subject": "new", "predicate": "supersedes", "object": "old", "relation_type": "edge"} in payload["relations"]


def test_memory_schema_adds_superseded_page_id_without_reset():
    assert bootstrap._PROPS["memory"]["Superseded Page ID"] == {"rich_text": {}}


def test_related_action_returns_connected_facts(monkeypatch, tmp_path):
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": "db"}
    graph = catalog.Catalog()
    graph.add_relation(catalog.Relation("Project X", "related", "m1", "edge"))
    graph.add_relation(catalog.Relation("m1", "related", "m2", "edge"))
    graph.save()
    monkeypatch.setattr(store, "query_database", lambda *a, **k: [
        {"id": "m1", "title": "Decision", "properties": {"Content": "decided"}},
        {"id": "m2", "title": "Task", "properties": {"Content": "do it"}},
    ])
    result = provider._tool_search({"action": "related", "start_id": "Project X"})
    assert {item["id"] for item in result[1]["items"]} == {"m1", "m2"}
