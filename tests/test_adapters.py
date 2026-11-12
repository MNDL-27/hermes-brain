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


def test_obsidian_get_note_returns_indexed_note_and_rejects_outside_paths(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = adapters.ObsidianVaultAdapter(vault)
    saved = adapter.remember({"id": "note1", "title": "Known", "content": "Body"})

    assert adapter.get_note(saved["path"])["id"] == "note1"
    assert adapter.get_note(vault / "outside.md") is None
    assert adapter.get_note(tmp_path / "escape.md") is None


def test_provider_prefetch_uses_notion_adapter(monkeypatch):
    from notion_brain.provider import NotionBrainProvider

    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db-memory"}
    adapter = adapters.NotionAdapter(hermes_home="")
    calls = {}

    def fake_prefetch(limit=10):
        calls["limit"] = limit
        return [
            {
                "id": "page-1",
                "title": "Fact",
                "properties": {"Content": "body", "Status": "active"},
            }
        ]

    monkeypatch.setattr(adapter, "prefetch", fake_prefetch)
    provider._notion_adapter = adapter

    entries = provider._prefetch_entries()

    assert calls == {"limit": 10}
    assert [entry["id"] for entry in entries] == ["page-1"]


def test_provider_search_uses_notion_adapter(monkeypatch):
    from notion_brain.provider import NotionBrainProvider

    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "db-memory"}
    adapter = adapters.NotionAdapter(hermes_home="")
    calls = {}

    def fake_search(query, limit=8, *, database_id=None):
        calls.update(query=query, limit=limit, database_id=database_id)
        return [
            {
                "id": "page-1",
                "title": "Printable",
                "properties": {"Content": "body", "Status": "active"},
            }
        ]

    monkeypatch.setattr(adapter, "search", fake_search)
    provider._notion_adapter = adapter

    text, payload = provider._tool_search({"query": "", "database": "memory"})

    assert calls == {"query": "", "limit": 8, "database_id": "db-memory"}
    assert [item["id"] for item in payload["items"]] == ["page-1"]
    assert "Printable" in text


def test_provider_initialize_wires_notion_adapter(monkeypatch, tmp_path):
    from notion_brain import bootstrap
    from notion_brain.provider import NotionBrainProvider

    monkeypatch.setattr(bootstrap, "ensure_brain", lambda home: {})

    provider = NotionBrainProvider()
    provider.initialize("session", hermes_home=str(tmp_path))

    assert isinstance(provider._notion_adapter, adapters.NotionAdapter)
    assert provider._adapter_name == "notion"


def test_provider_premium_selection_falls_back_when_unentitled(monkeypatch, tmp_path):
    from notion_brain import bootstrap
    from notion_brain.provider import NotionBrainProvider

    monkeypatch.setattr(bootstrap, "ensure_brain", lambda home: {})

    def deny(name, *, hermes_home, obsidian_vault=None):
        raise EntitlementError(
            "Obsidian storage requires premium. Free tier fallback: Notion storage."
        )

    monkeypatch.setattr(adapters, "get_adapter", deny)

    provider = NotionBrainProvider()
    provider.initialize(
        "session",
        hermes_home=str(tmp_path),
        storage_adapter="obsidian",
        obsidian_vault=str(tmp_path),
    )

    assert provider._adapter_name == "notion"
    assert provider._obsidian_adapter is None
    assert isinstance(provider._notion_adapter, adapters.NotionAdapter)


def test_provider_selects_entitled_obsidian_adapter(monkeypatch, tmp_path):
    from notion_brain import bootstrap
    from notion_brain.provider import NotionBrainProvider

    monkeypatch.setattr(bootstrap, "ensure_brain", lambda home: {})
    (tmp_path / "hermes_brain.license").write_text("stub", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()

    provider = NotionBrainProvider()
    provider.initialize(
        "session",
        hermes_home=str(tmp_path),
        storage_adapter="obsidian",
        obsidian_vault=str(vault),
    )

    assert provider._adapter_name == "obsidian"
    assert isinstance(provider._obsidian_adapter, adapters.ObsidianVaultAdapter)


def test_provider_premium_prefetch_skips_notion_cache(monkeypatch, tmp_path):
    from notion_brain import brain_cache
    from notion_brain.provider import NotionBrainProvider

    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = adapters.ObsidianVaultAdapter(vault)
    adapter.remember({"title": "Vault fact", "content": "Vault body"})

    def fail_cache(*args, **kwargs):
        raise AssertionError("premium prefetch read the Notion cache")

    monkeypatch.setattr(brain_cache, "list_active", fail_cache)

    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._adapter_name = "obsidian"
    provider._obsidian_adapter = adapter

    entries = provider._prefetch_entries()

    assert [entry["title"] for entry in entries] == ["Vault fact"]


def test_provider_search_merges_entitled_vault_rows(tmp_path):
    from notion_brain.provider import NotionBrainProvider

    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = adapters.ObsidianVaultAdapter(vault)
    adapter.remember({"title": "Vault fact", "content": "Vault body"})

    provider = NotionBrainProvider()
    provider._adapter_name = "obsidian"
    provider._obsidian_adapter = adapter

    text, payload = provider._tool_search({"query": ""})

    assert "Vault fact" in text
    assert payload["items"][0]["properties"]["Content"] == "Vault body"
