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


def test_search_resolves_obsidian_note_ref_without_text_match(tmp_path, monkeypatch):
    from notion_brain.adapters import ObsidianVaultAdapter

    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = ObsidianVaultAdapter(vault)
    referenced = adapter.remember(
        {"id": "refnote", "title": "Device of record", "content": "Pixel 9"}
    )
    adapter.remember({"id": "othernote", "title": "Weekly groceries", "content": "Milk"})

    graph = Catalog()
    graph.add_term(
        Term(
            name="Daily phone",
            storage_refs=(StorageRef("obsidian", "note/hermes-brain/refnote.md"),),
        )
    )
    graph.save(tmp_path / "brain_catalog.json")

    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._adapter_name = "obsidian"
    provider._obsidian_adapter = adapter
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [])

    _, payload = provider._tool_search({"query": "Daily phone?"})

    assert [item["id"] for item in payload["items"]] == [referenced["id"]]
    assert payload["definitions"][0]["storage_refs"] == [
        (vault / "hermes-brain" / "refnote.md").resolve().as_posix()
    ]


def _section_provider(tmp_path, monkeypatch, section, *, indexed=False, body=None, status="active"):
    from notion_brain.adapters import ObsidianVaultAdapter

    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = ObsidianVaultAdapter(vault)
    if indexed:
        adapter.remember({"id": "note", "title": "Device of record", "content": "Stale index"})
        path = vault / "hermes-brain" / "note.md"
    else:
        path = vault / "note.md"
    markdown = (
        f'---\nid: "note"\ntitle: "Device of record"\nstatus: "{status}"\n---\n\n'
        + (body or "# Overview\nWhole note introduction\n## Section Name\nSelected body\n## Other\nExcluded body\n")
    )
    path.write_text(markdown, encoding="utf-8")
    locator = path.relative_to(vault).as_posix()
    if section is not None:
        locator += "#" + section
    graph = Catalog()
    graph.add_term(Term(name="Daily phone", storage_refs=(StorageRef("obsidian", locator),)))
    graph.save(tmp_path / "brain_catalog.json")

    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._adapter_name = "obsidian"
    provider._obsidian_adapter = adapter
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [])
    return provider, path, markdown


@pytest.mark.parametrize("section", ["SECTION NAME", "section-name"])
@pytest.mark.parametrize("indexed", [False, True])
def test_search_reads_referenced_section_from_disk(tmp_path, monkeypatch, section, indexed):
    provider, path, _ = _section_provider(tmp_path, monkeypatch, section, indexed=indexed)
    _, payload = provider._tool_search({"query": "Daily phone"})

    assert len(payload["items"]) == 1
    assert payload["items"][0]["properties"]["Content"] == "## Section Name\nSelected body"
    assert payload["items"][0]["id"] == "note"
    assert payload["definitions"][0]["storage_refs"] == [path.as_posix() + "#" + section]


def test_search_replaces_content_of_note_already_returned_by_search(tmp_path, monkeypatch):
    provider, _, _ = _section_provider(
        tmp_path, monkeypatch, "section-name", indexed=True,
        body="# Overview\nDaily phone\n## Section Name\nSelected body\n## Other\nExcluded\n",
    )
    _, payload = provider._tool_search({"query": "Daily phone"})
    assert len(payload["items"]) == 1
    assert payload["items"][0]["properties"]["Content"] == "## Section Name\nSelected body"


@pytest.mark.parametrize("section", [None, "", "Missing"])
def test_search_section_falls_back_to_full_disk_note(tmp_path, monkeypatch, caplog, section):
    provider, _, markdown = _section_provider(tmp_path, monkeypatch, section)
    _, payload = provider._tool_search({"query": "Daily phone"})
    assert payload["items"][0]["properties"]["Content"] == markdown
    if section:
        assert "section" in caplog.text.lower() and "Missing" in caplog.text
    else:
        assert not caplog.records


def test_search_missing_referenced_note_logs_warning(tmp_path, monkeypatch, caplog):
    provider, path, _ = _section_provider(tmp_path, monkeypatch, "section-name")
    path.unlink()
    _, payload = provider._tool_search({"query": "Daily phone"})
    assert payload["items"] == []
    assert path.as_posix() in caplog.text
    assert "warning" in caplog.text.lower()


def test_search_section_reference_preserves_superseded_exclusion(tmp_path, monkeypatch):
    provider, _, _ = _section_provider(tmp_path, monkeypatch, "section-name", status="Superseded")
    _, payload = provider._tool_search({"query": "Daily phone"})
    assert payload["items"] == []


def test_search_missing_section_warning_redacts_fragment(tmp_path, monkeypatch, caplog):
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    provider, _, markdown = _section_provider(tmp_path, monkeypatch, "Missing api_key=" + secret)
    _, payload = provider._tool_search({"query": "Daily phone"})
    assert payload["items"][0]["properties"]["Content"] == markdown
    assert secret not in caplog.text
    assert "[REDACTED_SECRET]" in caplog.text
