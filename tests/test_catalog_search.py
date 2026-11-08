from __future__ import annotations

import pytest

from notion_brain import store
from notion_brain.catalog import Catalog, Entity, StorageRef, Term
from notion_brain.provider import NotionBrainProvider


def _provider(tmp_path, monkeypatch, rows):
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": "db1"}
    monkeypatch.setattr(store, "query_database", lambda *a, **k: rows)
    return provider


def test_search_expands_query_through_catalog_definitions(tmp_path, monkeypatch):
    catalog = Catalog()
    catalog.add_term(Term(name="Phone", synonyms=("mobile",)))
    catalog.save(tmp_path / "brain_catalog.json")
    row = {"id": "p1", "title": "Mobile device specs", "properties": {"Content": "Specs"}}
    provider = _provider(tmp_path, monkeypatch, [row])

    result = provider._tool_search({"query": "phone", "database": "memory"})

    assert result[1]["items"][0]["title"] == "Mobile device specs"


def test_search_includes_resolved_catalog_definitions(tmp_path, monkeypatch):
    ref = StorageRef(adapter_name="notion", locator="page/0123456789abcdef0123456789abcdef")
    catalog = Catalog()
    catalog.add_term(Term(name="Phone", description="A mobile device", storage_refs=(ref,)))
    catalog.save(tmp_path / "brain_catalog.json")
    row = {"id": "p1", "title": "Phone details", "properties": {"Content": "Specs"}}
    provider = _provider(tmp_path, monkeypatch, [row])

    result = provider._tool_search({"query": "phone", "database": "memory"})

    assert result[1]["definitions"][0]["storage_refs"] == ["0123456789abcdef0123456789abcdef"]


def test_search_without_catalog_matches_unchanged(tmp_path, monkeypatch):
    row = {"id": "p1", "title": "Plain title", "properties": {"Content": "Specs"}}
    catalog = Catalog()
    catalog.add_term(Term(name="plain"))
    catalog.save(tmp_path / "brain_catalog.json")
    provider = _provider(tmp_path, monkeypatch, [row])

    result = provider._tool_search({"query": "plain", "database": "memory"})

    assert result[1]["items"][0]["title"] == "Plain title"
    assert result[1]["definitions"][0]["name"] == "plain"


@pytest.mark.parametrize("definition_type", [Term, Entity])
def test_search_resolves_multiword_definition_to_page_without_text_match(tmp_path, monkeypatch, definition_type):
    page_id = "0123456789abcdef0123456789abcdef"
    graph = Catalog()
    definition = definition_type(
        name="Daily phone", storage_refs=(StorageRef("notion", f"page/{page_id}"),)
    )
    if isinstance(definition, Term):
        graph.add_term(definition)
    else:
        graph.add_entity(definition)
    graph.save(tmp_path / "brain_catalog.json")
    row = {"id": "01234567-89ab-cdef-0123-456789abcdef", "title": "Device of record", "properties": {"Content": "Pixel 9"}}
    unrelated = {"id": "other", "title": "Other record", "properties": {"Content": "Unrelated"}}
    provider = _provider(tmp_path, monkeypatch, [unrelated, row])

    _, payload = provider._tool_search({"query": "Daily phone?", "database": "memory"})

    assert [item["id"] for item in payload["items"]] == [row["id"]]
    assert payload["definitions"][0]["storage_refs"] == [page_id]


def test_database_reference_selects_only_rows_from_configured_target(tmp_path, monkeypatch):
    database_id = "0123456789abcdef0123456789abcdef"
    graph = Catalog()
    graph.add_term(Term(name="devices", storage_refs=(StorageRef("notion", f"db/{database_id}"),)))
    graph.save(tmp_path / "brain_catalog.json")
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": database_id, "projects": "other-db"}
    calls = []

    def query_database(db_id, **kwargs):
        calls.append(db_id)
        return [{"id": db_id + "-row", "title": "Inventory", "properties": {}}]

    monkeypatch.setattr(store, "query_database", query_database)
    _, payload = provider._tool_search({"query": "devices"})
    assert [item["id"] for item in payload["items"]] == [database_id + "-row"]
    assert calls == [database_id, "other-db"]

    # A catalog reference cannot escape an explicit database filter.
    _, payload = provider._tool_search({"query": "devices", "database": "projects"})
    assert payload["items"] == []


def test_search_does_not_recall_superseded_catalog_target(tmp_path, monkeypatch):
    page_id = "0123456789abcdef0123456789abcdef"
    graph = Catalog()
    graph.add_term(Term(name="phone", storage_refs=(StorageRef("notion", f"page/{page_id}"),)))
    graph.save(tmp_path / "brain_catalog.json")
    row = {"id": page_id, "title": "Phone", "properties": {"Status": "Superseded"}}
    provider = _provider(tmp_path, monkeypatch, [row])
    _, payload = provider._tool_search({"query": "phone", "database": "memory"})
    assert payload["items"] == []
