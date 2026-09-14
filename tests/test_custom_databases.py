"""Tests for user-defined custom databases and onboarding setup."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from notion_brain import bootstrap
from notion_brain import schema as S
from notion_brain.provider import NotionBrainProvider


@pytest.fixture(autouse=True)
def clean_custom_domains():
    S.clear_custom_domains()
    yield
    S.clear_custom_domains()


def test_build_custom_database_props():
    props = bootstrap.build_custom_database_props(
        "fitness",
        {
            "Reps": "number",
            "Exercise": "select",
            "Workout Date": "date",
            "Notes": "rich_text",
            "Completed": "checkbox",
        },
    )

    # Base properties inherited
    assert "title" in props
    assert "Domain" in props
    assert props["Domain"]["select"]["options"][0]["name"] == "fitness"
    assert "Status" in props
    assert "Tags" in props
    assert "Confidence" in props

    # Custom properties mapped
    assert props["Reps"] == {"number": {}}
    assert props["Exercise"] == {"select": {}}
    assert props["Workout Date"] == {"date": {}}
    assert props["Notes"] == {"rich_text": {}}
    assert props["Completed"] == {"checkbox": {}}


def test_custom_domain_registration_and_normalization():
    S.register_custom_domain(
        "fitness",
        "Fitness & Workouts",
        db_key="fitness_db",
        description="Workout logs and form notes",
        custom_fields={"Reps": "number", "Exercise": "select"},
    )

    assert "fitness" in S.get_all_domains()
    assert "fitness_db" in S.get_all_databases()
    assert S.normalize_domain("fitness") == "fitness"
    assert S.database_for_domain("fitness") == "fitness_db"

    # Alias normalization
    assert S.normalize_domain("tasks") == "daily_work"


def test_interactive_setup_with_answers(tmp_path):
    answers = {
        "standard_dbs": ["tasks", "projects", "memory"],
        "custom_dbs": [
            {
                "key": "finance",
                "title": "Expenses & Invoices",
                "description": "Financial records and invoices",
                "fields": {"Amount": "number", "Vendor": "select"},
            }
        ],
    }

    mock_db_create = MagicMock(side_effect=lambda parent, title, props: {"id": f"mock-{title.lower().replace(' ', '-')}"})
    mock_parent = MagicMock(return_value="parent-123")

    with patch.object(bootstrap.store, "create_database", mock_db_create), \
         patch.object(bootstrap, "_find_or_create_parent", mock_parent), \
         patch.object(bootstrap, "_find_existing_database", MagicMock(return_value="")), \
         patch.object(bootstrap.store, "get_page", MagicMock(return_value={"id": "parent-123"})):
        result = bootstrap.interactive_setup(tmp_path, answers=answers)

    assert result["parent_page_id"] == "parent-123"
    assert result["standard_count"] == 3
    assert result["custom_count"] == 1
    assert "tasks" in result["created_databases"]
    assert "projects" in result["created_databases"]
    assert "memory" in result["created_databases"]
    assert "finance" in result["created_databases"]

    # Verify cache saved properly
    cache_file = tmp_path / S.CACHE_FILE
    assert cache_file.exists()
    cached = json.loads(cache_file.read_text())
    assert cached["db_tasks"].startswith("mock-")
    assert cached["db_finance"].startswith("mock-")
    assert "finance" in cached["custom_databases"]


def test_provider_tool_schemas_includes_custom_domains():
    S.register_custom_domain(
        "fitness",
        "Fitness & Workouts",
        db_key="fitness",
        description="Workout tracking",
    )

    provider = NotionBrainProvider()
    schemas = provider.get_tool_schemas()
    remember_schema = next(s for s in schemas if s["name"] == "notion_brain_remember")
    search_schema = next(s for s in schemas if s["name"] == "notion_brain_search")

    assert "fitness" in remember_schema["parameters"]["properties"]["domain"]["description"]
    assert "fitness" in search_schema["parameters"]["properties"]["database"]["description"]
