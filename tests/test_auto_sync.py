"""Tests for automatic local disk memory synchronization."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from notion_brain import helpers, store
from notion_brain import schema as S
from notion_brain.provider import NotionBrainProvider


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch):
    def forbid(*args, **kwargs):
        raise AssertionError("No real network calls during unit tests")
    monkeypatch.setattr(store.requests, "request", forbid)


def test_parse_disk_memory_text_hermes_section_separator():
    text = (
        "Project update: We shipped the MVP.\n"
        "§\n"
        "Preference note: User prefers Python over Node for backend.\n"
        "§\n"
        "Task reminder: Fix the auth bug before release.\n"
    )
    entries = helpers.parse_disk_memory_text(text)
    assert len(entries) == 3
    assert any("Project update" in e["title"] for e in entries)
    assert any("User prefers Python" in e["content"] for e in entries)
    assert any("Fix the auth bug" in e["content"] for e in entries)


def test_parse_disk_memory_text_headings_and_bullets():
    text = (
        "# User Memory\n"
        "## Projects\n"
        "- **FitVision**: Computer vision fitness trainer.\n"
        "- **Hermes Brain**: Notion memory backend.\n"
        "## Tasks\n"
        "- **Ship**: Release v1.0.3 by Monday.\n"
    )
    entries = helpers.parse_disk_memory_text(text)
    assert len(entries) == 3
    fitvision = next(e for e in entries if e["title"] == "FitVision")
    assert fitvision["domain"] == "projects"
    ship = next(e for e in entries if e["title"] == "Ship")
    assert ship["domain"] == "daily_work"


def test_auto_disk_sync_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mem_dir = tmp_path / "memories"
    mem_dir.mkdir()
    (mem_dir / "MEMORY.md").write_text("Audit done: All P0 fixed.\n§\nDesktop installed.\n", encoding="utf-8")
    (mem_dir / "USER.md").write_text("User preference: Always use pytest.\n", encoding="utf-8")

    stored_entries = []

    def mock_store(entry):
        stored_entries.append(entry)

    provider = NotionBrainProvider()
    provider._session_id = "test-session"
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {k: f"db-{k}" for k in S.DATABASES}
    provider._parent_page_id = "parent-1"
    monkeypatch.setattr(provider, "_store_entry", mock_store)

    # 1. First sync should process entries
    provider._sync_disk_memories()
    assert len(stored_entries) == 3
    first_count = len(stored_entries)

    # Verify cache received the hash
    cache_path = tmp_path / S.CACHE_FILE
    assert cache_path.exists()
    cached = json.loads(cache_path.read_text())
    assert "disk_sync_hash" in cached

    # 2. Second sync with identical files should be a no-op
    provider._sync_disk_memories()
    assert len(stored_entries) == first_count  # No duplicate writes!
