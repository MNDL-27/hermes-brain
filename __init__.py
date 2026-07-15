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
from typing import Any, Dict, List, Optional
from agent.memory_manager import sanitize_context
from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

from . import bootstrap, extract, schema as S, store

logger = logging.getLogger(__name__)

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


class NotionBrainProvider(MemoryProvider):
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
            logger.error("NotionBrainProvider bootstrap failed: %s", exc)

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

    # ---- Prefetch & sync -------------------------------------------------

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Smart recall: search across relevant databases for context injection."""
        # Skip trivial queries
        if not query or not query.strip():
            return self._prefetch_cache or ""

        q = query.strip()
        if len(q) < 3 and q.lower() in {"ok", "yes", "no", "hi"}:
            return self._prefetch_cache or ""

        if not self._db_ids:
            return self._prefetch_cache or ""

        try:
            results = store.search_entries(q, page_size=8)
            if not results:
                return self._prefetch_cache or ""

            parts = ["<memory-context>"]
            for r in results[:6]:
                title = r.get("title", "")
                props = r.get("properties", {})
                snippet = props.get("Content", props.get("Title", "")) or title
                kind = props.get("Kind", props.get("Status", ""))
                domain = props.get("Domain", "")
                if snippet:
                    parts.append(f"- [{domain}/{kind}] {snippet[:200]}")
            parts.append("</memory-context>")
            context = "\n".join(parts)
            # Cache for subsequent calls
            with self._prefetch_lock:
                self._prefetch_cache = context
            return context
        except Exception as exc:
            logger.debug("Notion prefetch failed: %s", exc)
            return self._prefetch_cache or ""

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "", messages=None) -> None:
        """Non-blocking: classify the turn and store entries in a background thread."""
        if not self._db_ids:
            return

        # Sanitize content
        clean_user = sanitize_context(user_content or "").strip()
        clean_asst = sanitize_context(assistant_content or "").strip()

        if not clean_user and not clean_asst:
            return

        # Launch background thread — do not block the turn
        def _do_sync():
            try:
                entries = extract.classify_turn(clean_user, clean_asst)
                for entry in entries:
                    self._store_entry(entry)
            except Exception as exc:
                logger.debug("Notion sync_turn failed: %s", exc)

        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                # Let the prior catch-up finish first
                self._sync_thread.join(timeout=3.0)
            self._sync_thread = threading.Thread(target=_do_sync, daemon=True, name="notion-sync")
            self._sync_thread.start()

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Flush pending sync and optionally save a session summary to Notion."""
        # Wait for pending sync to complete
        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=10.0)

        if not self._db_ids or not messages:
            return

        # Save a brief session summary to the Memory database
        try:
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if not user_msgs:
                return
            topics = ", ".join(
                S.keyword_tokens(user_msgs[0].get("content", ""), limit=3)
            )
            if topics:
                title = f"Session {self._session_id[:8]}: {topics}"
                content_parts = []
                for m in messages[-6:]:
                    role = m.get("role", "")
                    text = sanitize_context(m.get("content", "") or "")[:300]
                    content_parts.append(f"[{role}] {text}")
                self._write_entry_raw(
                    domain="memory",
                    title=title,
                    content="\n\n".join(content_parts),
                    kind="note",
                    status="active",
                    confidence="medium",
                    tags=["session_summary"],
                )
        except Exception as exc:
            logger.debug("Notion on_session_end failed: %s", exc)

    def shutdown(self) -> None:
        """Flush sync thread and write cache."""
        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=8.0)

        # Write cache via bootstrap
        if self._hermes_home and self._parent_page_id:
            try:
                path = __import__("pathlib").Path(self._hermes_home) / S.CACHE_FILE
                data = {"parent_page_id": self._parent_page_id}
                for key, val in self._db_ids.items():
                    data[f"db_{key}"] = val
                path.write_text(json.dumps(data, indent=2))
            except Exception as exc:
                logger.debug("NotionBrainProvider cache save failed: %s", exc)

    # ---- Memory mirror ---------------------------------------------------

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in memory writes to the Notion Entities or Memory DB."""
        if action != "add" or target not in ("memory", "user") or not content:
            return

        try:
            domain = "entities" if target == "user" else "memory"
            kind = "preference" if target == "user" else "note"
            self._write_entry_raw(
                domain=domain,
                title=S.compact(content[:100]),
                content=S.compact(content, 900),
                kind=kind,
                status="active",
                confidence="high",
                tags=["mirror", target],
            )
        except Exception as exc:
            logger.debug("NotionBrainProvider on_memory_write failed: %s", exc)

    # ---- Tool schemas & dispatch ----------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return list(ALL_TOOL_SCHEMAS)

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        try:
            if tool_name == "notion_brain_search":
                return self._tool_search(args)
            if tool_name == "notion_brain_remember":
                return self._tool_remember(args)
            if tool_name == "notion_brain_task":
                return self._tool_task(args)
            if tool_name == "notion_brain_content":
                return self._tool_content(args)
            if tool_name == "notion_brain_research":
                return self._tool_research(args)
            return tool_error(f"Unknown tool: {tool_name}")
        except Exception as exc:
            logger.error("NotionBrainProvider tool %s failed: %s", tool_name, exc)
            return tool_error(f"{tool_name} failed: {exc}")

    # ---- Internal helpers ------------------------------------------------

    def _store_entry(self, entry: S.BrainEntry) -> None:
        """Normalize and write a BrainEntry to the correct database."""
        norm = entry.normalized()
        domain_db = S.database_for_domain(norm.domain)
        db_id = self._db_ids.get(domain_db)
        if not db_id:
            logger.warning("No database ID for domain '%s' -> '%s'", norm.domain, domain_db)
            return
        self._write_entry_raw(
            domain=norm.domain,
            title=norm.title,
            content=norm.content,
            kind=norm.kind,
            status=norm.status,
            confidence=norm.confidence,
            tags=norm.tags,
            entities=norm.entities,
            db_id=db_id,
        )

    def _write_entry_raw(
        self,
        domain: str,
        title: str,
        content: str,
        kind: str = "note",
        status: str = "active",
        confidence: str = "medium",
        tags: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        db_id: str = "",
    ) -> None:
        """Write a page to the appropriate database."""
        if not db_id:
            domain_db = S.database_for_domain(domain)
            db_id = self._db_ids.get(domain_db, "")

        if not db_id:
            logger.warning("No database ID for domain '%s'", domain)
            return

        domain_label = S.DOMAINS.get(domain, "Memory")
        db_props = self._database_properties(db_id)

        props: Dict[str, Any] = {
            "title": store.title_property(title),
            "Domain": store.select_property(domain_label),
            "Status": self._status_property(db_props, status),
            "Tags": store.multi_select_property(tags or []),
            "Confidence": store.select_property(confidence),
        }

        if kind and kind != "note" and "Kind" in db_props:
            props["Kind"] = store.select_property(kind)

        if entities and "Entities" in db_props:
            props["Entities"] = store.rich_text_property(", ".join(entities[:5]))

        props = {name: prop for name, prop in props.items() if name in db_props or name == "title"}

        children = []
        if content:
            # Split into paragraph-safe children (Notion block limit: 2000 chars / block)
            paras = content.replace("\n\n", "\n").split("\n")
            for para in paras[:8]:
                para = para.strip()
                if not para:
                    continue
                for i in range(0, len(para), 1900):
                    chunk = para[i:i + 1900]
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
                    })

        try:
            store.create_database_page(database_id=db_id, properties=props, children=children or None)
        except Exception as exc:
            logger.warning("_write_entry_raw failed for domain '%s' title '%s': %s",
                           domain, title[:60], exc)
            raise

    def _database_properties(self, db_id: str) -> Dict[str, Any]:
        try:
            return store.get_database(db_id).get("properties", {}) or {}
        except Exception as exc:
            logger.debug("Could not fetch database schema for %s: %s", db_id, exc)
            return {}

    def _status_property(self, db_props: Dict[str, Any], status: str) -> Dict[str, Any]:
        prop = db_props.get("Status") or {}
        if prop.get("type") == "select":
            return store.select_property(status)
        if prop.get("type") != "status":
            return store.rich_text_property(status)

        names = {
            opt.get("name")
            for opt in (prop.get("status") or {}).get("options", [])
            if opt.get("name")
        }
        if status in names:
            return store.status_property(status)
        fallback = {
            "active": "Not started",
            "needs_review": "In progress",
            "done": "Done",
            "archived": "Done",
        }.get(status, status)
        return store.status_property(fallback if fallback in names else next(iter(names), status))

    # ---- Tool handlers ---------------------------------------------------

    def _tool_search(self, args: Dict[str, Any]) -> str:
        query = args.get("query", "")
        if not query:
            return tool_error("Missing required parameter: query")

        db_filter = args.get("database", "all")
        max_results = min(int(args.get("max_results", 8)), 20)

        try:
            if db_filter != "all" and db_filter in self._db_ids:
                db_id = self._db_ids[db_filter]
                raw = store.query_database(db_id, page_size=max_results)
            else:
                raw = store.search_entries(query, page_size=max_results)

            if not raw:
                return json.dumps({"result": f"No results for '{query}'.", "items": []})

            items = []
            for r in raw:
                props = r.get("properties", {})
                items.append({
                    "id": r.get("id", ""),
                    "title": r.get("title", ""),
                    "domain": props.get("Domain", ""),
                    "kind": props.get("Kind", props.get("Status", "")),
                    "tags": props.get("Tags", []),
                    "snippet": (props.get("Content", "") or r.get("title", ""))[:200],
                })

            return json.dumps({"result": f"Found {len(items)} result(s).", "items": items})
        except Exception as exc:
            return tool_error(f"Search failed: {exc}")

    def _tool_remember(self, args: Dict[str, Any]) -> str:
        title = args.get("title", "")
        content = args.get("content", "")
        if not title or not content:
            return tool_error("Missing required parameters: title and content")

        domain = args.get("domain", "memory")
        kind = args.get("kind", "note")
        status = args.get("status", "active")
        tags = args.get("tags", [])
        entities = args.get("entities", [])

        try:
            entry = S.BrainEntry(
                domain=domain, title=title, content=content,
                kind=kind, status=status, tags=tags, entities=entities,
            ).normalized()
            self._store_entry(entry)
            db_key = S.database_for_domain(entry.domain)
            return json.dumps({
                "result": f"Saved '{entry.title}' to {db_key}.",
                "domain": db_key, "id": title[:60],
            })
        except Exception as exc:
            return tool_error(f"Remember failed: {exc}")

    def _tool_task(self, args: Dict[str, Any]) -> str:
        action = args.get("action", "create")
        db_id = self._db_ids.get("tasks", "")

        if not db_id:
            return tool_error("Tasks database not available.")

        try:
            if action == "list":
                status_filter = None
                for s in ("active", "done", "needs_review"):
                    if args.get("status") == s:
                        status_filter = {"property": "Status", "status": {"equals": s}}
                        break
                raw = store.query_database(
                    db_id, page_size=10,
                    filter_obj=status_filter,
                    sorts=[{"timestamp": "created_time", "direction": "descending"}],
                )
                if not raw:
                    return json.dumps({"result": "No tasks found.", "items": []})
                items = [
                    {
                        "id": r.get("id", ""),
                        "title": r.get("title", ""),
                        "status": r.get("properties", {}).get("Status", ""),
                        "priority": r.get("properties", {}).get("Priority", ""),
                        "due": r.get("properties", {}).get("Due", ""),
                        "project": r.get("properties", {}).get("Project", ""),
                    }
                    for r in raw[:10]
                ]
                return json.dumps({"result": f"{len(items)} task(s).", "items": items})

            if action == "create":
                title = args.get("title", "")
                if not title:
                    return tool_error("title required for task creation")
                page_id = args.get("page_id", "")
                if page_id:
                    return self._tool_task_update(db_id, page_id, args)

                props = {
                    "title": store.title_property(title),
                    "Status": self._status_property(self._database_properties(db_id), args.get("status", "active")),
                    "Tags": store.multi_select_property(args.get("tags", [])),
                }
                priority = args.get("priority", "")
                if priority:
                    props["Priority"] = store.select_property(priority)
                due = args.get("due", "")
                if due:
                    props["Due"] = store.date_property(due)
                project = args.get("project", "")
                if project:
                    props["Project"] = store.rich_text_property(project)

                page = store.create_database_page(database_id=db_id, properties=props)
                return json.dumps({"result": f"Task created.", "page_id": page.get("id", "")})

            if action in ("update", "complete"):
                page_id = args.get("page_id", "")
                if not page_id:
                    return tool_error("page_id required for update")
                if action == "complete":
                    args = dict(args)
                    args["status"] = "done"
                return self._tool_task_update(db_id, page_id, args)

            return tool_error(f"Unknown action: {action}")
        except Exception as exc:
            return tool_error(f"Task operation failed: {exc}")

    def _tool_task_update(self, db_id: str, page_id: str, args: Dict[str, Any]) -> str:
        props: Dict[str, Any] = {}
        if args.get("status"):
            props["Status"] = self._status_property(self._database_properties(db_id), args["status"])
        if args.get("priority"):
            props["Priority"] = store.select_property(args["priority"])
        if args.get("due"):
            props["Due"] = store.date_property(args["due"])
        if args.get("project"):
            props["Project"] = store.rich_text_property(args["project"])
        if not props:
            return tool_error("No properties to update.")
        page = store.update_page(page_id, props)
        return json.dumps({"result": "Task updated.", "page_id": page.get("id", page_id)})

    def _tool_content(self, args: Dict[str, Any]) -> str:
        action = args.get("action", "create")
        db_id = self._db_ids.get("content", "")

        if not db_id:
            return tool_error("Content database not available.")

        try:
            if action == "list":
                raw = store.query_database(
                    db_id, page_size=10,
                    sorts=[{"timestamp": "created_time", "direction": "descending"}],
                )
                if not raw:
                    return json.dumps({"result": "No content entries.", "items": []})
                items = [
                    {
                        "id": r.get("id", ""),
                        "title": r.get("title", ""),
                        "status": r.get("properties", {}).get("Status", ""),
                        "platform": r.get("properties", {}).get("Platform", ""),
                        "tags": r.get("properties", {}).get("Tags", []),
                    }
                    for r in raw[:10]
                ]
                return json.dumps({"result": f"{len(items)} content entry(ies).", "items": items})

            if action in ("publish", "archive"):
                page_id = args.get("page_id", "")
                if not page_id:
                    return tool_error("page_id required")
                new_status = "published" if action == "publish" else "archived"
                page = store.update_page(page_id, {"Status": self._status_property(self._database_properties(db_id), new_status)})
                return json.dumps({"result": f"Content {action}d.", "page_id": page.get("id", page_id)})

            # create / update
            title = args.get("title", "")
            if not title:
                return tool_error("title required for content creation")
            body = args.get("body", "")

            props = {
                "title": store.title_property(title),
                "Status": store.select_property(args.get("status", "draft")),
                "Tags": store.multi_select_property(args.get("tags", [])),
            }
            platform = args.get("platform", "")
            if platform:
                props["Platform"] = store.select_property(platform)

            children = []
            if body:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": body[:1900]}}]},
                })

            page = store.create_database_page(
                database_id=db_id, properties=props, children=children or None
            )
            return json.dumps({"result": f"Content '{title}' saved.", "page_id": page.get("id", "")})
        except Exception as exc:
            return tool_error(f"Content operation failed: {exc}")

    def _tool_research(self, args: Dict[str, Any]) -> str:
        action = args.get("action", "save")
        db_id = self._db_ids.get("research", "")

        if not db_id:
            return tool_error("Research database not available.")

        try:
            if action == "list":
                raw = store.query_database(
                    db_id, page_size=10,
                    sorts=[{"timestamp": "created_time", "direction": "descending"}],
                )
                if not raw:
                    return json.dumps({"result": "No research entries.", "items": []})
                items = [
                    {
                        "id": r.get("id", ""),
                        "title": r.get("title", ""),
                        "status": r.get("properties", {}).get("Status", ""),
                        "tags": r.get("properties", {}).get("Tags", []),
                    }
                    for r in raw[:10]
                ]
                return json.dumps({"result": f"{len(items)} research entry(ies).", "items": items})

            if action == "save":
                title = args.get("title", "")
                if not title:
                    return tool_error("title required for research save")
                content = args.get("content", "")
                props = {
                    "title": store.title_property(title),
                    "Status": self._status_property(self._database_properties(db_id), args.get("status", "active")),
                    "Tags": store.multi_select_property(args.get("tags", [])),
                }
                children = []
                if content:
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[:1900]}}]},
                    })
                page = store.create_database_page(
                    database_id=db_id, properties=props, children=children or None
                )
                return json.dumps({"result": f"Research saved.", "page_id": page.get("id", "")})

            return tool_error(f"Unknown action: {action}")
        except Exception as exc:
            return tool_error(f"Research operation failed: {exc}")


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Register NotionBrainProvider as a memory provider plugin."""
    ctx.register_memory_provider(NotionBrainProvider())
