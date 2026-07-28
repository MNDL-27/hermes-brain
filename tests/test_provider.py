"""Tests for the Notion Brain provider (notion_brain/__init__.py)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Set up path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notion_brain.schema import (
    DATABASES,
    DOMAIN_DATABASE,
    DOMAINS,
    database_for_domain,
    normalize_domain,
)
from notion_brain.store import (
    multi_select_property,
    rich_text_property,
    select_property,
    status_property,
    title_property,
)

# ---------------------------------------------------------------------------
# Provider existence and interface
# ---------------------------------------------------------------------------

class TestProviderInterface:
    def test_import(self):
        from notion_brain import NotionBrainProvider, register
        assert NotionBrainProvider is not None
        assert callable(register)

    def test_has_name(self):
        from notion_brain import NotionBrainProvider
        provider = NotionBrainProvider()
        assert provider.name == "notion_brain"

    def test_is_available_without_key(self):
        from notion_brain import NotionBrainProvider
        with patch("notion_brain.store.get_api_key", return_value=None):
            provider = NotionBrainProvider()
            assert provider.is_available() is False

    def test_is_available_with_key(self):
        from notion_brain import NotionBrainProvider
        with patch("notion_brain.store.get_api_key", return_value="test-key"):
            provider = NotionBrainProvider()
            assert provider.is_available() is True

    def test_tool_schemas_count(self):
        from notion_brain import ALL_TOOL_SCHEMAS
        assert len(ALL_TOOL_SCHEMAS) == 5

    def test_tool_schema_names(self):
        from notion_brain import ALL_TOOL_SCHEMAS
        names = [s["name"] for s in ALL_TOOL_SCHEMAS]
        expected = [
            "notion_brain_search",
            "notion_brain_remember",
            "notion_brain_task",
            "notion_brain_content",
            "notion_brain_research",
        ]
        for name in expected:
            assert name in names, f"Missing tool schema: {name}"

    def test_tool_schemas_have_required_fields(self):
        from notion_brain import ALL_TOOL_SCHEMAS
        for schema in ALL_TOOL_SCHEMAS:
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema
            params = schema["parameters"]
            assert "type" in params
            if schema["name"] != "notion_brain_search":
                # search requires 'query', others require 'action'
                pass


# ---------------------------------------------------------------------------
# handle_tool_call dispatch
# ---------------------------------------------------------------------------

class TestToolDispatch:
    def _make_initialized_provider(self):
        """Create a provider with mocked initialized state."""
        from notion_brain import NotionBrainProvider
        provider = NotionBrainProvider()
        provider._db_ids = {
            "tasks": "db-tasks-id",
            "content": "db-content-id",
            "research": "db-research-id",
            "projects": "db-projects-id",
            "career": "db-career-id",
            "entities": "db-entities-id",
            "memory": "db-memory-id",
        }
        provider._parent_page_id = "page-123"
        provider._hermes_home = "/tmp/test-hermes"
        provider._session_id = "test-session"
        return provider

    def test_search_dispatches(self):
        provider = self._make_initialized_provider()
        with patch("notion_brain.store.search_entries") as mock_search:
            mock_search.return_value = []
            result = provider.handle_tool_call("notion_brain_search", {"query": "test"})
            data = json.loads(result)
            assert "result" in data

    def test_search_requires_query(self):
        provider = self._make_initialized_provider()
        result = provider.handle_tool_call("notion_brain_search", {})
        # tool_error returns a plain string, not JSON
        assert "Missing" in result or "error" in result.lower()

    def test_remember_requires_title_content(self):
        provider = self._make_initialized_provider()
        with patch("notion_brain.store.create_database_page") as mock_create:
            mock_create.return_value = {"id": "new-page-123"}
            result = provider.handle_tool_call("notion_brain_remember", {"title": "Test", "content": "Content"})
            data = json.loads(result)
            assert "result" in data

    def test_remember_missing_fields(self):
        provider = self._make_initialized_provider()
        result = provider.handle_tool_call("notion_brain_remember", {"title": "Only title"})
        # tool_error returns a plain string, not JSON
        assert "Missing" in result or "error" in result.lower()

    def test_unknown_tool_returns_error(self):
        provider = self._make_initialized_provider()
        result = provider.handle_tool_call("nonexistent_tool", {})
        # tool_error returns a plain string, not JSON
        assert "Unknown" in result or "error" in result.lower()

    def test_task_list(self):
        provider = self._make_initialized_provider()
        with patch("notion_brain.store.query_database") as mock_query:
            mock_query.return_value = [
                {"id": "p1", "title": "Task 1", "properties": {"Status": {"name": "active"}, "Priority": {"name": "high"}, "Due": "2025-01-01", "Project": {"rich_text": [{"text": {"content": "Proj"}}]}}},
            ]
            result = provider.handle_tool_call("notion_brain_task", {"action": "list"})
            data = json.loads(result)
            assert "result" in data
            assert len(data.get("items", [])) == 1

    def test_content_create(self):
        provider = self._make_initialized_provider()
        with patch("notion_brain.store.create_database_page") as mock_create:
            mock_create.return_value = {"id": "content-page-1"}
            result = provider.handle_tool_call("notion_brain_content", {
                "action": "create", "title": "Tweet idea", "body": "Here's the text"
            })
            data = json.loads(result)
            assert "result" in data

    def test_research_save(self):
        provider = self._make_initialized_provider()
        with patch("notion_brain.store.create_database_page") as mock_create:
            mock_create.return_value = {"id": "research-page-1"}
            result = provider.handle_tool_call("notion_brain_research", {
                "action": "save", "title": "Finding", "content": "Results"
            })
            data = json.loads(result)
            assert "result" in data


# ---------------------------------------------------------------------------
# Domain mapping consistency
# ---------------------------------------------------------------------------

class TestDomainMapping:
    def test_all_domains_have_database(self):
        for domain_key in DOMAINS.keys():
            db = database_for_domain(domain_key)
            assert db in DATABASES, f"Domain {domain_key} -> DB {db} unknown"

    def test_db_keys_match_databases(self):
        assert set(DOMAIN_DATABASE.values()) == set(DATABASES.keys())

    def test_normalize_coverage(self):
        for domain in DOMAIN_DATABASE:
            norm = normalize_domain(domain)
            assert norm == domain, f"normalize_domain({domain}) should be identity"


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

class TestStoreHelpers:
    def test_title_property(self):
        prop = title_property("Hello")
        assert "title" in prop
        assert isinstance(prop["title"], list)
        assert prop["title"][0]["text"]["content"] == "Hello"

    def test_select_property(self):
        prop = select_property("option-a")
        assert prop["select"]["name"] == "option-a"

    def test_multi_select(self):
        prop = multi_select_property(["a", "b"])
        names = [o["name"] for o in prop["multi_select"]]
        assert "a" in names and "b" in names

    def test_multi_select_truncation(self):
        prop = multi_select_property(["x" * 100])
        assert all(len(o["name"]) <= 80 for o in prop["multi_select"])

    def test_multi_select_empty(self):
        prop = multi_select_property([])
        assert prop["multi_select"] == []

    def test_status_property(self):
        prop = status_property("done")
        assert prop["status"]["name"] == "done"

    def test_rich_text_property(self):
        prop = rich_text_property("some text")
        assert prop["rich_text"][0]["text"]["content"] == "some text"

    def test_rich_text_truncation(self):
        prop = rich_text_property("x" * 3000)
        assert len(prop["rich_text"][0]["text"]["content"]) == 2000

    def test_api_key_env(self):
        with patch.dict(os.environ, {}, clear=True):
            from notion_brain.store import get_api_key
            assert get_api_key() is None
        with patch.dict(os.environ, {"NOTION_API_KEY": "test-key-123"}):
            from importlib import reload

            import notion_brain.store as store_mod
            reload(store_mod)
            assert store_mod.get_api_key() == "test-key-123"
