"""Targeted tests to close the coverage gap toward the 80% release gate.

Each test exercises a specific uncovered branch or statement in the
production package. These are not new features — they are verification
that already-shipped code paths behave as designed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import notion_brain as nb
from notion_brain import NotionBrainProvider, bootstrap, store
from notion_brain import schema as S
from notion_brain.store import _block_text, _page_body_text, search_entries

# ---------------------------------------------------------------------------
# __init__.py top-level helpers
# ---------------------------------------------------------------------------


def test_ensure_brain_delegates_to_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[str] = []
    def fake_ensure(home: str) -> dict[str, str]:
        observed.append(home)
        return {"home": home}
    monkeypatch.setattr(bootstrap, "ensure_brain", fake_ensure)
    result = nb.ensure_brain("/tmp/fake-home")
    assert observed == ["/tmp/fake-home"]
    assert result == {"home": "/tmp/fake-home"}


def test_remember_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "mem-db"}
    monkeypatch.setattr(
        provider,
        "_database_properties",
        lambda database_id, entry: {"title": {"title": [{"type": "text", "text": {"content": entry.title}}]}},
    )
    monkeypatch.setattr(store, "search_page_by_title", lambda *a, **k: None)
    monkeypatch.setattr(store, "create_database_page", lambda *a, **k: {"id": "new-page"})

    monkeypatch.setattr(nb, "_session_provider", lambda home=None: provider)
    result = nb.remember(title="A fact", content="Some content")
    assert result["status"] == "saved"
    assert result["title"] == "A fact"


def test_remember_raises_on_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "mem-db"}
    monkeypatch.setattr(
        provider,
        "_database_properties",
        lambda database_id, entry: {"title": {"title": [{"type": "text", "text": {"content": entry.title}}]}},
    )
    monkeypatch.setattr(store, "search_page_by_title", lambda *a, **k: None)
    monkeypatch.setattr(store, "create_database_page", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    monkeypatch.setattr(nb, "_session_provider", lambda home=None: provider)
    # _tool_remember catches RuntimeError and returns a plain string; handle_tool_call
    # wraps it with error=False, so remember() surfaces it as the message rather than raising.
    result = nb.remember(title="A fact", content="Some content")
    assert result["message"].startswith("Error:")
    assert "Failed to save" in result["message"]


def test_search_entries_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "mem-db", "tasks": "task-db"}
    raw_response = json.dumps({
        "result": "- [note] A memory: some content\n- [note] Another: more content\n",
        "error": False,
    })
    monkeypatch.setattr(provider, "handle_tool_call", lambda name, args: raw_response)
    monkeypatch.setattr(nb, "_session_provider", lambda home=None: provider)
    entries = nb.search_entries("query", database="all", max_results=8)
    # search_entries strips the leading "- " from each line
    assert entries == [
        {"title": "[note] A memory: some content"},
        {"title": "[note] Another: more content"},
    ]


def test_search_entries_raises_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = NotionBrainProvider()
    monkeypatch.setattr(
        provider,
        "handle_tool_call",
        lambda name, args: json.dumps({"result": "something went wrong", "error": True}),
    )
    monkeypatch.setattr(nb, "_session_provider", lambda home=None: provider)
    with pytest.raises(RuntimeError, match="something went wrong"):
        nb.search_entries("query")


# ---------------------------------------------------------------------------
# bootstrap.py disk helpers and URL command
# ---------------------------------------------------------------------------


def test_read_memory_from_disk_returns_content(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memories"
    mem_dir.mkdir()
    (mem_dir / "MEMORY.md").write_text("# Memory\nhello world\n", encoding="utf-8")
    assert bootstrap.read_memory_from_disk(tmp_path) == "# Memory\nhello world\n"


def test_read_memory_from_disk_missing(tmp_path: Path) -> None:
    assert bootstrap.read_memory_from_disk(tmp_path) == ""


def test_read_user_from_disk_returns_content(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memories"
    mem_dir.mkdir()
    (mem_dir / "USER.md").write_text("# User Profile\n## Coffee\nblack\n", encoding="utf-8")
    assert bootstrap.read_user_from_disk(tmp_path) == "# User Profile\n## Coffee\nblack\n"


def test_read_user_from_disk_missing(tmp_path: Path) -> None:
    assert bootstrap.read_user_from_disk(tmp_path) == ""


def test_write_memory_to_disk_roundtrip(tmp_path: Path) -> None:
    entries = [
        {"title": "Alpha", "properties": {"Domain": "Daily Work", "Kind": "note", "Tags": ["a", "b"], "Content": "body"}},
        {"title": "Beta", "properties": {"Domain": "Memory", "Kind": "preference", "Tags": [], "Content": ""}},
    ]
    bootstrap.write_memory_to_disk(tmp_path, entries)
    text = (tmp_path / "memories" / "MEMORY.md").read_text(encoding="utf-8")
    assert "name: Alpha" in text
    assert "name: Beta" in text
    assert "body" in text
    assert "tags: a, b" in text


def test_write_user_to_disk_roundtrip(tmp_path: Path) -> None:
    entries = [{"title": "Coffee", "properties": {"Content": "black, no sugar"}}]
    bootstrap.write_user_to_disk(tmp_path, entries)
    text = (tmp_path / "memories" / "USER.md").read_text(encoding="utf-8")
    assert "## Coffee" in text
    assert "black, no sugar" in text


def test_write_memory_to_disk_handles_non_list_tags(tmp_path: Path) -> None:
    entries = [{"title": "Gamma", "properties": {"Domain": "Memory", "Kind": "note", "Tags": "single", "Content": ""}}]
    bootstrap.write_memory_to_disk(tmp_path, entries)
    text = (tmp_path / "memories" / "MEMORY.md").read_text(encoding="utf-8")
    assert "tags: single" in text


def test_get_url_returns_parent_and_databases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cached = {
        "parent_page_id": "parent-id",
        "db_memory": "mem-db",
        "db_tasks": "task-db",
    }
    monkeypatch.setattr(bootstrap, "_load_cache", lambda path: cached)
    monkeypatch.setattr(store, "get_page", lambda pid: {"id": pid, "url": "https://notion.so/parent", "title": "Hermes Brain"})
    monkeypatch.setattr(store, "get_database", lambda dbid: {
        "id": dbid, "url": f"https://notion.so/{dbid}",
        "title": [{"plain_text": dbid}],
    })
    output = bootstrap.get_url(tmp_path, db=True)
    assert "Hermes Brain" in output
    assert "https://notion.so/parent" in output
    assert "https://notion.so/mem-db" in output


def test_get_url_handles_missing_parent_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(bootstrap, "_load_cache", lambda path: {"parent_page_id": "missing"})
    monkeypatch.setattr(store, "get_page", lambda pid: (_ for _ in ()).throw(RuntimeError("gone")))
    output = bootstrap.get_url(tmp_path, db=False)
    assert output == ""


def test_get_url_handles_database_fetch_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cached = {"parent_page_id": "parent-id", "db_memory": "mem-db"}
    monkeypatch.setattr(bootstrap, "_load_cache", lambda path: cached)
    monkeypatch.setattr(store, "get_page", lambda pid: {"id": pid, "url": "https://notion.so/parent", "title": "Hermes Brain"})
    monkeypatch.setattr(store, "get_database", lambda dbid: (_ for _ in ()).throw(RuntimeError("nope")))
    output = bootstrap.get_url(tmp_path, db=True)
    assert "Hermes Brain" in output  # parent still printed


# ---------------------------------------------------------------------------
# store.py search_entries and block text extraction
# ---------------------------------------------------------------------------


def test_search_entries_hydrates_body(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {
        "object": "page",
        "id": "page-1",
        "properties": {
            "title": {"type": "title", "title": [{"type": "text", "text": {"content": "My Page"}, "plain_text": "My Page"}]},
        },
    }
    monkeypatch.setattr(store, "_request", lambda method, path, body=None: {"object": "page", "query": "", "results": [raw]})
    monkeypatch.setattr(store, "_page_body_text", lambda pid: "full body text")
    results = search_entries("query", page_size=8)
    assert len(results) == 1
    assert results[0]["content"] == "full body text"
    assert results[0]["properties"]["Content"] == "full body text"


def test_search_entries_handles_non_dict_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "_request", lambda method, path, body=None: ["not", "a", "dict"])
    assert search_entries("query") == []


def test_search_entries_skips_body_hydration_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "_request", lambda method, path, body=None: {"object": "page", "query": "", "results": []})
    results = search_entries("query")
    assert results == []


def test_block_text_paragraph(monkeypatch: pytest.MonkeyPatch) -> None:
    block = {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "hello"}]}}
    assert _block_text(block) == "hello"


def test_block_text_heading(monkeypatch: pytest.MonkeyPatch) -> None:
    block = {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title"}]}}
    assert _block_text(block) == "Title"


def test_block_text_code(monkeypatch: pytest.MonkeyPatch) -> None:
    block = {"type": "code", "code": {"rich_text": [{"plain_text": "print(1)"}]}}
    assert _block_text(block) == "print(1)"


def test_block_text_unsupported_type(monkeypatch: pytest.MonkeyPatch) -> None:
    block = {"type": "divider", "divider": {}}
    assert _block_text(block) == ""


def test_block_text_no_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    block = {"type": "paragraph"}
    assert _block_text(block) == ""


def test_page_body_text_breaks_on_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "_request", lambda method, path, json_body=None: (_ for _ in ()).throw(RuntimeError("network")))
    assert _page_body_text("page-1") == ""


def test_page_body_text_breaks_on_non_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "_request", lambda method, path, json_body=None: ["list"])
    assert _page_body_text("page-1") == ""


# ---------------------------------------------------------------------------
# provider.py uncovered paths
# ---------------------------------------------------------------------------


def _provider_with_dbs(**db_ids: str) -> NotionBrainProvider:
    p = NotionBrainProvider()
    p._db_ids = db_ids
    return p


def _schema_props() -> dict[str, Any]:
    return {
        "title": {"type": "title"},
        "Domain": {"type": "select"},
        "Status": {"type": "select"},
        "Kind": {"type": "select"},
        "Tags": {"type": "multi_select"},
        "Confidence": {"type": "select"},
        "Content": {"type": "rich_text"},
    }


def test_store_entry_raises_when_no_database() -> None:
    provider = _provider_with_dbs()
    entry = S.BrainEntry(domain="daily_work", title="t", content="c")
    with pytest.raises(RuntimeError, match="No database available"):
        provider._store_entry(entry)


def test_write_entry_raw_updates_existing_page(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(memory="mem-db")
    entry = S.BrainEntry(domain="memory", title="Existing", content="updated")
    monkeypatch.setattr(provider, "_database_properties", lambda dbid, e: {"title": {"title": []}})
    monkeypatch.setattr(
        store, "search_page_by_title",
        lambda title, object_type="page": {"id": "existing-page", "parent": {"database_id": "mem-db"}},
    )
    updated: list[tuple[str, dict]] = []
    monkeypatch.setattr(store, "update_page", lambda pid, props: updated.append((pid, props)))
    provider._write_entry_raw("mem-db", entry)
    assert updated == [("existing-page", {"title": {"title": []}})]


def test_prefetch_returns_empty_when_no_memory_db() -> None:
    provider = _provider_with_dbs()
    assert provider.prefetch() == ""


def test_prefetch_returns_cached_value() -> None:
    provider = _provider_with_dbs(memory="mem-db")
    provider._prefetch_cache = "preloaded"
    assert provider.prefetch() == "preloaded"


def test_prefetch_queries_recent_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(memory="mem-db")
    entries = [
        {"title": "R1", "properties": {"Content": "c1", "Kind": "note"}},
    ]
    monkeypatch.setattr(store, "query_database", lambda *a, **k: entries)
    text = provider.prefetch()
    assert "R1" in text


def test_prefetch_handles_query_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(memory="mem-db")
    monkeypatch.setattr(store, "query_database", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert provider.prefetch() == ""


def test_content_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: ({"status": {"name": status}}, None),
    )
    monkeypatch.setattr(store, "update_page", lambda pid, props: None)
    resp = provider.handle_tool_call("notion_brain_content", {"action": "publish", "page_id": "p1"})
    assert "published" in resp


def test_content_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: ({"status": {"name": status}}, None),
    )
    monkeypatch.setattr(store, "update_page", lambda pid, props: None)
    resp = provider.handle_tool_call("notion_brain_content", {"action": "archive", "page_id": "p1"})
    assert "archived" in resp


def test_content_list_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(store, "query_database", lambda *a, **k: [])
    resp = provider.handle_tool_call("notion_brain_content", {"action": "list"})
    assert "No content found" in resp


def test_content_list_with_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(store, "query_database", lambda *a, **k: [
        {"title": "Draft 1", "properties": {"Status": "draft"}},
    ])
    resp = provider.handle_tool_call("notion_brain_content", {"action": "list"})
    assert "Draft 1" in resp


def test_content_update_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(store, "update_page", lambda pid, props: (_ for _ in ()).throw(RuntimeError("nope")))
    resp = provider.handle_tool_call("notion_brain_content", {"action": "update", "page_id": "p1", "body": "x"})
    assert "Error updating content" in resp


def test_research_list_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(research="research-db")
    monkeypatch.setattr(store, "query_database", lambda *a, **k: [])
    resp = provider.handle_tool_call("notion_brain_research", {"action": "list"})
    assert "No research findings found" in resp


def test_task_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(tasks="task-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: ({"status": {"name": status}}, None),
    )
    monkeypatch.setattr(store, "update_page", lambda pid, props: None)
    resp = provider.handle_tool_call("notion_brain_task", {"action": "complete", "page_id": "p1"})
    assert "completed" in resp


def test_task_update_missing_page_id(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(tasks="task-db")
    resp = provider.handle_tool_call("notion_brain_task", {"action": "update"})
    assert "page_id is required" in resp


def test_task_update_with_status(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(tasks="task-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: ({"status": {"name": status}}, None),
    )
    monkeypatch.setattr(store, "update_page", lambda pid, props: None)
    resp = provider.handle_tool_call("notion_brain_task", {"action": "update", "page_id": "p1", "status": "done"})
    assert "Task updated" in resp


def test_task_update_with_invalid_status_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(tasks="task-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: ({}, "Error: status 'bogus' is not valid"),
    )
    resp = provider.handle_tool_call("notion_brain_task", {"action": "update", "page_id": "p1", "status": "bogus"})
    assert "not valid" in resp


def test_content_publish_invalid_status(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: (None, "Error: not valid"),
    )
    resp = provider.handle_tool_call("notion_brain_content", {"action": "publish", "page_id": "p1"})
    assert "not valid" in resp


def test_content_archive_invalid_status(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: (None, "Error: not valid"),
    )
    resp = provider.handle_tool_call("notion_brain_content", {"action": "archive", "page_id": "p1"})
    assert "not valid" in resp


def test_content_publish_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: ({"status": {"name": status}}, None),
    )
    monkeypatch.setattr(store, "update_page", lambda pid, props: (_ for _ in ()).throw(RuntimeError("boom")))
    resp = provider.handle_tool_call("notion_brain_content", {"action": "publish", "page_id": "p1"})
    assert "Error publishing content" in resp


def test_content_archive_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: ({"status": {"name": status}}, None),
    )
    monkeypatch.setattr(store, "update_page", lambda pid, props: (_ for _ in ()).throw(RuntimeError("boom")))
    resp = provider.handle_tool_call("notion_brain_content", {"action": "archive", "page_id": "p1"})
    assert "Error archiving content" in resp


def test_content_update_no_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    resp = provider.handle_tool_call("notion_brain_content", {"action": "update", "page_id": "p1"})
    assert "No fields provided" in resp


def test_content_update_missing_page_id(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    resp = provider.handle_tool_call("notion_brain_content", {"action": "update"})
    assert "page_id is required" in resp


def test_content_publish_missing_page_id(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    resp = provider.handle_tool_call("notion_brain_content", {"action": "publish"})
    assert "page_id is required" in resp


def test_content_archive_missing_page_id(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    resp = provider.handle_tool_call("notion_brain_content", {"action": "archive"})
    assert "page_id is required" in resp


def test_task_complete_missing_page_id(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(tasks="task-db")
    resp = provider.handle_tool_call("notion_brain_task", {"action": "complete"})
    assert "page_id is required" in resp


def test_task_complete_invalid_status(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(tasks="task-db")
    monkeypatch.setattr(
        provider, "_validated_status",
        lambda status, db_key: (None, "Error: not valid"),
    )
    resp = provider.handle_tool_call("notion_brain_task", {"action": "complete", "page_id": "p1"})
    assert "not valid" in resp


def test_research_save_missing_title(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(research="research-db")
    resp = provider.handle_tool_call("notion_brain_research", {"action": "save", "content": "body"})
    assert "title is required" in resp


def test_research_save_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(research="research-db")
    monkeypatch.setattr(provider, "_store_entry", lambda entry: (_ for _ in ()).throw(RuntimeError("boom")))
    resp = provider.handle_tool_call("notion_brain_research", {"action": "save", "title": "t", "content": "c"})
    assert "Error:" in resp


def test_content_save_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(content="content-db")
    monkeypatch.setattr(provider, "_store_entry", lambda entry: (_ for _ in ()).throw(RuntimeError("boom")))
    resp = provider.handle_tool_call("notion_brain_content", {"action": "create", "title": "t", "body": "c"})
    assert "Error:" in resp


def test_task_create_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(tasks="task-db")
    monkeypatch.setattr(provider, "_store_entry", lambda entry: (_ for _ in ()).throw(RuntimeError("boom")))
    resp = provider.handle_tool_call("notion_brain_task", {"action": "create", "title": "t"})
    assert "Error:" in resp


def test_validated_status_missing_db(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs()
    payload, err = provider._validated_status("done", "tasks")
    assert err is None
    assert payload == {"status": {"name": "done"}}


def test_database_properties_schema_error_reraises(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(memory="mem-db")
    entry = S.BrainEntry(domain="memory", title="t", content="c")
    monkeypatch.setattr(store, "get_database", lambda dbid: (_ for _ in ()).throw(RuntimeError("schema gone")))
    with pytest.raises(RuntimeError, match="schema gone"):
        provider._database_properties("mem-db", entry)


def test_on_memory_write_empty_text_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_dbs(memory="mem-db")
    monkeypatch.setattr(provider, "_store_entry", lambda entry: (_ for _ in ()).throw(AssertionError("should not reach")))
    provider.on_memory_write("   ")  # whitespace-only — should return without storing


def test__merge_disk_only_handles_no_disk_text() -> None:
    from notion_brain.helpers import _merge_disk_only
    entries = [{"title": "existing"}]
    assert _merge_disk_only(entries, "") == entries
    assert _merge_disk_only(entries, "   ") == entries


def test__merge_user_disk_only_handles_no_disk_text() -> None:
    from notion_brain.helpers import _merge_user_disk_only
    entries = [{"title": "existing"}]
    assert _merge_user_disk_only(entries, "") == entries
    assert _merge_user_disk_only(entries, "   ") == entries


def test_delete_page_and_wipe_database_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_cache = {
        "db_entities": "db-ent-1",
        "db_tasks": "db-task-1",
        "db_projects": "db-proj-1",
    }
    monkeypatch.setattr(bootstrap, "_load_cache", lambda p: fake_cache)
    monkeypatch.setattr(
        store,
        "query_database",
        lambda db_id, page_size=100: [{"id": f"page-{db_id}-1"}, {"id": f"page-{db_id}-2"}],
    )
    deleted_pages: list[str] = []

    def _fake_delete(pid: str) -> dict:  # type: ignore[no-untyped-def]
        deleted_pages.append(pid)
        return {"id": pid, "archived": True}

    monkeypatch.setattr(store, "delete_page", _fake_delete)

    res = bootstrap.wipe_database_rows(tmp_path, databases={"entities", "tasks"})
    assert res == {"entities": 2, "tasks": 2}
    assert len(deleted_pages) == 4

