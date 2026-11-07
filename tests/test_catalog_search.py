from __future__ import annotations

from notion_brain import store
from notion_brain.catalog import Catalog, StorageRef, Term
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
