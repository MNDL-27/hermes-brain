"""Offline coverage for the RET-02 SQLite cache."""

from __future__ import annotations

import sqlite3

from notion_brain import brain_cache


def test_cache_hit_returns_active_rows(tmp_path) -> None:
    assert brain_cache.upsert_active(
        tmp_path, page_id="page-1", title="A title", kind="fact",
        content="A fact", last_seen="2026-11-01",
    )

    rows = brain_cache.list_active(tmp_path)

    assert rows is not None
    assert rows[0]["id"] == "page-1"
    assert rows[0]["properties"]["Content"] == "A fact"


def test_missing_cache_returns_none(tmp_path) -> None:
    assert brain_cache.list_active(tmp_path) is None


def test_upsert_then_list_round_trip(tmp_path) -> None:
    assert brain_cache.upsert_active(
        tmp_path, page_id="round-trip", title="Round trip", kind="decision",
        content="Keep the local copy", status="active", last_seen="today",
        truth="certified",
    )

    rows = brain_cache.list_active(tmp_path)

    assert rows == [{
        "id": "round-trip",
        "title": "Round trip",
        "properties": {
            "Kind": "decision", "Content": "Keep the local copy",
            "Status": "active", "Last Seen": "today", "Truth": "certified",
        },
    }]


def test_secrets_are_redacted_before_storage(tmp_path) -> None:
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    assert brain_cache.upsert_active(
        tmp_path, page_id="secret", title=f"token {secret}", kind="note",
        content=f"api_key={secret}",
    )

    stored = sqlite3.connect(brain_cache.cache_path(tmp_path)).execute(
        "SELECT title, content FROM memory_rows WHERE page_id = 'secret'"
    ).fetchone()
    assert secret not in " ".join(stored)
    assert all("[REDACTED_SECRET]" in field for field in stored)


def test_non_active_rows_are_excluded(tmp_path) -> None:
    assert brain_cache.upsert_active(
        tmp_path, page_id="old", title="Old", kind="fact", content="old",
        status="Superseded",
    )

    assert brain_cache.list_active(tmp_path) == []


def test_newer_schema_is_left_unchanged(tmp_path) -> None:
    path = brain_cache.cache_path(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_meta VALUES ('version', '999')")
    conn.execute("CREATE TABLE future_rows (payload TEXT NOT NULL)")
    conn.commit()
    before = conn.execute(
        "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
    ).fetchall()
    conn.close()

    assert brain_cache.list_active(tmp_path) is None
    assert not brain_cache.upsert_active(
        tmp_path, page_id="blocked", title="Blocked", kind="fact", content="x",
    )

    conn = sqlite3.connect(path)
    after = conn.execute(
        "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
    ).fetchall()
    version = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
    conn.close()
    assert after == before
    assert version == ("999",)


def test_uninitialized_cache_file_is_a_miss(tmp_path) -> None:
    brain_cache.cache_path(tmp_path).touch()
    assert brain_cache.list_active(tmp_path) is None


def test_read_population_is_atomic_and_failed_initialization_remains_miss(tmp_path) -> None:
    conn = sqlite3.connect(brain_cache.cache_path(tmp_path))
    conn.row_factory = sqlite3.Row
    brain_cache._ensure_schema(conn)
    conn.execute("""
        CREATE TRIGGER reject_bad_row BEFORE INSERT ON memory_rows
        WHEN NEW.page_id = 'bad'
        BEGIN SELECT RAISE(ABORT, 'simulated disk write failure'); END
    """)
    conn.commit()
    conn.close()
    rows = [
        {"id": page_id, "title": page_id, "properties": {"Content": "A value"}}
        for page_id in ("first", "bad")
    ]
    assert not brain_cache.populate_from_read(tmp_path, rows)
    assert brain_cache.list_active(tmp_path) is None
    with sqlite3.connect(brain_cache.cache_path(tmp_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM memory_rows").fetchone()[0] == 0


def test_empty_read_population_preserves_existing_accepted_rows(tmp_path) -> None:
    assert brain_cache.upsert_active(tmp_path, page_id="accepted", title="Accepted", kind="fact", content="New value")
    assert brain_cache.populate_from_read(tmp_path, [])
    rows = brain_cache.list_active(tmp_path)
    assert rows is not None
    assert [row["id"] for row in rows] == ["accepted"]
