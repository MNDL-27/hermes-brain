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
            assert "Task 1" in data["result"]

    def test_task_update_rejects_unknown_status(self):
        """Status updates must validate against the DB's option set, not guess."""
        provider = self._make_initialized_provider()
        # Tasks DB schema only allows active/done/needs_review
        with patch("notion_brain.store.get_database") as mock_get:
            mock_get.return_value = {
                "properties": {
                    "Status": {
                        "status": {
                            "options": [
                                {"name": "active"},
                                {"name": "done"},
                                {"name": "needs_review"},
                            ]
                        }
                    }
                }
            }
            with patch("notion_brain.store.update_page") as mock_update:
                result = provider.handle_tool_call(
                    "notion_brain_task",
                    {"action": "update", "page_id": "page-1", "status": "draft"},
                )
                data = json.loads(result)
                assert "Error" in data["result"], data
                assert "draft" in data["result"]
                assert "active" in data["result"]
                mock_update.assert_not_called()

    def test_task_update_accepts_known_status(self):
        provider = self._make_initialized_provider()
        with patch("notion_brain.store.get_database") as mock_get:
            mock_get.return_value = {
                "properties": {
                    "Status": {
                        "status": {
                            "options": [{"name": "active"}, {"name": "done"}, {"name": "needs_review"}]
                        }
                    }
                }
            }
            with patch("notion_brain.store.update_page") as mock_update:
                mock_update.return_value = {"id": "page-1"}
                result = provider.handle_tool_call(
                    "notion_brain_task",
                    {"action": "complete", "page_id": "page-1"},
                )
                data = json.loads(result)
                assert "Task completed" in data["result"]
                # Status payload was written with a valid option name.
                args = mock_update.call_args.args
                assert args[1]["Status"]["status"]["name"] == "done"

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

    def test_direct_tools_redact_secrets(self):
        provider = self._make_initialized_provider()
        secret = "sk-A1B2C3D4E5F6G7H8"
        redacted = "[REDACTED_SECRET]"

        mock_schema = {
            "properties": {
                "title": {"title": {}},
                "Project": {"rich_text": {}},
                "Tags": {"multi_select": {}},
                "Status": {"status": {}},
                "Domain": {"select": {}},
                "Confidence": {"select": {}},
                "Kind": {"select": {}},
                "Entities": {"rich_text": {}},
                "Content": {"rich_text": {}},
            }
        }

        with patch("notion_brain.store.get_database") as mock_get:
            mock_get.return_value = mock_schema

            # 1. Test notion_brain_task redacts secrets in title, content, and tags
            with patch("notion_brain.store.create_database_page") as mock_create:
                mock_create.return_value = {"id": "task-page-secret"}
                provider.handle_tool_call("notion_brain_task", {
                    "action": "create",
                    "title": f"Fix key {secret}",
                    "content": f"Content with {secret}",
                    "tags": [f"tag-{secret}", "safe-tag"],
                })
                assert mock_create.call_count == 1
                args, kwargs = mock_create.call_args
                properties = args[1]
                assert secret not in properties["title"]["title"][0]["text"]["content"]
                assert redacted in properties["title"]["title"][0]["text"]["content"]
                assert secret not in properties["Content"]["rich_text"][0]["text"]["content"]
                assert redacted in properties["Content"]["rich_text"][0]["text"]["content"]
                tag_names = [t["name"] for t in properties["Tags"]["multi_select"]]
                assert f"tag-{secret}" not in tag_names
                assert f"tag-{redacted}" in tag_names
                assert "safe-tag" in tag_names

            # 2. Test notion_brain_content redacts secrets in title, body, and tags
            with patch("notion_brain.store.create_database_page") as mock_create:
                mock_create.return_value = {"id": "content-page-secret"}
                provider.handle_tool_call("notion_brain_content", {
                    "action": "create",
                    "title": f"Idea {secret}",
                    "body": f"Post my secret: {secret}",
                    "tags": [secret],
                })
                assert mock_create.call_count == 1
                args, kwargs = mock_create.call_args
                properties = args[1]
                assert secret not in properties["title"]["title"][0]["text"]["content"]
                assert redacted in properties["title"]["title"][0]["text"]["content"]
                assert secret not in properties["Content"]["rich_text"][0]["text"]["content"]
                assert redacted in properties["Content"]["rich_text"][0]["text"]["content"]
                tag_names = [t["name"] for t in properties["Tags"]["multi_select"]]
                assert secret not in tag_names
                assert redacted in tag_names

            # 3. Test notion_brain_research redacts secrets in title, content, and tags
            with patch("notion_brain.store.create_database_page") as mock_create:
                mock_create.return_value = {"id": "research-page-secret"}
                provider.handle_tool_call("notion_brain_research", {
                    "action": "save",
                    "title": f"Research on {secret}",
                    "content": f"Confidential {secret}",
                    "tags": [f"tag-{secret}"],
                })
                assert mock_create.call_count == 1
                args, kwargs = mock_create.call_args
                properties = args[1]
                assert secret not in properties["title"]["title"][0]["text"]["content"]
                assert redacted in properties["title"]["title"][0]["text"]["content"]
                assert secret not in properties["Content"]["rich_text"][0]["text"]["content"]
                assert redacted in properties["Content"]["rich_text"][0]["text"]["content"]
                tag_names = [t["name"] for t in properties["Tags"]["multi_select"]]
                assert f"tag-{secret}" not in tag_names
                assert f"tag-{redacted}" in tag_names

            # 4. Test notion_brain_task update action redacts title
            with patch("notion_brain.store.update_page") as mock_update:
                mock_update.return_value = {"id": "task-page-secret"}
                provider.handle_tool_call("notion_brain_task", {
                    "action": "update",
                    "page_id": "task-page-secret",
                    "title": f"New title {secret}",
                })
                assert mock_update.call_count == 1
                args, kwargs = mock_update.call_args
                properties = args[1]
                assert secret not in properties["title"]["title"][0]["text"]["content"]
                assert redacted in properties["title"]["title"][0]["text"]["content"]


# ---------------------------------------------------------------------------
# Merge helpers for disk-only entries
# ---------------------------------------------------------------------------

class TestMergeDiskOnly:
    """Tests for _merge_disk_only and _merge_user_disk_only."""

    # --- MEMORY.md format (_merge_disk_only) ---
    # Blocks separated by ---, each with name: / domain: / kind: / tags: lines

    def test_merge_disk_only_no_disk_text(self):
        from notion_brain.helpers import _merge_disk_only
        entries = [{"title": "Foo", "properties": {"Content": "bar"}}]
        result = _merge_disk_only(entries, "")
        assert result == entries

    def test_merge_disk_only_keeps_new_title(self):
        from notion_brain.helpers import _merge_disk_only
        notion = [{"title": "Already", "properties": {"Content": "x"}}]
        disk = "---\nname: New Entry\ndomain: Memory\nkind: note\ntags: a, b\n---\nSome body text\n"
        result = _merge_disk_only(notion, disk)
        titles = {e["title"] for e in result}
        assert "Already" in titles
        assert "New Entry" in titles

    def test_merge_disk_only_drops_duplicate_title(self):
        from notion_brain.helpers import _merge_disk_only
        notion = [{"title": "Duplicate", "properties": {"Content": "x"}}]
        disk = "---\nname: Duplicate\ndomain: Memory\nkind: note\n---\nBody\n"
        result = _merge_disk_only(notion, disk)
        assert len(result) == 1

    # --- USER.md format (_merge_user_disk_only) ---
    # # User Profile\n## Title\ncontent

    USER_DISK_TEXT = (
        "# User Profile\n"
        "## Code Style Preference\n"
        "I prefer functional style, no classes.\n"
        "## Editing Tools\n"
        "Use VSCode with Vim keybindings.\n"
        "## Already In Notion\n"
        "This should be dropped.\n"
    )

    def test_merge_user_disk_only_no_disk_text(self):
        from notion_brain.helpers import _merge_user_disk_only
        entries = [{"title": "Foo", "properties": {"Content": "bar"}}]
        result = _merge_user_disk_only(entries, "")
        assert result == entries

    def test_merge_user_disk_only_parses_sections(self):
        from notion_brain.helpers import _merge_user_disk_only
        notion = [{"title": "Already In Notion", "properties": {"Content": "from notion", "Kind": "preference"}}]
        result = _merge_user_disk_only(notion, self.USER_DISK_TEXT)
        titles = {e["title"] for e in result}
        # "Already In Notion" should be dropped (already in notion entries)
        assert "Code Style Preference" in titles
        assert "Editing Tools" in titles
        assert len(result) == 3  # 1 notion + 2 disk-only

    def test_merge_user_disk_only_content_preserved(self):
        from notion_brain.helpers import _merge_user_disk_only
        notion: list = []
        result = _merge_user_disk_only(notion, self.USER_DISK_TEXT)
        code_entry = next(e for e in result if e["title"] == "Code Style Preference")
        assert "functional style" in code_entry["properties"]["Content"]
        assert code_entry["properties"]["Kind"] == "preference"

    def test_merge_user_disk_only_empty_user_md(self):
        from notion_brain.helpers import _merge_user_disk_only
        result = _merge_user_disk_only([], "# User Profile\n")
        assert result == []

    def test_merge_user_disk_only_all_duplicates(self):
        from notion_brain.helpers import _merge_user_disk_only
        notion = [
            {"title": "Code Style Preference", "properties": {"Content": "c"}},
            {"title": "Editing Tools", "properties": {"Content": "c"}},
            {"title": "Already In Notion", "properties": {"Content": "c"}},
        ]
        result = _merge_user_disk_only(notion, self.USER_DISK_TEXT)
        assert len(result) == 3  # only notion entries

    # --- USER.md without the leading "# User Profile" header ---

    def test_merge_user_disk_only_no_profile_header(self):
        from notion_brain.helpers import _merge_user_disk_only
        disk = "## Preference One\nBody one.\n\n## Preference Two\nBody two.\n"
        result = _merge_user_disk_only([], disk)
        titles = {e["title"] for e in result}
        assert titles == {"Preference One", "Preference Two"}
# ---------------------------------------------------------------------------

class TestDomainMapping:
    def test_all_domains_have_database(self):
        for domain_key in DOMAINS:
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


# ---------------------------------------------------------------------------
# Regression: exception log redaction (Sentinel CRITICAL — PR #13)
# ---------------------------------------------------------------------------

class TestExceptionLogRedaction:
    """Production paths must redact secrets in exception messages before logging or returning."""

    SECRET = "sk-A1B2C3D4E5F6G7H8"

    def _assert_no_leak(self, caplog, secret: str, logger_name: str = "notion_brain") -> None:
        assert secret not in caplog.text
        assert "[REDACTED_SECRET]" in caplog.text

    @patch("notion_brain.bootstrap.ensure_brain")
    def test_initialize_error_redacts_secrets(self, mock_ensure, caplog):
        """provider.initialize() logs bootstrap exception with redaction."""
        from notion_brain import NotionBrainProvider
        caplog.set_level("ERROR", logger="notion_brain")
        mock_ensure.side_effect = RuntimeError(f"db connection: {self.SECRET}")
        provider = NotionBrainProvider()
        provider.initialize("test-session", hermes_home="/tmp/test")
        self._assert_no_leak(caplog, self.SECRET)

    @patch("notion_brain.store.create_database_page")
    @patch("notion_brain.store.get_database")
    def test_database_properties_error_redacts_secrets(self, mock_get_db, mock_create, caplog):
        """_database_properties logs schema-fetch exception with redaction."""
        from notion_brain import NotionBrainProvider
        from notion_brain import schema as S
        caplog.set_level("WARNING", logger="notion_brain")
        mock_get_db.side_effect = RuntimeError(f"schema read: {self.SECRET}")
        mock_create.side_effect = RuntimeError("NOTION_API_KEY not set")
        provider = NotionBrainProvider()
        provider._session_id = "test"
        provider._db_ids = {"memory": "db-id"}
        entry = S.BrainEntry(domain="memory", title="test", content="test", kind="note").normalized()
        try:
            provider._write_entry_raw("db-id", entry)
        except RuntimeError:
            pass
        self._assert_no_leak(caplog, self.SECRET)

    @patch("notion_brain.store.get_database")
    def test_validated_status_error_redacts_secrets(self, mock_get_db, caplog):
        """_validated_status logs schema-read exception with redaction."""
        from notion_brain import NotionBrainProvider
        caplog.set_level("WARNING", logger="notion_brain")
        mock_get_db.side_effect = RuntimeError(f"status schema: {self.SECRET}")
        provider = NotionBrainProvider()
        provider._db_ids = {"tasks": "db-id"}
        _, err = provider._validated_status("active", "tasks")
        assert err is None  # fallback path taken
        self._assert_no_leak(caplog, self.SECRET)

    def test_get_url_db_error_redacts_secrets(self, caplog):
        """get_url logs database-fetch exception with redaction."""
        from notion_brain import bootstrap
        caplog.set_level("DEBUG", logger="notion_brain.bootstrap")
        fake_cache = {"parent_page_id": "parent-123", "db_tasks": "db-456"}
        with patch("notion_brain.bootstrap._load_cache", return_value=fake_cache), \
             patch("notion_brain.store.get_page") as mock_pg, \
             patch("notion_brain.store.get_database") as mock_db:
            mock_pg.side_effect = RuntimeError(f"parent fetch: {self.SECRET}")
            mock_db.side_effect = RuntimeError(f"db fetch: {self.SECRET}")
            bootstrap.get_url(Path("/tmp/fake-hermes-home"), db=True)
        self._assert_no_leak(caplog, self.SECRET, logger_name="notion_brain.bootstrap")

    def test_cache_write_error_redacts_secrets(self, caplog):
        """_save_cache logs cache-write exception with redaction."""
        from notion_brain import bootstrap
        caplog.set_level("WARNING", logger="notion_brain.bootstrap")
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "sub" / "cache.json"
            with patch.object(Path, "write_text", side_effect=RuntimeError(f"disk full: {self.SECRET}")):
                bootstrap._save_cache(cache_path, {"key": "val"})
            self._assert_no_leak(caplog, self.SECRET, logger_name="notion_brain.bootstrap")

    def test_health_report_error_redacts_secrets(self, caplog):
        """health_report interpolates exception with redaction, not raw."""
        from notion_brain import bootstrap
        caplog.set_level("INFO")
        fake_cache = {"parent_page_id": "nonexistent-parent-uuid", "db_tasks": "nonexistent-db-uuid"}
        with patch("notion_brain.bootstrap._load_cache", return_value=fake_cache), \
             patch("notion_brain.store.get_page") as mock_pg, \
             patch("notion_brain.store.get_database") as mock_db:
            mock_pg.side_effect = RuntimeError(f"page error: {self.SECRET}")
            mock_db.side_effect = RuntimeError(f"db error: {self.SECRET}")
            report = bootstrap.health_report(Path("/tmp/fake-hermes-home"))
        assert self.SECRET not in report
        assert "[REDACTED_SECRET]" in report

    def test_handle_tool_call_error_redacts_secrets(self, caplog):
        """Tool call error responses redact secrets before returning JSON to the caller."""
        import json

        from notion_brain import NotionBrainProvider
        caplog.set_level("WARNING", logger="notion_brain")
        provider = NotionBrainProvider()

        # mock a tool to raise an exception with a secret
        def failing_tool(*args, **kwargs):
            raise RuntimeError(f"tool error: {self.SECRET}")

        with patch.object(provider, "_tool_search", side_effect=failing_tool):
            result_json = provider.handle_tool_call("notion_brain_search", {"query": "test"})

        result = json.loads(result_json)
        assert result["error"] is True
        assert self.SECRET not in result["result"]
        assert "[REDACTED_SECRET]" in result["result"]
        self._assert_no_leak(caplog, self.SECRET)
