from __future__ import annotations

import json

from notion_brain import catalog, store
from notion_brain.provider import NotionBrainProvider


def test_check_answerable_full_coverage():
    graph = catalog.Catalog()
    graph.add_term(catalog.Term(name="phone"))
    graph.add_entity(catalog.Entity(name="Hermes"))
    assert catalog.check_answerable("phone Hermes", graph) == {
        "answerable": True,
        "coverage": 1.0,
        "matched_terms": ["phone", "Hermes"],
        "missing_terms": [],
    }


def test_check_answerable_zero_coverage_names_missing():
    result = catalog.check_answerable("unknown gadget")
    assert result["coverage"] == 0.0
    assert result["missing_terms"] == ["unknown", "gadget"]


def test_answerability_tool_callable(monkeypatch):
    graph = catalog.Catalog()
    graph.add_term(catalog.Term(name="phone"))
    monkeypatch.setattr(catalog.Catalog, "load", lambda self, path=None: graph)
    payload = json.loads(NotionBrainProvider().handle_tool_call(
        "notion_brain_check_answerable", {"query": "phone"}
    ))
    assert payload["answerable"] is True


def test_search_terms_uses_glossary(monkeypatch):
    graph = catalog.Catalog()
    graph.add_term(catalog.Term(name="phone", synonyms=("mobile",)))
    monkeypatch.setattr(catalog.Catalog, "load", lambda self, path=None: graph)
    payload = json.loads(NotionBrainProvider().handle_tool_call(
        "notion_brain_search_terms", {"query": "mobile"}
    ))
    assert payload["terms"] == ["phone"]


def test_search_surfaces_active_contradiction(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    rows = [
        {"id": "1", "title": "Car one", "created_time": "2026-01-01", "properties": {"Subject Key": "car", "Content": "Volvo", "Status": "active", "Truth": "certified"}},
        {"id": "2", "title": "Car two", "created_time": "2026-02-01", "properties": {"Subject Key": "car", "Content": "Saab", "Status": "active", "Truth": "inferred"}},
    ]
    graph = catalog.Catalog()
    graph.add_term(catalog.Term(name="Car"))
    monkeypatch.setattr(catalog.Catalog, "load", lambda self, path=None: graph)
    monkeypatch.setattr(store, "query_database", lambda *a, **k: rows)
    payload = json.loads(provider.handle_tool_call("notion_brain_search", {"query": "Car", "database": "memory"}))
    assert len(payload["contradiction"]) == 1
    assert {x["value"] for x in payload["contradiction"][0]["entries"]} == {"Volvo", "Saab"}
    assert {x["timestamp"] for x in payload["contradiction"][0]["entries"]} == {"2026-01-01", "2026-02-01"}
    assert {x["certification"] for x in payload["contradiction"][0]["entries"]} == {"certified", "inferred"}


def test_single_active_row_not_contradiction():
    assert NotionBrainProvider._contradictions([
        {"properties": {"Subject Key": "car", "Content": "Volvo", "Status": "active"}}
    ]) == []


def test_prefetch_surfaces_contradiction(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    rows = [
        {"title": "Car A", "properties": {"Subject Key": "car", "Content": "Volvo", "Status": "active", "Truth": "certified"}},
        {"title": "Car B", "properties": {"Subject Key": "car", "Content": "Saab", "Status": "active", "Truth": "inferred"}},
    ]
    monkeypatch.setattr(provider, "_prefetch_entries", lambda: rows)
    output = provider.prefetch()
    assert "CONTRADICTION" in output
    assert "Volvo" in output and "Saab" in output
    assert "certified" in output and "inferred" in output


def test_answerability_and_contradiction_output_redacted():
    secret = "ghp_" + "a" * 30
    graph = catalog.Catalog()
    graph.add_term(catalog.Term(name=secret))
    result = catalog.check_answerable(secret, graph)
    assert secret not in str(result)
    conflicts = NotionBrainProvider._contradictions([
        {"created_time": secret, "properties": {"Subject Key": secret, "Content": secret, "Status": "active", "Truth": "certified"}},
        {"created_time": "later", "properties": {"Subject Key": secret, "Content": "different", "Status": "active", "Truth": "inferred"}},
    ])
    assert secret not in str(conflicts)


def test_search_zero_coverage_blocks_near_miss(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    empty = catalog.Catalog()
    monkeypatch.setattr(catalog.Catalog, "load", lambda self, path=None: empty)
    rows = [{"id": "1", "title": "Unknown Gadget Recall", "properties": {"Content": "near miss"}}]
    calls = []

    def query_database(*args, **kwargs):
        calls.append((args, kwargs))
        return rows

    monkeypatch.setattr(store, "query_database", query_database)
    response, _ = provider._tool_search({"query": "unknown gadget", "database": "memory"})
    assert "no certified memory" in response.lower()
    assert "Unknown Gadget Recall" not in response
    assert calls == []


def test_search_partial_coverage_still_retrieves(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db"}
    graph = catalog.Catalog()
    graph.add_term(catalog.Term(name="phone"))
    monkeypatch.setattr(catalog.Catalog, "load", lambda self, path=None: graph)
    rows = [{"id": "1", "title": "Phone details", "properties": {"Content": "A phone"}}]
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: rows)
    response, payload = provider._tool_search({"query": "phone unknown", "database": "memory"})
    assert "Phone details" in response
    assert payload["items"][0]["title"] == "Phone details"


def test_check_answerable_zero_coverage_says_no_certified_memory(monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "load", lambda self, path=None: catalog.Catalog())
    payload = json.loads(NotionBrainProvider().handle_tool_call(
        "notion_brain_check_answerable", {"query": "unknown gadget"}
    ))
    assert "no certified memory" in payload["result"].lower()
