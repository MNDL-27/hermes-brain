from __future__ import annotations

import sqlite3

import pytest

from notion_brain import brain_cache, catalog, store
from notion_brain.provider import NotionBrainProvider


def _write_provider(monkeypatch, tmp_path, rows):
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": "memory-db"}
    monkeypatch.setattr(store, "search_page_by_title", lambda *args, **kwargs: None)
    monkeypatch.setattr(store, "get_database", lambda *_: {"properties": {
        "Status": {"type": "status", "status": {"options": [{"name": "active"}, {"name": "Superseded"}]}},
        "Subject Key": {"type": "rich_text"},
        "Content": {"type": "rich_text"},
        "Superseded Page ID": {"type": "rich_text"},
    }})
    monkeypatch.setattr(store, "create_database_page", lambda **kwargs: {"id": "new-page"})
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: rows)
    return provider


def test_normal_memory_write_records_supersession_provenance(monkeypatch, tmp_path):
    rows = [
        {"id": "new-page", "properties": {"Subject Key": "device.phone", "Status": "active"}},
        {"id": "old-page", "title": "Old phone", "properties": {
            "Subject Key": "device.phone", "Status": "active", "Content": "Pixel 8",
        }},
        {"id": "historical", "properties": {"Subject Key": "device.phone", "Status": "Superseded"}},
        {"id": "unrelated", "properties": {"Subject Key": "device.car", "Status": "active"}},
    ]
    provider = _write_provider(monkeypatch, tmp_path, rows)
    target = tmp_path / "brain_catalog.json"
    graph = catalog.Catalog()
    graph.add_relation(catalog.Relation("old-page", "supersedes", "historical", "edge"))
    graph.save(target)
    updates = []
    monkeypatch.setattr(store, "update_page", lambda page_id, properties, **kwargs: updates.append((page_id, properties, kwargs)))

    assert provider._tool_remember({
        "title": "Current phone", "content": "Pixel 9", "subject_key": "device.phone",
    }) == "Saved: Current phone"

    assert updates == [
        ("old-page", {"Status": {"status": {"name": "Superseded"}}}, {"expected_database_id": "memory-db"}),
        ("new-page", {"Superseded Page ID": store.rich_text_property("old-page")}, {"expected_database_id": "memory-db"}),
    ]
    graph = catalog.Catalog().load(target)
    assert graph.graph_traverse("new-page", predicate="supersedes") == ["old-page", "historical"]
    assert rows[1]["properties"]["Content"] == "Pixel 8"
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    assert [row["id"] for row in cached] == ["new-page"]


def test_failed_supersession_does_not_record_provenance(monkeypatch, tmp_path):
    rows = [{"id": "old-page", "properties": {"Subject Key": "device.phone", "Status": "active"}}]
    provider = _write_provider(monkeypatch, tmp_path, rows)
    updates = []

    def fail_status_update(page_id, properties, **kwargs):
        updates.append((page_id, properties))
        raise RuntimeError("Notion update unavailable")

    monkeypatch.setattr(store, "update_page", fail_status_update)
    assert provider._tool_remember({
        "title": "Current phone", "content": "Pixel 9", "subject_key": "device.phone",
    }) == "Saved: Current phone"
    assert updates == [("old-page", {"Status": {"status": {"name": "Superseded"}}})]
    assert not (tmp_path / "brain_catalog.json").exists()


@pytest.mark.parametrize("failure", ["catalog", "predecessor"])
def test_provenance_failure_preserves_cache_supersession_and_remaining_rows(monkeypatch, tmp_path, failure):
    old_ids = ["old-page", "another-old-page"]
    rows = [{"id": page_id, "title": "Old phone", "properties": {
        "Subject Key": "device.phone", "Status": "active", "Content": "Pixel 8",
    }} for page_id in old_ids]
    provider = _write_provider(monkeypatch, tmp_path, rows)
    for page_id in old_ids:
        assert brain_cache.upsert_active(
            tmp_path, page_id=page_id, title="Old phone", kind="note", content="Pixel 8",
            subject_key="device.phone",
        )
    target = tmp_path / "brain_catalog.json"
    malformed = b'{"relations": '
    if failure == "catalog":
        target.write_bytes(malformed)
    updates = []

    def update_page(page_id, properties, **kwargs):
        updates.append((page_id, properties))
        if failure == "predecessor" and "Superseded Page ID" in properties:
            raise RuntimeError("Predecessor update unavailable")

    monkeypatch.setattr(store, "update_page", update_page)
    assert provider._tool_remember({
        "title": "Current phone", "content": "Pixel 9", "subject_key": "device.phone",
    }) == "Saved: Current phone"
    assert [page_id for page_id, props in updates if "Status" in props] == old_ids
    with sqlite3.connect(brain_cache.cache_path(tmp_path)) as connection:
        statuses = dict(connection.execute("SELECT page_id, status FROM memory_rows"))
    assert statuses == {"new-page": "active", **dict.fromkeys(old_ids, "superseded")}
    if failure == "catalog":
        assert target.read_bytes() == malformed
    else:
        graph = catalog.Catalog().load(target)
        assert set(graph.graph_traverse("new-page", predicate="supersedes")) == set(old_ids)
