"""NotionBrainProvider — persistent long-term memory via a Notion workspace brain.

This module is a lazy facade for backward compatibility. The actual provider
implementation lives in ``notion_brain.provider``.

7 Notion databases (Memory, Tasks, Projects, Content, Research, Career, Entities)
are organized under a "Hermes Brain" parent page. Background sync threads classify
conversation turns using heuristics and write entries to the correct database.

Auth:   NOTION_API_KEY env var
Cache:  $HERMES_HOME/notion_brain.json
"""

from __future__ import annotations

from typing import Any

# Lazy imports — Hermes runtime modules (agent, tools) may not be available
# in dev/test environments. They are imported inside methods where needed.
# from agent.memory_manager import sanitize_context
# from agent.memory_provider import MemoryProvider
# from tools.registry import tool_error

# Re-export schema helpers for backward compatibility
from .schema import (
    BrainEntry,
    CACHE_FILE,
    clean_title,
    compact,
    CONFIDENCES,
    DATABASES,
    database_for_domain,
    DEFAULT_PARENT_PAGE,
    DOMAINS,
    DOMAIN_DATABASE,
    dedupe_strings,
    keyword_tokens,
    NOTION_API_VERSION,
    normalize_domain,
    redact_secrets,
    STATUSES,
)

# Re-export store helpers for backward compatibility
from .store import (
    create_database_page,
    create_page,
    date_property,
    get_database,
    get_page,
    multi_select_property,
    number_property,
    query_database,
    rich_text_property,
    search_entries,
    search_page_by_title,
    select_property,
    status_property,
    title_property,
    update_page,
)

# Re-export tool schemas for backward compatibility
from .provider import (
    ALL_TOOL_SCHEMAS,
    CONTENT_SCHEMA,
    NotionBrainProvider,
    REMEMBER_SCHEMA,
    RESEARCH_SCHEMA,
    SEARCH_SCHEMA,
    TASK_SCHEMA,
)

# Re-export bootstrap helpers for backward compatibility
from .bootstrap import (
    ensure_brain,
    get_url,
    health_report,
    read_memory_from_disk,
    read_user_from_disk,
    reset_databases,
)

# Re-export extract for backward compatibility
from .extract import classify_turn as classify_text


# Lazy facade: provider is imported on first access
def __getattr__(name: str) -> Any:
    """Lazy attribute access for backward compatibility."""
    if name == "register":
        from .provider import register

        return register

    # Legacy helpers that were in __init__.py
    if name == "_sanitize_context":
        from .provider import _sanitize_context

        return _sanitize_context
    if name == "_tool_error":
        from .provider import _tool_error

        return _tool_error
    if name == "_merge_disk_only":
        from .provider import _merge_disk_only

        return _merge_disk_only
    if name == "_merge_user_disk_only":
        from .provider import _merge_user_disk_only

        return _merge_user_disk_only
    if name == "_user_disk_entry":
        from .provider import _user_disk_entry

        return _user_disk_entry
    if name == "_paragraph_blocks":
        from .provider import _paragraph_blocks

        return _paragraph_blocks

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Schema
    "BrainEntry",
    "CACHE_FILE",
    "clean_title",
    "compact",
    "CONFIDENCES",
    "DATABASES",
    "database_for_domain",
    "DEFAULT_PARENT_PAGE",
    "DOMAINS",
    "DOMAIN_DATABASE",
    "dedupe_strings",
    "keyword_tokens",
    "NOTION_API_VERSION",
    "normalize_domain",
    "redact_secrets",
    "STATUSES",
    # Store
    "create_database_page",
    "create_page",
    "date_property",
    "get_database",
    "get_page",
    "multi_select_property",
    "number_property",
    "query_database",
    "rich_text_property",
    "search_entries",
    "search_page_by_title",
    "select_property",
    "status_property",
    "title_property",
    "update_page",
    # Provider
    "ALL_TOOL_SCHEMAS",
    "CONTENT_SCHEMA",
    "NotionBrainProvider",
    "REMEMBER_SCHEMA",
    "RESEARCH_SCHEMA",
    "SEARCH_SCHEMA",
    "TASK_SCHEMA",
    # Bootstrap
    "ensure_brain",
    "get_url",
    "health_report",
    "read_memory_from_disk",
    "read_user_from_disk",
    "reset_databases",
    # Extract
    "classify_text",
    # Lazy
    "register",
    "_sanitize_context",
    "_tool_error",
    "_merge_disk_only",
    "_merge_user_disk_only",
    "_user_disk_entry",
    "_paragraph_blocks",
]