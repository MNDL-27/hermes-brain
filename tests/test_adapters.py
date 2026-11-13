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


# --- Phase 16: vault note schema v2 and write operations ---


def test_obsidian_frontmatter_v2_round_trip(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    saved = adapter.remember({
        "id": "fact-1", "title": "Phone", "content": "Daily phone is Pixel",
        "subject_key": "device.phone", "truth": "certified",
        "source_agent": "hermes", "source_session": "sess-1",
        "domain": "memory", "kind": "decision", "tags": ["device", "phone"],
    })

    note = (tmp_path / "hermes-brain" / "fact-1.md").read_text(encoding="utf-8")
    assert 'truth: "certified"' in note
    assert 'source_agent: "hermes"' in note
    assert 'source_session: "sess-1"' in note
    assert 'tags: ["device", "phone"]' in note
    assert 'domain: "memory"' in note and 'kind: "decision"' in note

    row = adapter.get_note(saved["path"])
    assert row is not None
    assert row["truth"] == "certified"
    assert row["source_agent"] == "hermes"
    assert row["source_session"] == "sess-1"
    assert row["tags"] == ["device", "phone"]
    assert row["domain"] == "memory" and row["kind"] == "decision"

    with sqlite3.connect(tmp_path / "hermes-brain" / "index.db") as conn:
        stored = conn.execute(
            "SELECT truth, source_agent, source_session, tags FROM memories WHERE id='fact-1'"
        ).fetchone()
    assert stored == ("certified", "hermes", "sess-1", '["device", "phone"]')


def test_obsidian_v1_note_reads_with_defaults_and_upgrades_on_write(tmp_path):
    storage = tmp_path / "hermes-brain"
    storage.mkdir()
    (storage / "v1.md").write_text(
        '---\ntitle: "Old"\nsubject_key: "legacy"\nstatus: "active"\n'
        'created_at: "2026-01-01"\n---\n\nLegacy body\n',
        encoding="utf-8",
    )
    conn = sqlite3.connect(storage / "index.db")
    conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE memories (id TEXT PRIMARY KEY, path TEXT NOT NULL, title TEXT NOT NULL, "
        "subject_key TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, body TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO memories VALUES ('v1', 'v1.md', 'Old', 'legacy', 'active', '2026-01-01', 'Legacy body')"
    )
    conn.execute("INSERT INTO schema_meta VALUES ('version', '1')")
    conn.commit()
    conn.close()

    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    row = adapter.get_note(storage / "v1.md")
    assert row is not None
    assert row["truth"] == "inferred"
    assert row["source_agent"] == "unknown"
    assert row["tags"] == []
    assert row["updated_at"] == ""

    upgraded = adapter.remember({
        "id": "v1", "title": "Old", "content": "Legacy body",
        "source_session": "s1", "tags": ["legacy"],
    })
    assert upgraded["created_at"] == "2026-01-01"
    note = (storage / "v1.md").read_text(encoding="utf-8")
    assert 'truth: "inferred"' in note
    assert 'source_session: "s1"' in note
    assert 'tags: ["legacy"]' in note
    assert 'created_at: "2026-01-01"' in note


def test_obsidian_remember_is_idempotent_for_identical_active_entry(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    first = adapter.remember({"title": "Same", "content": "Body", "subject_key": "k"})
    second = adapter.remember({"title": "Same", "content": "Body", "subject_key": "k"})

    assert first["id"] == second["id"]
    assert len(adapter.prefetch()) == 1
    assert len(list((tmp_path / "hermes-brain").glob("*.md"))) == 1


def test_obsidian_supersede_keeps_history_and_links_predecessor(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    old = adapter.remember({"title": "Phone", "content": "Pixel", "subject_key": "device.phone"})
    new = adapter.supersede("device.phone", {"title": "Phone", "content": "iPhone"})

    assert new["status"] == "active"
    assert new["superseded_page_id"] == old["id"]
    old_row = adapter.get_note(old["path"])
    assert old_row is not None
    assert old_row["status"] == "Superseded"
    assert len(adapter.prefetch()) == 2
    assert "Superseded" in (tmp_path / "hermes-brain" / f"{old['id']}.md").read_text(encoding="utf-8")


def test_obsidian_certify_sets_truth_without_demotion(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    adapter.remember({"id": "c1", "title": "Fact", "content": "Certified value", "truth": "inferred"})

    certified = adapter.certify("c1")
    assert certified is not None and certified["truth"] == "certified"

    updated = adapter.remember({
        "id": "c1", "title": "Fact", "content": "Certified value", "truth": "inferred",
    })
    assert updated["truth"] == "certified"
    assert 'truth: "certified"' in (tmp_path / "hermes-brain" / "c1.md").read_text(encoding="utf-8")


def test_obsidian_v2_redacts_provenance_fields(tmp_path):
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    saved = adapter.remember({
        "title": f"token {secret}", "content": f"api_key={secret}",
        "source_session": secret, "tags": [secret],
    })

    raw = (tmp_path / "hermes-brain" / f"{saved['id']}.md").read_text(encoding="utf-8")
    assert secret not in raw
    assert "[REDACTED_SECRET]" in raw
    row = adapter.get_note(saved["path"])
    assert row is not None
    assert secret not in str(row)


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
