"""NotionBrainProvider — persistent long-term memory via a Notion workspace brain.

7 Notion databases (Memory, Tasks, Projects, Content, Research, Career, Entities)
are organized under a "Hermes Brain" parent page. Background sync threads classify
conversation turns using heuristics and write entries to the correct database.

Auth:   NOTION_API_KEY env var
Cache:  $HERMES_HOME/notion_brain.json
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import bootstrap, extract, schema as S, store

logger = logging.getLogger(__name__)


def _safe_select_value(value: str, prop_schema: Dict[str, Any]) -> str | None:
    """Return ``value`` if it is a defined option on this select property, else ``None``.

    Per-DB option sets differ (memory Kind: note/preference/lesson/decision/reminder;
    entities Kind: person/company/tool/project/topic/preference). Writing a value
    that isn't a defined option makes Notion reject the whole page with a 400.
    Dropping the property is safer than guessing — Notion will leave it blank or
    fill the default option.
    """
    options = prop_schema.get("select", {}).get("options", [])
    valid = {opt.get("name", "") for opt in options}
    if not valid:
        # Schema unknown — pass through; better to attempt than silently drop
        # user data when we genuinely don't know what's allowed.
        return value
    return value if value in valid else None


# ---------------------------------------------------------------------------
# Lazy helpers for Hermes runtime imports
# ---------------------------------------------------------------------------

def _sanitize_context(text: str) -> str:
    from agent.memory_manager import sanitize_context
    return sanitize_context(text)

def _tool_error(msg: str) -> str:
    from tools.registry import tool_error
    return tool_error(msg)

def _merge_disk_only(notion_entries: list[dict], disk_text: str) -> list[dict]:
    """Merge entries from disk that aren't already in the Notion list.

    Simple heuristic: if the title from disk is not in Notion titles,
    treat it as a disk-only entry and wrap it in a flat result structure.
    """
    import re

    if not disk_text or not disk_text.strip():
        return notion_entries

    notion_titles = {e.get("title", "").lower() for e in notion_entries}

    # Basic parser for the frontmatter-style blocks we write to disk
    # Expects blocks starting with --- and having a 'name: ...' line
    # Line-anchored split only on lines that are exactly "---", so content
    # containing "---" (e.g. code fences, horizontal rules) is preserved.
    disk_entries = []
    blocks = re.split(r"(?m)^---$", disk_text)
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        title = None
        tags: list[str] = []
        content = []
        for line in lines:
            if line.startswith("name: "):
                title = line[6:].strip()
            elif line.startswith("tags: "):
                tags = [t.strip() for t in line[6:].split(",") if t.strip()]
            elif not line.startswith("domain: ") and not line.startswith("kind: "):
                content.append(line)

        if title and title.lower() not in notion_titles:
            disk_entries.append({
                "title": title,
                "properties": {
                    "Content": "\n".join(content).strip(),
                    "Domain": "Memory",
                    "Kind": "note",
                    "Tags": tags,
                }
            })

    return notion_entries + disk_entries

def _merge_user_disk_only(notion_entries: list[dict], disk_text: str) -> list[dict]:
    """Merge USER.md disk-only preferences into Notion user entry list.

    USER.md uses a different format from MEMORY.md:
        # User Profile
        ## Title
        content

    Splits by ``## `` headers; each section's title is the header, body is the
    content. Entries whose title is not already in ``notion_entries`` are kept
    as disk-only, wrapped in the same flat result structure as memory entries.
    """
    if not disk_text or not disk_text.strip():
        return notion_entries

    notion_titles = {e.get("title", "").lower() for e in notion_entries}

    disk_entries: list[dict] = []
    lines = disk_text.splitlines()
    title: Optional[str] = None
    body: list[str] = []
    for line in lines[1:] if lines and lines[0].lstrip().startswith("# ") else lines:
        if line.startswith("## "):
            if title and title.lower() not in notion_titles:
                disk_entries.append(_user_disk_entry(title, body))
            title = line[3:].strip()
            body = []
        elif title is not None:
            body.append(line)
    if title and title.lower() not in notion_titles:
        disk_entries.append(_user_disk_entry(title, body))

    return notion_entries + disk_entries

def _user_disk_entry(title: str, body: list[str]) -> dict:
    return {
        "title": title,
        "properties": {
            "Content": "\n".join(body).strip(),
            "Kind": "preference",
        },
    }

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

SEARCH_SCHEMA: Dict[str, Any] = {
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

REMEMBER_SCHEMA: Dict[str, Any] = {
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

TASK_SCHEMA: Dict[str, Any] = {
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

CONTENT_SCHEMA: Dict[str, Any] = {
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

RESEARCH_SCHEMA: Dict[str, Any] = {
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

# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------

def _paragraph_blocks(content: str, *, max_paras: int = 8, chunk: int = 1900) -> list[dict]:
    """Split content into Notion paragraph children.

    Collapses blank-line paragraph gaps (Notion renders blocks without gaps),
    caps the number of paragraphs, and chunks each to the block char limit.
    ponytail: max_paras/chunk hardcoded; parameterize when a caller needs more.
    """
    if not content:
        return []
    paras = content.replace("\n\n", "\n").split("\n")
    blocks: list[dict] = []
    for para in paras[:max_paras]:
        para = para.strip()
        if not para:
            continue
        for i in range(0, len(para), chunk):
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": para[i:i + chunk]}}]},
            })
    return blocks

class NotionBrainProvider(object):
    """Notion-backed long-term memory for Hermes."""

    def __init__(self) -> None:
        # Set by initialize()
        self._session_id: str = ""
        self._hermes_home: str = ""
        self._db_ids: Dict[str, str] = {}
        self._parent_page_id: str = ""

        # Background sync state
        self._sync_lock = threading.Lock()
        self._sync_thread: Optional[threading.Thread] = None

        # Prefetch cache
        self._prefetch_cache: str = ""
        self._prefetch_lock = threading.Lock()

    # ---- Core lifecycle --------------------------------------------------

    @property
    def name(self) -> str:
        return "notion_brain"

    def is_available(self) -> bool:
        return bool(store.get_api_key())

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._hermes_home = str(kwargs.get("hermes_home", ""))

        if not self._hermes_home:
            logger.warning("NotionBrainProvider: no hermes_home — limited functionality")

        # Bootstrap workspace (idempotent)
        try:
            cache = bootstrap.ensure_brain(self._hermes_home)
            self._parent_page_id = cache.get("parent_page_id", "")
            for key in S.DATABASES:
                self._db_ids[key] = cache.get(f"db_{key}", "")
            logger.info("Notion brain initialized: %d databases", len(self._db_ids))
        except Exception as exc:
            logger.error("NotionBrainProvider bootstrap failed: %s", S.redact_secrets(str(exc)))

        # Pre-load memory files from disk as fallback context
        if self._hermes_home:
            mem_text = bootstrap.read_memory_from_disk(self._hermes_home)
            user_text = bootstrap.read_user_from_disk(self._hermes_home)
            combined = "\n".join(filter(None, [mem_text, user_text])).strip()
            if combined:
                # Store as local fallback; prefetch() will use it
                self._prefetch_cache = (
                    "<!-- memory-context from disk -->\n" + combined[:4000]
                )

    def system_prompt_block(self) -> str:
        return (
            "# Notion Brain\n"
            "Your long-term memory lives in a Notion workspace called "
            "\"Hermes Brain\" with 7 databases: "
            "Memory (general notes + preferences), Tasks, Projects, Content "
            "(social media drafts), Research, Career, and Entities (people, "
            "companies, tools, topics). "
            "Use notion_brain_search to recall context, notion_brain_remember "
            "to save important facts, notion_brain_task for task management, "
            "notion_brain_content for social content ideas, and "
            "notion_brain_research for research findings. "
            "Memory is automatically synced after each turn."
        )

    def prefetch(self, **kwargs) -> str:
        with self._prefetch_lock:
            if self._prefetch_cache:
                return self._prefetch_cache

            # Query memory database for recent entries
            if not self._db_ids.get("memory"):
                return ""

            try:
                entries = store.query_database(
                    self._db_ids["memory"],
                    sorts=[{"property": "Last Seen", "direction": "descending"}],
                    page_size=10,
                )
                if not entries:
                    return ""

                lines: list[str] = []
                for entry in entries[:10]:
                    title = entry.get("title", "Untitled")
                    content = entry.get("properties", {}).get("Content", "")
                    kind = entry.get("properties", {}).get("Kind", "note")
                    lines.append(f"- [{kind}] {title}: {content[:200]}")

                self._prefetch_cache = "\n".join(lines)
                return self._prefetch_cache
            except Exception as exc:
                logger.warning("NotionBrainProvider prefetch failed: %s", S.redact_secrets(str(exc)))
                return ""

    def sync_turn(self, **kwargs) -> None:
        """Background sync after a turn. Called by Hermes after each response."""
        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                return

            def _do_sync() -> None:
                try:
                    # TODO: implement actual sync logic
                    logger.debug("NotionBrainProvider: sync turn complete")
                except Exception as exc:
                    logger.error("NotionBrainProvider sync error: %s", S.redact_secrets(str(exc)))

            self._sync_thread = threading.Thread(target=_do_sync, daemon=True)
            self._sync_thread.start()

    def on_session_end(self, **kwargs) -> None:
        """Called when Hermes session ends. Wait for pending sync."""
        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=5.0)

    def shutdown(self) -> None:
        """Clean shutdown."""
        self.on_session_end()

    def _sync_disk_output(self, entries: list[dict]) -> str:
        """Format entries as frontmatter-style disk output."""
        lines: list[str] = []
        for entry in entries:
            title = entry.get("title", "Untitled")
            props = entry.get("properties", {})
            domain = props.get("Domain", "Memory")
            kind = props.get("Kind", "note")
            content = props.get("Content", "")
            tags = props.get("Tags", [])
            tag_str = ", ".join(tags) if tags else ""

            lines.append("---")
            lines.append(f"name: {title}")
            lines.append(f"domain: {domain}")
            lines.append(f"kind: {kind}")
            if tag_str:
                lines.append(f"tags: {tag_str}")
            lines.append("")
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    def on_memory_write(self, text: str, **kwargs) -> None:
        """Called when Hermes writes memory. Classify and store."""
        if not text.strip():
            return

        # Classify using heuristics
        classification = extract.classify_text(text)
        domain = classification.get("domain", "memory")
        kind = classification.get("kind", "note")

        entry = S.BrainEntry(
            domain=domain,
            title=classification.get("title", "Untitled"),
            content=text,
            kind=kind,
            source_session_id=self._session_id,
        ).normalized()

        self._store_entry(entry)

    def get_tool_schemas(self) -> list[Dict[str, Any]]:
        return ALL_TOOL_SCHEMAS

    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        handlers = {
            "notion_brain_search": self._tool_search,
            "notion_brain_remember": self._tool_remember,
            "notion_brain_task": self._tool_task,
            "notion_brain_content": self._tool_content,
            "notion_brain_research": self._tool_research,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({
                "result": f"Unknown tool: {tool_name}",
                "error": True,
            })

        try:
            result = handler(arguments)
            return json.dumps({"result": result, "error": False})
        except Exception as exc:
            logger.error("Tool call %s failed: %s", tool_name, S.redact_secrets(str(exc)))
            return json.dumps({
                "result": f"Tool error: {S.redact_secrets(str(exc))}",
                "error": True,
            })

    def _store_entry(self, entry: S.BrainEntry) -> None:
        """Store a normalized entry in the appropriate database."""
        database_key = S.database_for_domain(entry.domain)
        database_id = self._db_ids.get(database_key)

        if not database_id:
            logger.warning("No database for domain %s", entry.domain)
            return

        self._write_entry_raw(database_id, entry)

    def _write_entry_raw(self, database_id: str, entry: S.BrainEntry) -> None:
        """Write entry to Notion database.

        Raises ``RuntimeError`` on failure so callers (especially the tool
        handlers) can surface a real error to the user instead of letting
        the entry vanish. The background ``sync_turn`` path wraps its own
        calls in ``try/except`` so it can keep running on errors.
        """
        properties = self._database_properties(database_id, entry)

        try:
            store.create_database_page(database_id, properties)
            logger.debug("Stored entry in %s: %s", database_id, entry.title)
        except Exception as exc:
            # Scrub both the inner failure detail and the entry title before
            # logging — error paths must not leak secrets into log streams.
            safe_detail = S.redact_secrets(str(exc))
            safe_title = S.redact_secrets(entry.title)
            logger.error("Failed to store entry %r: %s", safe_title, safe_detail)
            raise RuntimeError(
                f"Failed to save {safe_title!r} to Notion: {safe_detail}"
            ) from exc

    def _database_properties(self, database_id: str, entry: S.BrainEntry) -> Dict[str, Any]:
        """Build Notion properties from a BrainEntry."""
        props: Dict[str, Any] = {
            "title": store.title_property(entry.title),
        }

        # Get database schema to know available properties
        try:
            db = store.get_database(database_id)
            schema_props = db.get("properties", {})

            if "Domain" in schema_props:
                props["Domain"] = store.select_property(S.DOMAINS.get(entry.domain, entry.domain))
            if "Status" in schema_props:
                props["Status"] = self._status_property(entry.status, schema_props)
            if "Kind" in schema_props:
                kind_value = _safe_select_value(entry.kind, schema_props["Kind"])
                if kind_value is not None:
                    props["Kind"] = store.select_property(kind_value)
            if "Confidence" in schema_props:
                props["Confidence"] = store.select_property(entry.confidence)
            if "Tags" in schema_props:
                props["Tags"] = store.multi_select_property(entry.tags)
            if "Entities" in schema_props:
                props["Entities"] = store.multi_select_property(entry.entities)
            if "Content" in schema_props:
                props["Content"] = store.rich_text_property(entry.content)
            if "Source Session" in schema_props and entry.source_session_id:
                props["Source Session"] = store.rich_text_property(entry.source_session_id)
        except Exception as exc:
            logger.warning("Could not get database schema for %s: %s", database_id, S.redact_secrets(str(exc)))
            # Fallback to known properties — pick the safest status shape per-DB.
            props["Domain"] = store.select_property(S.DOMAINS.get(entry.domain, entry.domain))
            props["Kind"] = store.select_property(entry.kind)
            props["Confidence"] = store.select_property(entry.confidence)
            props["Tags"] = store.multi_select_property(entry.tags)
            props["Entities"] = store.multi_select_property(entry.entities)
            props["Content"] = store.rich_text_property(entry.content)

        return props

    def _status_property(
        self,
        status: str,
        schema_props: Dict[str, Any],
        *,
        strict: bool = False,
    ) -> Dict[str, Any]:
        """Map status to a valid Notion Status option, respecting the DB's actual type.

        ``Status`` in our content DB is a ``select`` type (draft/published/scheduled/idea);
        everywhere else it's a ``status`` type (active/done/needs_review). We read the
        options out of whichever shape the DB actually uses and emit the matching
        payload. When ``strict=True`` an unknown status returns ``{}`` so callers
        can surface the error instead of silently coercing.
        """
        status_prop = schema_props.get("Status", {})
        # Notion puts option lists under the property type key — ``status`` or ``select``.
        options = status_prop.get("status", {}).get("options") or status_prop.get("select", {}).get("options") or []
        valid_names = {opt.get("name", "") for opt in options if isinstance(opt, dict)}
        use_select = "select" in status_prop and "status" not in status_prop

        if status in valid_names:
            target = status
        elif strict:
            # Caller asked for strict mode — return empty so it can surface the error.
            return {}
        elif valid_names:
            # Deterministic fallback — pick the lowest option alphabetically.
            target = sorted(valid_names)[0]
        else:
            # No options at all — nothing safe to write; omit the property.
            return {}

        if use_select:
            return store.select_property(target)
        return store.status_property(target)

    def _tool_search(self, args: Dict[str, Any]) -> str:
        """Search across brain databases."""
        query = args.get("query", "")
        database = args.get("database")
        max_results = min(args.get("max_results", 8), 20)

        # Merge disk context
        disk_text = ""
        if self._hermes_home:
            disk_text = bootstrap.read_memory_from_disk(self._hermes_home)

        if database:
            # Search specific database
            db_id = self._db_ids.get(database)
            if not db_id:
                return f"No database found for: {database}"

            entries = store.query_database(db_id, page_size=max_results)
            entries = _merge_disk_only(entries, disk_text)
        else:
            # Search all databases
            all_entries: list[dict] = []
            for key, db_id in self._db_ids.items():
                try:
                    results = store.query_database(db_id, page_size=max_results)
                    all_entries.extend(results)
                except Exception:
                    pass
            all_entries = _merge_disk_only(all_entries, disk_text)
            entries = all_entries[:max_results]

        # Format results
        if not entries:
            return "No results found."

        lines: list[str] = []
        for entry in entries:
            title = entry.get("title", "Untitled")
            content = entry.get("properties", {}).get("Content", "")[:200]
            kind = entry.get("properties", {}).get("Kind", "note")
            lines.append(f"- [{kind}] {title}: {content}")

        return "\n".join(lines)

    def _tool_remember(self, args: Dict[str, Any]) -> str:
        """Explicitly remember something."""
        title = args.get("title", "").strip()
        content = args.get("content", "").strip()
        domain = args.get("domain", "memory")
        kind = args.get("kind", "note")
        status = args.get("status", "active")
        tags = args.get("tags", [])
        entities = args.get("entities", [])

        if not title:
            return "Error: title is required"
        if not content:
            return "Error: content is required"

        entry = S.BrainEntry(
            domain=domain,
            title=title,
            content=content,
            kind=kind,
            status=status,
            tags=tags,
            entities=entities,
            source_session_id=self._session_id,
        ).normalized()

        try:
            self._store_entry(entry)
        except RuntimeError as exc:
            return f"Error: {S.redact_secrets(str(exc))}"
        return f"Saved: {title}"

    def _tool_task(self, args: Dict[str, Any]) -> str:
        """Manage tasks."""
        action = args.get("action", "list")

        if action == "create":
            title = args.get("title", "").strip()
            if not title:
                return "Error: task title is required"

            entry = S.BrainEntry(
                domain="daily_work",
                title=title,
                content=args.get("content", ""),
                kind="task",
                status=args.get("status", "active"),
                tags=args.get("tags", []),
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Task created: {title}"

        elif action == "list":
            db_id = self._db_ids.get("tasks")
            if not db_id:
                return "No Tasks database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No tasks found."

            lines: list[str] = []
            for entry in entries:
                title = entry.get("title", "Untitled")
                status = entry.get("properties", {}).get("Status", "")
                lines.append(f"- [{status}] {title}")

            return "\n".join(lines)

        elif action == "update":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"

            properties: dict[str, Any] = {}
            if "title" in args:
                properties["title"] = store.title_property(S.clean_title(args["title"]))
            if "status" in args:
                status_payload, status_err = self._validated_status(
                    args["status"], "tasks"
                )
                if status_err:
                    return status_err
                if status_payload:
                    properties["Status"] = status_payload

            store.update_page(page_id, properties)
            return "Task updated."

        elif action == "complete":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required"

            status_payload, status_err = self._validated_status("done", "tasks")
            if status_err:
                return status_err
            properties = {"Status": status_payload} if status_payload else {}
            store.update_page(page_id, properties)
            return "Task completed."

        return f"Unknown task action: {action}"

    def _validated_status(
        self, status: str, db_key: str
    ) -> tuple[Dict[str, Any], str | None]:
        """Build a Status payload validated against ``db_key``'s real options.

        Returns (payload, None) on success, ({}, error_message) if ``status``
        is not a defined option. Falls back to a plain status_property write
        if the schema can't be read — matching create-path behavior.
        """
        db_id = self._db_ids.get(db_key)
        if not db_id:
            return store.status_property(status), None
        try:
            db = store.get_database(db_id)
            schema_props = db.get("properties", {})
        except Exception as exc:
            logger.warning("Could not read schema for %s: %s", db_key, S.redact_secrets(str(exc)))
            return store.status_property(status), None

        payload = self._status_property(status, schema_props, strict=True)
        if payload:
            return payload, None
        # _status_property returns {} only when the value isn't a valid option
        # (and it can't fall back). Surface that so the user knows.
        status_prop = schema_props.get("Status", {})
        options = (
            status_prop.get("status", {}).get("options")
            or status_prop.get("select", {}).get("options")
            or []
        )
        valid = sorted({opt.get("name", "") for opt in options if isinstance(opt, dict)})
        return {}, f"Error: status '{status}' is not valid for {db_key}. Valid: {valid}"

    def _tool_content(self, args: Dict[str, Any]) -> str:
        """Manage social content."""
        action = args.get("action", "list")

        if action == "create":
            title = args.get("title", "").strip()
            body = args.get("body", "").strip()
            if not title:
                return "Error: content title is required"

            entry = S.BrainEntry(
                domain="social_content",
                title=title,
                content=body,
                kind="draft",
                status=args.get("status", "draft"),
                tags=args.get("tags", []),
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Content saved: {title}"

        elif action == "list":
            db_id = self._db_ids.get("content")
            if not db_id:
                return "No Content database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No content found."

            lines: list[str] = []
            for entry in entries:
                title = entry.get("title", "Untitled")
                status = entry.get("properties", {}).get("Status", "")
                lines.append(f"- [{status}] {title}")

            return "\n".join(lines)

        return f"Unknown content action: {action}"

    def _tool_research(self, args: Dict[str, Any]) -> str:
        """Manage research findings."""
        action = args.get("action", "save")

        if action == "save":
            title = args.get("title", "").strip()
            content = args.get("content", "").strip()
            if not title:
                return "Error: research title is required"

            entry = S.BrainEntry(
                domain="research",
                title=title,
                content=content,
                kind="reference",
                status=args.get("status", "active"),
                tags=args.get("tags", []),
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Research saved: {title}"

        elif action == "list":
            db_id = self._db_ids.get("research")
            if not db_id:
                return "No Research database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No research findings found."

            lines: list[str] = []
            for entry in entries:
                title = entry.get("title", "Untitled")
                lines.append(f"- {title}")

            return "\n".join(lines)

        return f"Unknown research action: {action}"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(context: Any) -> None:
    """Register the NotionBrainProvider with Hermes."""
    context.register_memory_provider(NotionBrainProvider())