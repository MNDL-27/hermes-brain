from __future__ import annotations

import pytest

# Import CONFIG_SCHEMA from production module (has its own fallback for offline use)
from notion_brain.config_schema import CONFIG_SCHEMA, KIND_SECRET, KIND_TEXT, STORAGE_FLAT_JSON


def test_schema_metadata() -> None:
    """Verifies CONFIG_SCHEMA basic metadata (D-05, D-11, SCHEMA-01)."""
    assert CONFIG_SCHEMA is not None
    assert CONFIG_SCHEMA.name == "notion_brain"
    assert CONFIG_SCHEMA.label == "Hermes Brain (Notion)"
    assert CONFIG_SCHEMA.storage == STORAGE_FLAT_JSON
    assert len(CONFIG_SCHEMA.fields) == 2


def test_notion_api_key_field() -> None:
    """Verifies notionApiKey field contract (D-04, D-05, D-11)."""
    field = CONFIG_SCHEMA.fields[0]
    assert field.key == "notionApiKey"
    assert field.label == "Notion API Key"
    assert field.kind == KIND_SECRET
    assert field.description == "Notion integration token. Create one at notion.so/my-integrations."
    assert field.env_key == "NOTION_API_KEY"
    assert field.placeholder == "ntn_xxxxx_xxxxx"
    assert field.inline is True
    assert field.group == "Connection"
    assert field.default is None
    assert field.env_fallbacks == ()


def test_hermes_home_field() -> None:
    """Verifies hermesHome field contract (D-04, D-05, D-11)."""
    field = CONFIG_SCHEMA.fields[1]
    assert field.key == "hermesHome"
    assert field.label == "Hermes Home"
    assert field.kind == KIND_TEXT
    assert field.description == "Directory for cache and config. Defaults to ~/.hermes."
    assert field.default == "~/.hermes"
    assert field.env_fallbacks == ("HERMES_HOME",)
    assert field.placeholder == "~/.hermes"
    assert field.inline is True
    assert field.group == "Connection"
    assert field.env_key is None


def test_schema_immutability() -> None:
    """Verifies CONFIG_SCHEMA immutability (D-06, D-11, SCHEMA-02)."""
    assert isinstance(CONFIG_SCHEMA.fields, tuple)
    assert isinstance(CONFIG_SCHEMA.fields[1].env_fallbacks, tuple)

    with pytest.raises((AttributeError, TypeError)):
        CONFIG_SCHEMA.fields[0].label = "New Label"


def test_secret_safety() -> None:
    """Verifies secret safety guard (D-07, SCHEMA-02)."""
    field = CONFIG_SCHEMA.fields[0]
    assert field.kind == KIND_SECRET
    assert field.default is None
