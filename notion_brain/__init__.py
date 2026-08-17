"""Hermes memory provider plugin backed by Notion.

7 Notion databases (Memory, Tasks, Projects, Content, Research, Career, Entities)
are organized under a "Hermes Brain" parent page. Background sync threads classify
conversation turns using heuristics and write entries to the correct database.

Auth:   NOTION_API_KEY env var
Cache:  $HERMES_HOME/notion_brain.json
"""

from __future__ import annotations

__version__ = "1.0.2"

from .extract import classify_turn as classify_text
from .provider import NotionBrainProvider, register
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
    "register",
]
