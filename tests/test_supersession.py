from __future__ import annotations

from copy import deepcopy

from notion_brain import bootstrap, brain_cache, store
from notion_brain.provider import NotionBrainProvider
from notion_brain.schema import BrainEntry, infer_subject_key


def _memory_schema() -> dict:
    return {
        "Status": {"type": "status", "status": {"options": [{"name": "active"}, {"name": "Superseded"}]}},
        "Subject Key": {"type": "rich_text"},
        "Truth": {"type": "select"},
        "Kind": {"type": "select"},
        "Content": {"type": "rich_text"},
    }


def _write_entry(monkeypatch, *, old_rows: list[dict], update=None) -> tuple[NotionBrainProvider, list]:
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "memory-db"}
    monkeypatch.setattr(store, "search_page_by_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(store, "get_database", lambda *_: {"properties": _memory_schema()})
    monkeypatch.setattr(store, "create_database_page", lambda **_kwargs: {"id": "new-page"})
    monkeypatch.setattr(store, "query_database", lambda *_args, **_kwargs: old_rows)
    calls = []
    monkeypatch.setattr(store, "update_page", update or (lambda *args, **kwargs: calls.append((args, kwargs))))
    provider._store_entry(BrainEntry(
        domain="memory", title="Current phone", content="My daily phone is Pixel 9",
        metadata={"subject_key": "device.daily_phone"},
    ).normalized())
    return provider, calls


def test_infers_subject_key_from_fact_content_and_title():
    assert infer_subject_key("Phone", "My daily phone is Pixel") == "device.daily_phone"
    assert infer_subject_key("Engine preference", "I prefer a 650cc engine") == "preferences.engine_cc"
    assert infer_subject_key("Unrelated", "A fact with no recognized slot") == ""


def test_remember_subject_key_inference_and_override(monkeypatch):
    provider = NotionBrainProvider()
    captured = []
    monkeypatch.setattr(provider, "_store_entry", captured.append)
    provider._tool_remember({"title": "Phone", "content": "My daily phone is Pixel"})
    provider._tool_remember({
        "title": "Phone", "content": "My daily phone is Pixel", "subject_key": "custom.phone",
    })
    assert captured[0].metadata["subject_key"] == "device.daily_phone"
    assert captured[1].metadata["subject_key"] == "custom.phone"


def test_same_subject_write_supersedes_prior_active_row(monkeypatch):
    rows = [
        {"id": "new-page", "properties": {"Subject Key": "device.daily_phone", "Status": "active"}},
        {"id": "old-page", "title": "Old phone", "properties": {"Subject Key": "device.daily_phone", "Status": "active"}},
    ]
    _, calls = _write_entry(monkeypatch, old_rows=rows)
    assert len(calls) == 1
    assert calls[0][0][0] == "old-page"
    assert calls[0][0][1] == {"Status": {"status": {"name": "Superseded"}}}


def test_different_or_blank_subject_does_not_supersede(monkeypatch):
    rows = [{"id": "old-page", "properties": {"Subject Key": "device.car", "Status": "active"}}]
    _, calls = _write_entry(monkeypatch, old_rows=rows)
    assert calls == []

    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "memory-db"}
    provider._supersede_matching_active("new-page", BrainEntry(domain="memory", title="x", content="y"), "memory-db")
    assert calls == []


def test_timeline_orders_rows_newest_first_with_status(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "memory-db"}
    rows = [
        {"id": "old", "title": "Old", "created_time": "2024-01-01", "properties": {"Subject Key": "device.phone", "Status": "Superseded", "Last Seen": "2024-01-01"}},
        {"id": "new", "title": "New", "created_time": "2025-01-01", "properties": {"Subject Key": "device.phone", "Status": "active", "Last Seen": "2025-01-01"}},
        {"id": "other", "title": "Other", "properties": {"Subject Key": "device.car", "Status": "active"}},
    ]
    monkeypatch.setattr(store, "query_database", lambda *_args, **_kwargs: rows)
    result = provider._tool_search({"action": "timeline", "subject_key": "device.phone"})
    assert [item["id"] for item in result[1]["items"]] == ["new", "old"]
    assert [item["status"] for item in result[1]["items"]] == ["active", "Superseded"]


def test_supersession_failure_is_fail_soft_and_redacted(monkeypatch, caplog):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "memory-db"}
    monkeypatch.setattr(store, "search_page_by_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(store, "get_database", lambda *_: {"properties": _memory_schema()})
    created = []
    monkeypatch.setattr(store, "create_database_page", lambda **kwargs: created.append(kwargs) or {"id": "new-page"})

    def fail_query(*_args, **_kwargs):
        raise RuntimeError("failed token=sk-proj-12345678901234567890")

    monkeypatch.setattr(store, "query_database", fail_query)
    result = provider._tool_remember({
        "title": "Phone", "content": "My daily phone is Pixel", "subject_key": "device.daily_phone",
    })
    assert result == "Saved: Phone"
    assert created
    assert "sk-proj-12345678901234567890" not in caplog.text
    assert "[REDACTED_SECRET]" in caplog.text


def test_memory_schema_match_includes_subject_key_and_status_superset():
    expected = bootstrap._PROPS["memory"]
    db = {"properties": {
        name: {"type": next(iter(spec)), next(iter(spec)): deepcopy(spec[next(iter(spec))])}
        for name, spec in expected.items()
    }}
    db["properties"]["Status"]["status"]["options"].append({"name": "user-option"})
    assert bootstrap._database_schema_matches(db, expected) is False
    db["properties"]["Status"]["status"]["options"].pop()
    db["properties"]["Domain"]["select"]["options"].append({"name": "user-option"})
    assert bootstrap._database_schema_matches(db, expected)
    assert expected["Subject Key"] == {"rich_text": {}}


def test_cache_mirrors_subject_key(tmp_path):
    assert brain_cache.upsert_active(
        tmp_path, page_id="phone", title="Phone", kind="preference", content="Pixel",
        subject_key="device.daily_phone",
    )
    rows = brain_cache.list_active(tmp_path)
    assert rows is not None
    assert rows[0]["properties"]["Subject Key"] == "device.daily_phone"
