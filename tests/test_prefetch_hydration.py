"""RET-01: prefetch hydrates page body text when Content is absent."""

from __future__ import annotations

import logging

from notion_brain.provider import NotionBrainProvider


def _provider_with_memory_db() -> NotionBrainProvider:
    provider = NotionBrainProvider()
    provider._db_ids["memory"] = "db-memory"
    return provider


def _entry(page_id: str, title: str, kind: str = "fact") -> dict:
    return {
        "id": page_id,
        "title": title,
        "properties": {
            "Kind": kind,
            "Last Seen": "2026-08-01",
            "Confidence": "high",
            "Status": "active",
        },
    }


def test_prefetch_renders_hydrated_body(monkeypatch) -> None:
    provider = _provider_with_memory_db()
    body_calls: list[str] = []

    def fake_query(database_id: str, **kwargs) -> list[dict]:
        assert database_id == "db-memory"
        assert kwargs["page_size"] == 10
        return [_entry("page-1", "Deploy notes")]

    def fake_body(page_id: str) -> str:
        body_calls.append(page_id)
        return "Ship the cache fix before Friday."

    monkeypatch.setattr("notion_brain.provider.store.query_database", fake_query)
    monkeypatch.setattr("notion_brain.provider.store.page_body_text", fake_body)

    text = provider.prefetch()

    assert text == (
        "- [fact] Deploy notes: Ship the cache fix before Friday. "
        "[fact:inferred:unknown] [provenance: session=unknown created=unknown status=active]"
    )
    assert body_calls == ["page-1"]


def test_prefetch_blank_when_body_empty(monkeypatch) -> None:
    provider = _provider_with_memory_db()

    monkeypatch.setattr(
        "notion_brain.provider.store.query_database",
        lambda database_id, **kwargs: [_entry("page-empty", "Empty page")],
    )
    monkeypatch.setattr("notion_brain.provider.store.page_body_text", lambda page_id: "")

    assert provider.prefetch() == (
        "- [fact] Empty page:  [fact:inferred:unknown] "
        "[provenance: session=unknown created=unknown status=active]"
    )


def test_prefetch_redacts_secrets_in_body(monkeypatch) -> None:
    provider = _provider_with_memory_db()
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"

    monkeypatch.setattr(
        "notion_brain.provider.store.query_database",
        lambda database_id, **kwargs: [_entry("page-secret", "Token note")],
    )
    monkeypatch.setattr(
        "notion_brain.provider.store.page_body_text",
        lambda page_id: f"rotate this key {secret} now",
    )

    text = provider.prefetch()

    assert secret not in text
    assert "[REDACTED_SECRET]" in text
    assert text.startswith("- [fact] Token note: ")


def test_prefetch_second_call_uses_cache(monkeypatch) -> None:
    provider = _provider_with_memory_db()
    query_calls = {"n": 0}
    body_calls = {"n": 0}

    def fake_query(database_id: str, **kwargs) -> list[dict]:
        query_calls["n"] += 1
        return [_entry("page-1", "Cached title")]

    def fake_body(page_id: str) -> str:
        body_calls["n"] += 1
        return "hydrated once"

    monkeypatch.setattr("notion_brain.provider.store.query_database", fake_query)
    monkeypatch.setattr("notion_brain.provider.store.page_body_text", fake_body)

    first = provider.prefetch()
    second = provider.prefetch()

    assert first == second == (
        "- [fact] Cached title: hydrated once [fact:inferred:unknown] "
        "[provenance: session=unknown created=unknown status=active]"
    )
    assert query_calls["n"] == 1
    assert body_calls["n"] == 1


def test_prefetch_fetches_each_page_body_once(monkeypatch) -> None:
    provider = _provider_with_memory_db()
    body_calls: list[str] = []

    monkeypatch.setattr(
        "notion_brain.provider.store.query_database",
        lambda database_id, **kwargs: [
            _entry("page-1", "First"),
            _entry("page-1", "Duplicate"),
            _entry("page-2", "Second"),
        ],
    )

    def fake_body(page_id: str) -> str:
        body_calls.append(page_id)
        return f"body {page_id}"

    monkeypatch.setattr("notion_brain.provider.store.page_body_text", fake_body)

    text = provider.prefetch()

    assert body_calls == ["page-1", "page-2"]
    assert text.count("body page-1") == 2
    assert "body page-2" in text


def test_prefetch_continues_when_one_body_fails(monkeypatch, caplog) -> None:
    provider = _provider_with_memory_db()

    monkeypatch.setattr(
        "notion_brain.provider.store.query_database",
        lambda database_id, **kwargs: [
            _entry("page-bad", "Broken"),
            _entry("page-ok", "Healthy"),
        ],
    )

    def fake_body(page_id: str) -> str:
        if page_id == "page-bad":
            raise RuntimeError("token sk-ant-api03-abcdefghijklmnopqrstuvwxyz leaked")
        return "still here"

    monkeypatch.setattr("notion_brain.provider.store.page_body_text", fake_body)

    with caplog.at_level(logging.WARNING, logger="notion_brain.provider"):
        text = provider.prefetch()

    assert "- [fact] Broken: " in text
    assert "- [fact] Healthy: still here" in text
    assert "sk-ant-" not in text
    assert caplog.records
    assert all("sk-ant-" not in record.getMessage() for record in caplog.records)
    assert any("[REDACTED_SECRET]" in record.getMessage() for record in caplog.records)
