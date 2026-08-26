"""Hermes memory provider plugin backed by Notion.

7 Notion databases (Memory, Tasks, Projects, Content, Research, Career, Entities)
are organized under a "Hermes Brain" parent page. Background sync threads classify
conversation turns using heuristics and write entries to the correct database.

Auth:   NOTION_API_KEY env var
Cache:  $HERMES_HOME/notion_brain.json
"""

from __future__ import annotations

import json

__version__ = "1.0.2"

from .extract import classify_turn as classify_text
from .provider import NotionBrainProvider, register
from .schema import redact_secrets
from .schemas import (
    ALL_TOOL_SCHEMAS,
    CONTENT_SCHEMA,
    REMEMBER_SCHEMA,
    RESEARCH_SCHEMA,
    SEARCH_SCHEMA,
    TASK_SCHEMA,
)

__all__ = [
    "ALL_TOOL_SCHEMAS",
    "CONTENT_SCHEMA",
    "REMEMBER_SCHEMA",
    "RESEARCH_SCHEMA",
    "SEARCH_SCHEMA",
    "TASK_SCHEMA",
    "NotionBrainProvider",
    "classify_text",
    "ensure_brain",
    "register",
    "remember",
    "search_entries",
]


# --- Top-level helpers for examples and standalone scripts ----------------

_DEFAULT_HERMES_HOME = "~/.hermes"


def _session_provider(hermes_home: str | None = None) -> NotionBrainProvider:
    """Construct a provider pre-initialized for the current environment."""
    provider = NotionBrainProvider()
    provider.initialize(session_id="script", hermes_home=hermes_home or _DEFAULT_HERMES_HOME)
    return provider


def ensure_brain(hermes_home: str | None = None) -> dict[str, str]:
    """Bootstrap the Notion workspace and return the page/db ID cache."""
    from . import bootstrap

    return bootstrap.ensure_brain(hermes_home or _DEFAULT_HERMES_HOME)


def remember(
    title: str,
    content: str,
    *,
    domain: str = "memory",
    kind: str = "note",
    status: str = "active",
    tags: list[str] | None = None,
    entities: list[str] | None = None,
    hermes_home: str | None = None,
) -> dict:
    """Save an entry to the Notion brain and return a small confirmation dict."""
    provider = _session_provider(hermes_home)
    raw = provider.handle_tool_call(
        "notion_brain_remember",
        {
            "title": title,
            "content": content,
            "domain": domain,
            "kind": kind,
            "status": status,
            "tags": tags or [],
            "entities": entities or [],
        },
    )
    result = json.loads(raw)
    if result.get("error"):
        raise RuntimeError(redact_secrets(result["result"]))
    return {"status": "saved", "title": title, "message": result["result"]}


def search_entries(query: str, *, database: str = "all", max_results: int = 8,
                   hermes_home: str | None = None) -> list[dict]:
    """Search the Notion brain and return a list of result dicts."""
    provider = _session_provider(hermes_home)
    raw = provider.handle_tool_call(
        "notion_brain_search",
        {"query": query, "database": database, "max_results": max_results},
    )
    parsed = json.loads(raw)
    if parsed.get("error"):
        raise RuntimeError(redact_secrets(parsed["result"]))
    entries: list[dict] = []
    for line in (parsed["result"] or "").splitlines():
        if not line.startswith("- "):
            continue
        entries.append({"title": line[2:].strip()})
    return entries
