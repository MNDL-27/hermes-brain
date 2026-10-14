"""Regression tests for FRE-16 / FRE-11.3: Centralized Notion authorization and IDOR guards.

Verifies:
1. store.verify_page_in_database validation, containment checks, normalization, and fail-closed behavior.
2. store.update_page, store.get_page, and store.delete_page with expected_database_id enforce containment.
3. provider.handle_tool_call rejects IDOR-style cross-database page_id manipulation for tasks, content, and research.
4. provider.handle_tool_call rejects page_ids belonging to parent pages or missing parents.
5. Error messages redact any secret substrings present in page IDs or exceptions.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from notion_brain import store
from notion_brain.provider import NotionBrainProvider


class TestStoreAuthorizationPrimitives:
    """Direct unit tests for store.py authorization functions."""

    def test_normalize_id_handles_various_formats(self) -> None:
        assert store.normalize_id(None) == ""
        assert store.normalize_id("") == ""
        assert store.normalize_id("  ") == ""
        assert (
            store.normalize_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
            == "a1b2c3d4e5f67890abcdef1234567890"
        )
        assert (
            store.normalize_id("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")
            == "a1b2c3d4e5f67890abcdef1234567890"
        )
        assert store.normalize_id("  a1b2c3d4e5f6  ") == "a1b2c3d4e5f6"

    def test_verify_page_in_database_missing_arguments(self) -> None:
        auth, reason = store.verify_page_in_database("", "db-1")
        assert auth is False
        assert reason == "page_id is required"

        auth, reason = store.verify_page_in_database("page-1", "")
        assert auth is False
        assert reason == "expected_database_id is required"

    def test_verify_page_in_database_fails_closed_on_get_page_error(self) -> None:
        with patch("notion_brain.store.get_page", side_effect=RuntimeError("Notion API 404: Not found")):
            auth, reason = store.verify_page_in_database("missing-page", "db-1")
            assert auth is False
            assert reason is not None
            assert "could not retrieve page" in reason
            assert "404" in reason

    def test_verify_page_in_database_rejects_missing_parent(self) -> None:
        with patch("notion_brain.store.get_page", return_value={"id": "page-1"}):
            auth, reason = store.verify_page_in_database("page-1", "db-1")
            assert auth is False
            assert reason == "page has no parent structure"

    def test_verify_page_in_database_rejects_non_database_parent(self) -> None:
        # E.g. parent is workspace or page_id (child of parent page)
        with patch(
            "notion_brain.store.get_page",
            return_value={"id": "page-1", "parent": {"type": "page_id", "page_id": "root-page"}},
        ):
            auth, reason = store.verify_page_in_database("page-1", "db-1")
            assert auth is False
            assert reason is not None
            assert "not a database" in reason

    def test_verify_page_in_database_rejects_database_mismatch(self) -> None:
        with patch(
            "notion_brain.store.get_page",
            return_value={"id": "page-1", "parent": {"type": "database_id", "database_id": "other-db"}},
        ):
            auth, reason = store.verify_page_in_database("page-1", "expected-db")
            assert auth is False
            assert reason is not None
            assert "page belongs to database other-db, expected expected-db" in reason

    def test_verify_page_in_database_accepts_matching_database_normalized(self) -> None:
        with patch(
            "notion_brain.store.get_page",
            return_value={
                "id": "page-1",
                "parent": {
                    "type": "database_id",
                    "database_id": "12345678-ABCD-ef01-2345-6789abcdef01",
                },
            },
        ):
            auth, reason = store.verify_page_in_database(
                "page-1", "12345678abcdef0123456789abcdef01"
            )
            assert auth is True
            assert reason is None

    def test_update_page_enforces_expected_database_id(self) -> None:
        with patch(
            "notion_brain.store.get_page",
            return_value={"id": "p1", "parent": {"database_id": "wrong-db"}},
        ):
            with pytest.raises(store.AuthorizationError) as exc_info:
                store.update_page("p1", {"title": {}}, expected_database_id="right-db")
            assert "Authorization denied for page p1" in str(exc_info.value)

        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "p1", "parent": {"database_id": "right-db"}},
            ),
            patch("notion_brain.store._request", return_value={"id": "p1"}) as mock_req,
        ):
            res = store.update_page("p1", {"title": {}}, expected_database_id="right-db")
            assert res == {"id": "p1"}
            mock_req.assert_called_once_with("PATCH", "/pages/p1", {"properties": {"title": {}}})

    def test_get_page_enforces_expected_database_id(self) -> None:
        with patch(
            "notion_brain.store._request",
            return_value={"id": "p1", "parent": {"database_id": "wrong-db"}},
        ):
            with pytest.raises(store.AuthorizationError):
                store.get_page("p1", expected_database_id="target-db")

        with patch(
            "notion_brain.store._request",
            return_value={"id": "p1", "parent": {"database_id": "target-db"}},
        ):
            page = store.get_page("p1", expected_database_id="target-db")
            assert page["id"] == "p1"

    def test_delete_page_enforces_expected_database_id(self) -> None:
        with patch(
            "notion_brain.store.get_page",
            return_value={"id": "p1", "parent": {"database_id": "wrong-db"}},
        ):
            with pytest.raises(store.AuthorizationError):
                store.delete_page("p1", expected_database_id="target-db")

        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "p1", "parent": {"database_id": "target-db"}},
            ),
            patch("notion_brain.store._request", return_value={"id": "p1", "archived": True}),
        ):
            res = store.delete_page("p1", expected_database_id="target-db")
            assert res["archived"] is True


class TestProviderIDORMitigation:
    """Integration-level regression tests for provider tool authorization boundaries."""

    @pytest.fixture
    def provider(self) -> NotionBrainProvider:
        p = NotionBrainProvider()
        p._db_ids = {
            "tasks": "db-tasks-uuid",
            "content": "db-content-uuid",
            "research": "db-research-uuid",
            "projects": "db-projects-uuid",
            "career": "db-career-uuid",
            "entities": "db-entities-uuid",
            "memory": "db-memory-uuid",
        }
        p._parent_page_id = "parent-page-uuid"
        return p

    def test_task_update_rejects_cross_database_idor(self, provider: NotionBrainProvider) -> None:
        # Caller tries to update a page belonging to content database using task tool
        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "content-page-id", "parent": {"database_id": "db-content-uuid"}},
            ),
            patch("notion_brain.store.update_page") as mock_update,
        ):
            res_str = provider.handle_tool_call(
                "notion_brain_task",
                {"action": "update", "page_id": "content-page-id", "title": "Injected task"},
            )
            data = json.loads(res_str)
            assert "Error:" in data["result"]
            assert "does not belong to tasks database" in data["result"]
            mock_update.assert_not_called()

    def test_task_complete_rejects_cross_database_idor(self, provider: NotionBrainProvider) -> None:
        # Caller tries to complete a page belonging to parent page / workspace
        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "root-page-id", "parent": {"type": "page_id", "page_id": "root"}},
            ),
            patch("notion_brain.store.update_page") as mock_update,
        ):
            res_str = provider.handle_tool_call(
                "notion_brain_task",
                {"action": "complete", "page_id": "root-page-id"},
            )
            data = json.loads(res_str)
            assert "Error:" in data["result"]
            assert "does not belong to tasks database" in data["result"]
            mock_update.assert_not_called()

    def test_content_update_rejects_cross_database_idor(self, provider: NotionBrainProvider) -> None:
        # Caller tries to update a task page using content tool
        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "task-page-id", "parent": {"database_id": "db-tasks-uuid"}},
            ),
            patch("notion_brain.store.update_page") as mock_update,
        ):
            res_str = provider.handle_tool_call(
                "notion_brain_content",
                {"action": "update", "page_id": "task-page-id", "title": "Tampered content"},
            )
            data = json.loads(res_str)
            assert "Error:" in data["result"]
            assert "does not belong to content database" in data["result"]
            mock_update.assert_not_called()

    def test_content_publish_rejects_cross_database_idor(self, provider: NotionBrainProvider) -> None:
        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "research-page-id", "parent": {"database_id": "db-research-uuid"}},
            ),
            patch("notion_brain.store.update_page") as mock_update,
        ):
            res_str = provider.handle_tool_call(
                "notion_brain_content",
                {"action": "publish", "page_id": "research-page-id"},
            )
            data = json.loads(res_str)
            assert "Error:" in data["result"]
            assert "does not belong to content database" in data["result"]
            mock_update.assert_not_called()

    def test_content_archive_rejects_cross_database_idor(self, provider: NotionBrainProvider) -> None:
        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "other-page-id", "parent": {"database_id": "db-other-uuid"}},
            ),
            patch("notion_brain.store.update_page") as mock_update,
        ):
            res_str = provider.handle_tool_call(
                "notion_brain_content",
                {"action": "archive", "page_id": "other-page-id"},
            )
            data = json.loads(res_str)
            assert "Error:" in data["result"]
            assert "does not belong to content database" in data["result"]
            mock_update.assert_not_called()

    def test_research_update_authorized_and_idor_blocked(self, provider: NotionBrainProvider) -> None:
        # 1. IDOR rejected when page is not in research db
        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "task-page-id", "parent": {"database_id": "db-tasks-uuid"}},
            ),
            patch("notion_brain.store.update_page") as mock_update,
        ):
            res_str = provider.handle_tool_call(
                "notion_brain_research",
                {"action": "update", "page_id": "task-page-id", "title": "Tampered research"},
            )
            data = json.loads(res_str)
            assert "Error:" in data["result"]
            assert "does not belong to research database" in data["result"]
            mock_update.assert_not_called()

        # 2. Authorized update succeeds
        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": "res-page-id", "parent": {"database_id": "db-research-uuid"}},
            ),
            patch(
                "notion_brain.store.get_database",
                return_value={"properties": {"Status": {"status": {"options": [{"name": "active"}]}}}},
            ),
            patch("notion_brain.store.update_page") as mock_update,
        ):
            res_str = provider.handle_tool_call(
                "notion_brain_research",
                {
                    "action": "update",
                    "page_id": "res-page-id",
                    "title": "New Title",
                    "content": "New Notes",
                },
            )
            data = json.loads(res_str)
            assert "Research updated for page ID: res-page-id" in data["result"]
            mock_update.assert_called_once()
            args, kwargs = mock_update.call_args
            assert args[0] == "res-page-id"
            assert kwargs["expected_database_id"] == "db-research-uuid"

    def test_secret_redaction_in_idor_error_messages(self, provider: NotionBrainProvider) -> None:
        secret_token = "sk-ant-api03-abcdef12345678901234567890"
        with (
            patch(
                "notion_brain.store.get_page",
                return_value={"id": f"page-{secret_token}", "parent": {"database_id": "wrong-db"}},
            ),
            patch("notion_brain.store.update_page") as mock_update,
        ):
            res_str = provider.handle_tool_call(
                "notion_brain_task",
                {"action": "update", "page_id": f"page-{secret_token}", "title": "Test"},
            )
            assert secret_token not in res_str
            assert "[REDACTED_SECRET]" in res_str
            mock_update.assert_not_called()
