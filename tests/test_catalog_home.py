from __future__ import annotations

from pathlib import Path

import pytest

from notion_brain import brain_cache, catalog, store
from notion_brain.provider import NotionBrainProvider
from notion_brain.schema import BrainEntry


def _seed_catalog(home: Path, term: str, page_id: str) -> catalog.Catalog:
    graph = catalog.Catalog()
    graph.add_term(catalog.Term(term))
    graph.add_entity(catalog.Entity(
        name="Project",
        entity_type="project",
        description="User-maintained project definition",
        storage_refs=(catalog.StorageRef("notion", f"page/{page_id}"),),
    ))
    graph.add_relation(catalog.Relation("Project", "related", page_id, "edge"))
    graph.save(home / "brain_catalog.json")
    return graph


@pytest.fixture
def separate_catalogs(tmp_path, monkeypatch):
    default_home = tmp_path / "default"
    session_home = tmp_path / "session"
    monkeypatch.setenv("HERMES_HOME", str(default_home))
    _seed_catalog(default_home, "defaultonly", "default-memory")
    _seed_catalog(session_home, "sessiononly", "session-memory")
    return default_home, session_home


@pytest.mark.parametrize("explicit_home", [True, False])
def test_catalog_tools_share_the_provider_home(separate_catalogs, monkeypatch, explicit_home):
    _, session_home = separate_catalogs
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    if explicit_home:
        provider._hermes_home = str(session_home)
    expected_term = "sessiononly" if explicit_home else "defaultonly"
    other_term = "defaultonly" if explicit_home else "sessiononly"
    expected_id = "session-memory" if explicit_home else "default-memory"
    rows = [
        {"id": "default-memory", "title": "defaultonly", "properties": {"Content": "Default fact"}},
        {"id": "session-memory", "title": "sessiononly", "properties": {"Content": "Session fact"}},
    ]
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: rows)

    assert provider._tool_check_answerable({"query": expected_term})[1]["coverage"] == 1.0
    assert provider._tool_check_answerable({"query": other_term})[1]["coverage"] == 0.0
    assert provider._tool_search_terms({"query": expected_term})[1]["terms"] == [expected_term]
    assert provider._tool_search_terms({"query": other_term})[1]["terms"] == []
    search = provider._tool_search({"query": expected_term, "database": "memory"})
    assert [item["id"] for item in search[1]["items"]] == [expected_id]
    related = provider._tool_related({"start_id": "Project"})
    assert [item["id"] for item in related[1]["items"]] == [expected_id]


def test_entity_write_preserves_session_catalog_and_existing_definitions(
    separate_catalogs, monkeypatch
):
    default_home, session_home = separate_catalogs
    default_path = default_home / "brain_catalog.json"
    default_before = default_path.read_bytes()
    before = catalog.Catalog().load(session_home / "brain_catalog.json")
    project_before = before.list_entities()[0]
    provider = NotionBrainProvider()
    provider._hermes_home = str(session_home)
    provider._db_ids = {"memory": "db"}
    monkeypatch.setattr(provider, "_database_properties", lambda *args: {})
    monkeypatch.setattr(provider, "_mirror_memory_cache", lambda *args: None)
    monkeypatch.setattr(provider, "_supersede_matching_active", lambda *args: None)
    monkeypatch.setattr(store, "search_page_by_title", lambda *args, **kwargs: None)
    monkeypatch.setattr(store, "create_database_page", lambda **kwargs: {"id": "new"})

    provider._write_entry_raw("db", BrainEntry(
        domain="memory", title="New fact", content="A value", entities=["project", "Fresh"]
    ))

    after = catalog.Catalog().load(session_home / "brain_catalog.json")
    assert after.resolve_term("sessiononly") is not None
    assert after.resolve_term("defaultonly") is None
    assert after.list_entities("project") == [project_before]
    assert {entity.name for entity in after.list_entities()} == {"Project", "Fresh"}
    assert after.get_relations() == [
        *before.get_relations(),
        catalog.Relation("project", "related", "new", "edge"),
        catalog.Relation("Fresh", "related", "new", "edge"),
    ]
    assert default_path.read_bytes() == default_before


def test_certification_preserves_catalog_and_all_predecessor_edges(separate_catalogs, monkeypatch):
    default_home, session_home = separate_catalogs
    default_path = default_home / "brain_catalog.json"
    default_before = default_path.read_bytes()
    provider = NotionBrainProvider()
    provider._hermes_home = str(session_home)
    provider._db_ids = {"memory": "db"}
    rows = [
        {"id": page_id, "title": page_id, "properties": {
            "Subject Key": "device.phone", "Status": "active", "Truth": "inferred"
        }}
        for page_id in ("new", "old-one", "old-two")
    ]
    schema = {"properties": {
        "Status": {"status": {"options": [{"name": "Superseded"}]}},
        "Superseded Page ID": {"rich_text": {}},
    }}
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: rows)
    monkeypatch.setattr(store, "get_database", lambda *args: schema)
    monkeypatch.setattr(store, "update_page", lambda *args, **kwargs: None)
    monkeypatch.setattr(brain_cache, "upsert_active", lambda *args, **kwargs: True)

    assert provider._tool_certify({"memory_id": "new"}, user_confirmed=True) == "Certified: new"

    after = catalog.Catalog().load(session_home / "brain_catalog.json")
    assert after.resolve_term("sessiononly") is not None
    assert after.resolve_term("defaultonly") is None
    assert after.get_relations() == [
        catalog.Relation("Project", "related", "session-memory", "edge"),
        catalog.Relation("new", "supersedes", "old-one", "edge"),
        catalog.Relation("new", "supersedes", "old-two", "edge"),
    ]
    assert default_path.read_bytes() == default_before
