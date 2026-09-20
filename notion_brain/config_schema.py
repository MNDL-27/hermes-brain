"""Notion Brain's declared config surface — rendered by the generic desktop panel."""

try:
    from plugins.memory.config_schema import (
        KIND_SECRET,
        KIND_TEXT,
        STORAGE_FLAT_JSON,
        ProviderConfigSchema,
        ProviderField,
    )
except ImportError as _import_err:
    # Offline / test harness fallback — register stubs so downstream imports resolve.
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class ProviderField:  # type: ignore[no-redef]
        key: str
        label: str
        kind: str
        description: str = ""
        env_key: str | None = None
        env_fallbacks: tuple[str, ...] = ()
        placeholder: str = ""
        inline: bool = False
        group: str = ""
        default: str | None = None

    @dataclass(frozen=True)
    class ProviderConfigSchema:  # type: ignore[no-redef]
        name: str
        label: str
        storage: str
        fields: tuple[ProviderField, ...]

    KIND_SECRET: str = "secret"  # type: ignore[no-redef]
    KIND_TEXT: str = "text"  # type: ignore[no-redef]
    STORAGE_FLAT_JSON: str = "flat_json"  # type: ignore[no-redef]

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
