"""Tool schemas for the Hermes agent runtime."""

from __future__ import annotations

from typing import Any

SEARCH_SCHEMA: dict[str, Any] = {
    "name": "notion_brain_search",
    "description": (
        "Semantic-text search across ALL Notion brain databases (memory, tasks, "
        "projects, content, research, career, entities). Use this to recall "
        "anything stored in your Notion brain — past decisions, open tasks, "
        "research notes, social content ideas, people, and preferences. "
        "Pass a specific query string for targeted recall."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for (e.g. 'database migration plan', 'Sarah preferences').",
            },
            "database": {
                "type": "string",
                "description": (
                    "Optional database filter: memory|tasks|projects|content|"
                    "research|career|entities. Omit to search all."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Max results to return (default 8, max 20).",
            },
        },
        "required": ["query"],
    },
}

REMEMBER_SCHEMA: dict[str, Any] = {
    "name": "notion_brain_remember",
    "description": (
        "Explicitly save something to the Notion brain. Use this when the user "
        "asks you to remember a fact, decision, or note that capture heuristics "
        "won't pick up automatically. Domain is inferred from content but can "
        "be overridden. "
        "Domains: daily_work, projects, social_content, research, career, entities."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title for this memory entry (max 120 chars).",
            },
            "content": {
                "type": "string",
                "description": "Full content / description of what to remember.",
            },
            "domain": {
                "type": "string",
                "description": "Which domain: daily_work|projects|social_content|research|career|entities.",
            },
            "kind": {
                "type": "string",
                "description": "Entry kind: note|task|decision|preference|source_note|draft|lesson|reminder.",
            },
            "status": {
                "type": "string",
                "description": "Status: active|done|draft|published|archived|needs_review.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for filtering (e.g. ['urgent', 'backend']).",
            },
            "entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relevant people/companies/projects mentioned.",
            },
        },
        "required": ["title", "content"],
    },
}

TASK_SCHEMA: dict[str, Any] = {
    "name": "notion_brain_task",
    "description": (
        "Manage tasks in the Notion brain Tasks database. "
        "Use this to create, update, query, or archive tasks. "
        "When creating, pass title + optional priority, due date, status, tags, and project."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "create|list|update|complete. (default: create)",
                "enum": ["create", "list", "update", "complete"],
            },
            "title": {
                "type": "string",
                "description": "Task title (required for create/update).",
            },
            "status": {
                "type": "string",
                "description": "active|done|needs_review",
            },
            "priority": {
                "type": "string",
                "description": "urgent|high|medium|low",
            },
            "due": {
                "type": "string",
                "description": "Due date ISO (YYYY-MM-DD).",
            },
            "project": {
                "type": "string",
                "description": "Associated project name.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags.",
            },
            "page_id": {
                "type": "string",
                "description": "Notion page ID for update actions.",
            },
        },
        "required": ["action"],
    },
}

CONTENT_SCHEMA: dict[str, Any] = {
    "name": "notion_brain_content",
    "description": (
        "Manage social content ideas in the Notion brain Content database. "
        "Use this to save drafts, schedule ideas, or query content by platform and status. "
        "Platforms: twitter, linkedin, instagram, tiktok, facebook, youtube, bluesky."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "create|list|update|publish|archive",
                "enum": ["create", "list", "update", "publish", "archive"],
            },
            "title": {
                "type": "string",
                "description": "Content title / headline.",
            },
            "body": {
                "type": "string",
                "description": "The content body (draft text, hook, caption).",
            },
            "status": {
                "type": "string",
                "description": "draft|published|scheduled|idea",
            },
            "platform": {
                "type": "string",
                "description": "target platform.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags.",
            },
            "page_id": {
                "type": "string",
                "description": "Notion page ID for update/publish/archive.",
            },
        },
        "required": ["action"],
    },
}

RESEARCH_SCHEMA: dict[str, Any] = {
    "name": "notion_brain_research",
    "description": (
        "Save or query research findings in the Notion brain Research database. "
        "Use this when you find a useful source, citation, or analysis worth keeping "
        "for future reference."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "save|list (default: save)",
                "enum": ["save", "list"],
            },
            "title": {
                "type": "string",
                "description": "Research entry title.",
            },
            "content": {
                "type": "string",
                "description": "Findings, summary, or citation text.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags (e.g. ['ml', 'papers', 'benchmark']).",
            },
            "status": {
                "type": "string",
                "description": "active|archived",
            },
        },
        "required": ["action"],
    },
}

ALL_TOOL_SCHEMAS = [
    SEARCH_SCHEMA,
    REMEMBER_SCHEMA,
    TASK_SCHEMA,
    CONTENT_SCHEMA,
    RESEARCH_SCHEMA,
]
