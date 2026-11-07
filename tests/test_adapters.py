from __future__ import annotations

import sqlite3

import pytest

from notion_brain import adapters
from notion_brain.entitlement import EntitlementError


def test_notion_adapter_delegates_search(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(adapters.store, "search_entries", lambda query, page_size: called.update(query=query, page_size=page_size) or [{"title": "x"}])
    result = adapters.NotionAdapter(hermes_home=tmp_path).search("hello", 4)
    assert result == [{"title": "x"}]
    assert called == {"query": "hello", "page_size": 4}


def test_notion_adapter_remember_redacts_before_store(monkeypatch, tmp_path):
    secret = "«redacted:sk-…»"
    monkeypatch.setattr(adapters.bootstrap, "_load_cache", lambda path: {"db_memory": "db-id"})
    captured = {}

    def create_page(database_id, properties):
        captured.update(database_id=database_id, properties=properties)
        return {"id": "page-id"}

    monkeypatch.setattr(adapters.store, "get_database", lambda database_id: {
        "id": database_id,
        "properties": {
            "title": {"title": {}},
            "Status": {"status": {"options": [{"name": "active"}, {"name": "Superseded"}]}},
            "Subject Key": {"rich_text": {}},
            "Content": {"rich_text": {}},
        },
    })
    monkeypatch.setattr(adapters.store, "create_database_page", create_page)
    result = adapters.NotionAdapter(hermes_home=tmp_path).remember(
        {"title": "A fact", "content": f"api_key={secret}", "metadata": {"subject_key": "k"}}
    )
    assert result == {"id": "page-id"}
    assert secret not in str(captured)
    assert "[REDACTED_SECRET]" in str(captured)
    assert captured["properties"]["Subject Key"]["rich_text"][0]["text"]["content"] == "k"


def test_notion_adapter_supersede_flips_older_active_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(adapters.bootstrap, "_load_cache", lambda path: {"db_memory": "db-id"})
    updated = []

    def create_page(database_id, properties):
        return {"id": "new-id"}

    def update_page(page_id, payload, expected_database_id=None):
        updated.append((page_id, payload))
        return {}

    monkeypatch.setattr(adapters.store, "get_database", lambda database_id: {
        "id": database_id,
        "properties": {
            "title": {"title": {}},
            "Status": {"status": {"options": [{"name": "active"}, {"name": "Superseded"}]}},
            "Subject Key": {"rich_text": {}},
        },
    })
    monkeypatch.setattr(adapters.store, "create_database_page", create_page)
    monkeypatch.setattr(adapters.store, "query_database", lambda database_id, page_size=100: [
        {"id": "old-id", "title": "old", "properties": {"Subject Key": "device", "Status": "active"}},
        {"id": "new-id", "title": "new", "properties": {"Subject Key": "device", "Status": "active"}},
        {"id": "other", "title": "other", "properties": {"Subject Key": "device.other", "Status": "active"}},
    ])
    monkeypatch.setattr(adapters.store, "update_page", update_page)
    result = adapters.NotionAdapter(hermes_home=tmp_path).supersede(
        "device", {"title": "Phone update", "content": "Now iPhone"}
    )
    assert result["id"] == "new-id"
    assert updated == [("old-id", {"Status": {"status": {"name": "Superseded"}}})]


def test_obsidian_round_trip_and_sqlite_index(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = adapters.ObsidianVaultAdapter(vault)
    old = adapter.remember({"title": "Phone", "content": "Daily phone is Pixel", "subject_key": "device.phone"})
    assert adapter.search("PIXEL")
    assert adapter.prefetch()[0]["id"] == old["id"]
    new = adapter.supersede("device.phone", {"title": "Phone update", "content": "Now iPhone"})
    assert new["status"] == "active"
    assert adapter.prefetch()[1]["status"] == "Superseded"
    assert sqlite3.connect(vault / "hermes-brain" / "index.db").execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 2


def test_get_adapter_entitlement_and_defaults(tmp_path):
    with pytest.raises(EntitlementError, match="Notion"):
        adapters.get_adapter("obsidian", hermes_home=tmp_path, obsidian_vault=tmp_path)
    (tmp_path / "hermes_brain.license").write_text("stub", encoding="utf-8")
    assert isinstance(adapters.get_adapter("obsidian", hermes_home=tmp_path, obsidian_vault=tmp_path), adapters.ObsidianVaultAdapter)
    assert isinstance(adapters.get_adapter("notion", hermes_home=tmp_path), adapters.NotionAdapter)
    with pytest.raises(ValueError):
        adapters.get_adapter("other", hermes_home=tmp_path)


def test_obsidian_redacts_secrets(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    saved = adapter.remember({"title": "token=" + secret, "content": "api_key=" + secret})
    raw = (tmp_path / "hermes-brain" / (saved["id"] + ".md")).read_text(encoding="utf-8")
    assert secret not in raw
    assert "[REDACTED_SECRET]" in raw
