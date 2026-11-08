"""Provider-level regressions for Phase 9 read-through and budget gaps."""

from __future__ import annotations

import pytest

from notion_brain import bootstrap, brain_cache, injection, store
from notion_brain.provider import NotionBrainProvider


def _provider(home):
    provider = NotionBrainProvider()
    provider._hermes_home = str(home)
    provider._db_ids = {"memory": "memory-db"}
    return provider


def _row(page_id, *, content="", summary="", status="active", kind="fact"):
    return {"id": page_id, "title": page_id, "properties": {
        "Content": content, "Summary": summary, "Status": status, "Kind": kind,
        "Last Seen": "2026-11-09",
    }}


def _deny_network(*args, **kwargs):
    pytest.fail("Cached prefetch attempted a remote operation")


def test_cold_hydrated_read_is_available_to_new_offline_provider(tmp_path, monkeypatch):
    calls = []
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [_row("page-1"), _row("page-1")])
    monkeypatch.setattr(store, "page_body_text", lambda page_id: calls.append(page_id) or f"Saved detail api_key={secret}")

    first = _provider(tmp_path).prefetch()
    assert calls == ["page-1"]
    assert "Saved detail" in first and secret not in first
    monkeypatch.setattr(store, "query_database", _deny_network)
    monkeypatch.setattr(store, "page_body_text", _deny_network)

    second = _provider(tmp_path).prefetch()
    assert "Saved detail" in second
    assert secret not in second
    assert "[REDACTED_SECRET]" in second
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None and len(cached) == 1
    assert secret not in str(cached)


def test_successful_empty_read_is_cached_but_failed_read_is_not(tmp_path, monkeypatch):
    empty_home = tmp_path / "empty"
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [])
    assert _provider(empty_home).prefetch() == ""
    assert brain_cache.list_active(empty_home) == []
    monkeypatch.setattr(store, "query_database", _deny_network)
    monkeypatch.setattr(store, "page_body_text", _deny_network)
    assert _provider(empty_home).prefetch() == ""

    failed_home = tmp_path / "failed"

    def fail_query(*args, **kwargs):
        raise RuntimeError("remote read failed")

    monkeypatch.setattr(store, "query_database", fail_query)
    assert _provider(failed_home).prefetch() == ""
    assert brain_cache.list_active(failed_home) is None


def test_remote_inactive_rows_are_excluded_before_hydration_and_caching(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [
        _row("old", status="Superseded"), _row("done", status="done"),
        _row("current", summary="Current saved summary"),
    ])
    monkeypatch.setattr(store, "page_body_text", _deny_network)

    output = _provider(tmp_path).prefetch()
    assert "Current saved summary" in output
    assert "old" not in output and "done" not in output
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    assert [row["id"] for row in cached] == ["current"]


def test_cached_empty_content_never_fetches_body(tmp_path, monkeypatch):
    assert brain_cache.upsert_active(tmp_path, page_id="blank", title="Blank", kind="fact", content="")
    monkeypatch.setattr(store, "query_database", _deny_network)
    monkeypatch.setattr(store, "page_body_text", _deny_network)
    assert "Blank" in _provider(tmp_path).prefetch()


def test_hydration_failure_still_creates_offline_cache_hit(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [_row("blank")])

    def fail_body(*args, **kwargs):
        raise RuntimeError("body unavailable")

    monkeypatch.setattr(store, "page_body_text", fail_body)
    first = _provider(tmp_path).prefetch()
    assert "blank" in first
    monkeypatch.setattr(store, "query_database", _deny_network)
    monkeypatch.setattr(store, "page_body_text", _deny_network)
    assert _provider(tmp_path).prefetch() == first


def test_cache_population_failure_keeps_cold_recall(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [_row("page", content="Usable content")])

    def fail_cache(*args, **kwargs):
        raise OSError("cache unavailable")

    monkeypatch.setattr(brain_cache, "populate_from_read", fail_cache)
    assert "Usable content" in _provider(tmp_path).prefetch()


def test_unreadable_cache_does_not_block_cold_recall(tmp_path, monkeypatch):
    assert brain_cache.upsert_active(
        tmp_path, page_id="cached", title="Old cached fact", kind="fact", content="Old content",
    )

    def unreadable_cache(*args, **kwargs):
        raise PermissionError("cache cannot be opened")

    monkeypatch.setattr(brain_cache, "_connect", unreadable_cache)
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [_row("remote", content="Usable remote content")])
    assert "Usable remote content" in _provider(tmp_path).prefetch()


def test_read_population_preserves_concurrent_accepted_write(tmp_path, monkeypatch):
    def query_with_write(*args, **kwargs):
        assert brain_cache.upsert_active(
            tmp_path, page_id="same", title="Accepted update", kind="fact",
            content="New accepted value", last_seen="2026-11-10",
        )
        return [_row("same", content="Stale remote value"), _row("remote", content="Remote-only value")]

    monkeypatch.setattr(store, "query_database", query_with_write)
    _provider(tmp_path).prefetch()
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    values = {row["id"]: row["properties"]["Content"] for row in cached}
    assert values == {"same": "New accepted value", "remote": "Remote-only value"}


def test_disk_context_budget_does_not_truncate_background_sync_payload(tmp_path, monkeypatch):
    memory = "m " * 1500
    user = "u " * 1500
    provider = NotionBrainProvider()
    synced = []
    monkeypatch.setattr(bootstrap, "ensure_brain", lambda *args: {"db_memory": "memory-db"})
    monkeypatch.setattr(bootstrap, "read_memory_from_disk", lambda *args: memory)
    monkeypatch.setattr(bootstrap, "read_user_from_disk", lambda *args: user)
    monkeypatch.setattr(provider, "_dispatch_update_refresh", lambda: None)
    monkeypatch.setattr(provider, "_trigger_auto_disk_sync", lambda mem, usr: synced.append((mem, usr)))

    provider.initialize("session", hermes_home=str(tmp_path))
    output = provider.prefetch()
    assert injection.count_tokens(output) <= 800
    assert 0 < output.split().count("u") <= 400
    assert 0 < output.split().count("m") <= 400
    assert injection.count_tokens(output) - output.split().count("m") <= 400
    assert "memory-context" in output
    assert output == provider.prefetch()
    assert synced == [(memory, user)]


def test_conflict_notices_share_budget_and_keep_both_value_snippets(tmp_path, monkeypatch):
    rows = [_row("one", content="first-value " * 1000), _row("two", content="second-value " * 1000)]
    for row in rows:
        row["properties"]["Subject Key"] = "device.phone"
    provider = _provider(tmp_path)
    monkeypatch.setattr(provider, "_prefetch_entries", lambda: rows)
    output = provider.prefetch()
    assert injection.count_tokens(output) <= 800
    assert "CONTRADICTION" in output
    assert "first-value" in output and "second-value" in output
    warning_lines = [line for line in output.splitlines() if not line.startswith("- [fact]")]
    warning_text = "\n".join(warning_lines)
    assert "first-value" in warning_text and "second-value" in warning_text
    assert injection.count_tokens(warning_text) <= 400
    assert injection.count_tokens(output) - injection.count_tokens(warning_text) <= 400
    assert output == provider.prefetch()
