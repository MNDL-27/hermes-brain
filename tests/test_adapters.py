from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from notion_brain import adapters, store
from notion_brain.catalog import StorageRef
from notion_brain.entitlement import EntitlementError
from notion_brain.provider import NotionBrainProvider


@pytest.mark.parametrize("fragment", ["Section Name", "section-name", ""])
def test_obsidian_resolve_storage_ref_strips_section(tmp_path, fragment):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    ref = StorageRef("obsidian", f"note/note.md#{fragment}")
    assert adapter.resolve_storage_ref(ref) == (tmp_path / "note.md").as_posix()


@pytest.mark.parametrize("locator", ["note.md", "note.md#Section Name", "note.md#"])
def test_obsidian_resolve_storage_section(tmp_path, locator):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    fragment = locator.split("#", 1)[1] if "#" in locator else None
    assert adapter.resolve_storage_section({"adapter_name": "obsidian", "locator": locator}) == (
        (tmp_path / "note.md").as_posix(), fragment
    )


@pytest.mark.parametrize("locator", ["../escape.md#section", "note.txt#section", "#section"])
def test_obsidian_section_ref_rejects_invalid_path(tmp_path, locator):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    ref = StorageRef("obsidian", locator)
    assert adapter.resolve_storage_ref(ref) is None
    assert adapter.resolve_storage_section(ref) == ("", None)


def test_obsidian_section_ref_rejects_symlink_outside_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "escape.md").symlink_to(tmp_path / "outside.md")
    adapter = adapters.ObsidianVaultAdapter(vault)
    assert adapter.resolve_storage_ref(StorageRef("obsidian", "escape.md#Section")) is None


def test_obsidian_get_note_content_reads_full_markdown_from_disk(tmp_path, monkeypatch):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    saved = adapter.remember({"id": "note", "title": "Original", "content": "Indexed body"})
    path = Path(saved["path"])
    markdown = '---\ntitle: "Edited title"\n---\n\n# Overview\nEdited body\n'
    path.write_text(markdown, encoding="utf-8")

    def fail_index_access():
        pytest.fail("Raw note retrieval must not read the index")

    monkeypatch.setattr(adapter, "_connect", fail_index_access)
    assert adapter.get_note_content(str(path)) == {
        "path": path.as_posix(), "title": "Edited title", "Content": markdown,
        "Source": "obsidian",
        "Timestamp": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
    }


def test_obsidian_get_note_content_reads_unindexed_note(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    path = tmp_path / "note.md"
    path.write_text("# Overview\nFull markdown\n", encoding="utf-8")
    note = adapter.get_note_content(path)
    assert note is not None
    assert note["title"] == "note"
    assert note["Content"] == "# Overview\nFull markdown\n"
    assert not adapter.index_path.exists()


@pytest.mark.parametrize("failure", ["missing", "directory", "unreadable", "invalid-utf8"])
def test_obsidian_get_note_content_returns_none_on_read_failure(tmp_path, monkeypatch, failure):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    path = tmp_path / "note.md"
    if failure == "directory":
        path.mkdir()
    elif failure == "invalid-utf8":
        path.write_bytes(b"\xff")
    elif failure == "unreadable":
        path.write_text("Content", encoding="utf-8")

        def deny_read(*args, **kwargs):
            raise PermissionError("Unreadable")

        monkeypatch.setattr(Path, "read_text", deny_read)
    assert adapter.get_note_content(path) is None


@pytest.mark.parametrize("section", ["Section Name", "SECTION NAME", "section-name", "#section-name"])
def test_obsidian_get_section_content_matches_header_and_slug(tmp_path, section):
    path = tmp_path / "note.md"
    path.write_text(
        "# Note\nIntroduction\n## Section Name\nSelected body\n"
        "### Child\nNested body\n## Next\nExcluded body\n", encoding="utf-8"
    )
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    assert adapter.get_section_content(path, section) == (
        "## Section Name\nSelected body\n### Child\nNested body"
    )


def test_obsidian_get_section_content_strips_punctuation_in_slug(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("## Section Name: (Details!)\nBody\n", encoding="utf-8")
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    assert adapter.get_section_content(path, "section-name-details") == (
        "## Section Name: (Details!)\nBody"
    )


def test_obsidian_get_section_content_concatenates_duplicate_headers(tmp_path):
    path = tmp_path / "note.md"
    path.write_text(
        "## Repeated\nFirst\n## Other\nExcluded\n## REPEATED\nSecond\n"
        "### Child\nNested\n# End\nExcluded\n", encoding="utf-8"
    )
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    assert adapter.get_section_content(path, "repeated") == (
        "## Repeated\nFirst\n\n## REPEATED\nSecond\n### Child\nNested"
    )


@pytest.mark.parametrize("section", [None, "", "missing", "Partial"])
def test_obsidian_get_section_content_returns_none_without_match(tmp_path, section):
    path = tmp_path / "note.md"
    path.write_text("#Note\n# Partial match\nBody\n", encoding="utf-8")
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    assert adapter.get_section_content(path, section) is None


def test_obsidian_get_section_content_returns_none_for_missing_note(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    assert adapter.get_section_content(tmp_path / "missing.md", "Section") is None


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


# --- Phase 17: vault-primary provider routing ---


def _premium_provider(monkeypatch, tmp_path, *, vault=None, env_only=False):
    from notion_brain import bootstrap

    monkeypatch.setattr(bootstrap, "ensure_brain", lambda home: {"db_memory": "db1"})
    monkeypatch.setattr(bootstrap, "read_memory_from_disk", lambda home: "")
    monkeypatch.setattr(bootstrap, "read_user_from_disk", lambda home: "")
    (tmp_path / "hermes_brain.license").write_text("stub", encoding="utf-8")
    vault_path = vault or (tmp_path / "vault")
    vault_path.mkdir(parents=True, exist_ok=True)
    if env_only:
        monkeypatch.setenv("HERMES_OBSIDIAN_VAULT", str(vault_path))
    provider = NotionBrainProvider()
    kwargs = {"hermes_home": str(tmp_path), "storage_adapter": "obsidian"}
    if not env_only:
        kwargs["obsidian_vault"] = str(vault_path)
    provider.initialize("session", **kwargs)
    return provider, vault_path


def test_obsidian_list_active_find_and_supersede_inferred(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    one = adapter.remember({"title": "Phone A", "content": "Pixel", "subject_key": "device.phone"})
    two = adapter.remember({"title": "Phone B", "content": "iPhone", "subject_key": "device.phone"})

    assert {row["id"] for row in adapter.list_active("device.phone")} == {one["id"], two["id"]}
    assert adapter.find(one["id"])["content"] == "Pixel"

    superseded = adapter.supersede_inferred("device.phone", keep_id=two["id"])

    assert superseded == [one["id"]]
    assert adapter.find(one["id"])["status"] == "Superseded"
    assert adapter.find(two["id"])["status"] == "active"


def test_obsidian_supersede_skips_certified_peer(tmp_path):
    adapter = adapters.ObsidianVaultAdapter(tmp_path)
    certified = adapter.remember({
        "title": "Certified", "content": "Keep", "subject_key": "k", "truth": "certified",
    })

    replacement = adapter.supersede("k", {"title": "New value", "content": "Fresh"})

    assert replacement["superseded_ids"] == []
    assert adapter.find(certified["id"])["status"] == "active"
    assert adapter.find(certified["id"])["truth"] == "certified"
    assert {row["status"] for row in adapter.list_active("k")} == {"active"}


def test_provider_vault_primary_remember_writes_note_not_notion(monkeypatch, tmp_path):
    provider, vault = _premium_provider(monkeypatch, tmp_path)
    monkeypatch.setattr(store, "create_database_page", lambda *a, **k: pytest.fail("Notion write"))
    monkeypatch.setattr(store, "update_page", lambda *a, **k: pytest.fail("Notion update"))

    result = provider._tool_remember({
        "title": "Phone", "content": "Pixel", "subject_key": "device.phone",
    })

    assert result == "Saved: Phone"
    assert len(list((vault / "hermes-brain").glob("*.md"))) == 1


def test_provider_vault_write_failure_fails_closed(monkeypatch, tmp_path):
    provider, _ = _premium_provider(monkeypatch, tmp_path)
    monkeypatch.setattr(
        provider._obsidian_adapter, "remember",
        lambda entry: (_ for _ in ()).throw(RuntimeError("vault unavailable")),
    )
    monkeypatch.setattr(
        provider._obsidian_adapter, "supersede",
        lambda key, entry: (_ for _ in ()).throw(RuntimeError("vault unavailable")),
    )
    monkeypatch.setattr(store, "create_database_page", lambda *a, **k: pytest.fail("Notion fallback"))

    result = provider._tool_remember({"title": "Phone", "content": "Pixel", "subject_key": "k"})

    assert result == "Error: Failed to save entry to the Obsidian vault"


def test_provider_vault_supersede_retains_history_and_edge(monkeypatch, tmp_path):
    provider, _ = _premium_provider(monkeypatch, tmp_path)

    provider._tool_remember({"title": "Phone", "content": "Pixel", "subject_key": "device.phone"})
    provider._tool_remember({"title": "Phone", "content": "iPhone", "subject_key": "device.phone"})

    adapter = provider._obsidian_adapter
    active = adapter.list_active("device.phone")
    assert [row["content"] for row in active] == ["iPhone"]
    old_rows = [row for row in adapter.prefetch() if row["status"] == "Superseded"]
    assert len(old_rows) == 1 and old_rows[0]["content"] == "Pixel"
    assert active[0]["superseded_page_id"] == old_rows[0]["id"]
    catalog = json.loads((tmp_path / "brain_catalog.json").read_text(encoding="utf-8"))
    assert any(
        rel["subject"] == active[0]["id"]
        and rel["predicate"] == "supersedes"
        and rel["object"] == old_rows[0]["id"]
        for rel in catalog["relations"]
    )


def test_provider_vault_certify_flips_truth_and_supersedes_inferred_peer(monkeypatch, tmp_path):
    provider, _ = _premium_provider(monkeypatch, tmp_path)
    adapter = provider._obsidian_adapter
    old = adapter.remember({
        "title": "Phone A", "content": "Pixel", "subject_key": "device.phone", "truth": "inferred",
    })
    new = adapter.remember({
        "title": "Phone B", "content": "iPhone", "subject_key": "device.phone", "truth": "inferred",
    })

    result = provider._tool_certify({"memory_id": new["id"]}, user_confirmed=True)

    assert result == "Certified: Phone B"
    assert adapter.find(new["id"])["truth"] == "certified"
    assert adapter.find(old["id"])["status"] == "Superseded"
    catalog = json.loads((tmp_path / "brain_catalog.json").read_text(encoding="utf-8"))
    assert any(
        rel["subject"] == new["id"] and rel["predicate"] == "supersedes" and rel["object"] == old["id"]
        for rel in catalog["relations"]
    )

    provider._tool_remember({"title": "Phone C", "content": "Galaxy", "subject_key": "device.phone"})
    certified = adapter.find(new["id"])
    assert certified["truth"] == "certified"
    assert certified["status"] == "active"


def test_provider_vault_search_prefers_vault_and_falls_back(monkeypatch, tmp_path):
    provider, _ = _premium_provider(monkeypatch, tmp_path)
    provider._obsidian_adapter.remember({
        "title": "Vault phone", "content": "Pixel value", "subject_key": "device.phone",
    })
    calls = []
    monkeypatch.setattr(store, "query_database", lambda *a, **k: calls.append(a) or [])

    text, _ = provider._tool_search({"query": ""})

    assert "Vault phone" in text
    assert calls == []

    empty_vault = tmp_path / "empty-vault"
    empty_vault.mkdir()
    provider2 = NotionBrainProvider()
    provider2.initialize(
        "session-2", hermes_home=str(tmp_path),
        storage_adapter="obsidian", obsidian_vault=str(empty_vault),
    )
    monkeypatch.setattr(store, "query_database", lambda *a, **k: [{
        "id": "notion-1", "title": "Notion phone",
        "properties": {"Content": "Fallback", "Status": "active"},
    }])

    text2, payload2 = provider2._tool_search({"query": "", "database": "memory"})

    assert "Notion phone" in text2
    assert payload2["items"][0]["id"] == "notion-1"


def test_provider_vault_status_and_env_path(monkeypatch, tmp_path):
    provider, vault = _premium_provider(monkeypatch, tmp_path, env_only=True)

    assert provider._obsidian_adapter is not None
    status = provider.vault_status()
    assert status["backend"] == "obsidian"
    assert status["entitled"] is True
    assert status["vault_path"] == str(vault.resolve())
    assert status["last_sync"] == "not_run"
    assert status["count"] == 0
    assert status["schema_version"] == 2


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
