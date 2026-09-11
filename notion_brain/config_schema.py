"""Notion Brain's declared config surface — rendered by the generic desktop panel."""

from plugins.memory.config_schema import (
    KIND_SECRET,
    KIND_TEXT,
    STORAGE_FLAT_JSON,
    ProviderConfigSchema,
    ProviderField,
)

CONFIG_SCHEMA = ProviderConfigSchema(
    name="notion_brain",
    label="Hermes Brain (Notion)",
    storage=STORAGE_FLAT_JSON,
    fields=(
        ProviderField(
            key="notionApiKey",
            label="Notion API Key",
            kind=KIND_SECRET,
            description="Notion integration token. Create one at notion.so/my-integrations.",
            env_key="NOTION_API_KEY",
            placeholder="ntn_xxxxx_xxxxx",
            inline=True,
            group="Connection",
        ),
        ProviderField(
            key="hermesHome",
            label="Hermes Home",
            kind=KIND_TEXT,
            description="Directory for cache and config. Defaults to ~/.hermes.",
            default="~/.hermes",
            env_fallbacks=("HERMES_HOME",),
            placeholder="~/.hermes",
            inline=True,
            group="Connection",
        ),
    ),
)
