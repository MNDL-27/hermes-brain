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
import queue
import threading
from typing import Any

from . import bootstrap, extract, store
from . import schema as S
from .helpers import _merge_disk_only, _safe_select_value
from .schemas import ALL_TOOL_SCHEMAS

logger = logging.getLogger(__name__)


def _message_content_text(content: Any) -> str:
    """Extract plain text from a message ``content`` field.

    Hermes/OpenAI tool-call messages encode ``content`` as a list of block
    dicts (``{"type": "text", "text": {"content": ...}}``); plain chat
    messages use a plain string. Returns ``""`` for ``None``/missing content
    so callers can safely pass the result to ``redact_secrets``.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, dict):
                    texts.append(t.get("content", ""))
            elif isinstance(block.get("content"), str):
                texts.append(block["content"])
        return "\n".join(texts)
    return str(content) if content else ""


class NotionBrainProvider:
    """Notion-backed long-term memory for Hermes."""

    def __init__(self) -> None:
        # Set by initialize()
        self._session_id: str = ""
        self._hermes_home: str = ""
        self._db_ids: dict[str, str] = {}
        self._parent_page_id: str = ""

        # Background sync state
        self._sync_lock = threading.Lock()
        self._sync_thread: threading.Thread | None = None
        self._sync_queue: queue.Queue = queue.Queue()

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
                    safe_title = S.redact_secrets(title)
                    safe_content = S.redact_secrets(content[:200])
                    lines.append(f"- [{kind}] {safe_title}: {safe_content}")

                safe_lines = S.redact_secrets("\n".join(lines))
                self._prefetch_cache = safe_lines
                return self._prefetch_cache
            except Exception as exc:
                logger.warning("NotionBrainProvider prefetch failed: %s", S.redact_secrets(str(exc)))
                return ""

    def _worker_loop(self) -> None:
        while True:
            with self._sync_lock:
                try:
                    task = self._sync_queue.get_nowait()
                except queue.Empty:
                    self._sync_thread = None
                    break
            func, args, kwargs = task
            try:
                func(*args, **kwargs)
            except Exception as exc:
                logger.error("NotionBrainProvider sync worker error: %s", S.redact_secrets(str(exc)))
            finally:
                self._sync_queue.task_done()

    def _process_sync_turn(self, user_content: str, assistant_content: str) -> None:
        try:
            entries = extract.classify_turn(user_content, assistant_content)
            for entry in entries:
                if isinstance(entry, S.BrainEntry):
                    entry.source_session_id = self._session_id
                    self._store_entry(entry.normalized())
                else:
                    self._store_entry(entry)
            self._prefetch_cache = ""
            self.prefetch()
            logger.debug("NotionBrainProvider: sync turn complete")
        except Exception as exc:
            logger.error("NotionBrainProvider sync error: %s", S.redact_secrets(str(exc)))

    def sync_turn(self, *args, **kwargs) -> None:
        """Background sync after a turn. Called by Hermes after each response."""
        user_content = args[0] if len(args) > 0 else kwargs.get("user_content", "")
        assistant_content = args[1] if len(args) > 1 else kwargs.get("assistant_content", "")
        with self._sync_lock:
            self._sync_queue.put((self._process_sync_turn, (user_content, assistant_content), {}))
            if self._sync_thread is None or not self._sync_thread.is_alive():
                self._sync_thread = threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name="notion-brain-sync-worker",
                )
                self._sync_thread.start()

    def on_session_end(self, *args, **kwargs) -> None:
        """Called when Hermes session ends. Wait for pending sync, then
        optionally write a session-summary entry from inline messages."""
        self._sync_queue.join()
        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=5.0)
                self._sync_thread = None

        messages = args[0] if args else kwargs.get("messages")
        if messages:
            try:
                self._write_session_summary(messages)
            except Exception as exc:
                logger.error(
                    "NotionBrainProvider session summary failed: %s",
                    S.redact_secrets(str(exc)),
                )

    def _write_session_summary(self, messages: list[dict[str, Any]]) -> None:
        """Write conversation messages as a redacted session-summary entry."""
        parts = [
            f"{msg.get('role', '')}: {S.redact_secrets(_message_content_text(msg.get('content')))}"
            for msg in messages
        ]
        text = "\n".join(parts)
        entry = S.BrainEntry(
            domain="memory",
            title="Session summary",
            content=text,
            kind="note",
            source_session_id=self._session_id,
        ).normalized()
        self._store_entry(entry)

    def shutdown(self) -> None:
        """Clean shutdown."""
        self.on_session_end()

    def on_memory_write(self, text: str, **kwargs) -> None:
        """Called when Hermes writes memory. Classify and store."""
        if not text.strip():
            return

        # Classify using heuristics
        classification = extract.classify_text(text)
        domain = classification.get("domain", "memory")
        kind = classification.get("kind", "note")

        # Scrub raw text BEFORE classification and storage so secrets never
        # travel through classification helpers, caches, or the outbox path.
        safe_text = S.redact_secrets(text)
        safe_title = S.clean_title(classification.get("title", "Untitled"))

        entry = S.BrainEntry(
            domain=domain,
            title=safe_title,
            content=safe_text,
            kind=kind,
            source_session_id=self._session_id,
        ).normalized()

        self._store_entry(entry)

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return ALL_TOOL_SCHEMAS

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
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
                "result": S.redact_secrets(f"Unknown tool: {tool_name}"),
                "error": True,
            })

        try:
            result = handler(arguments)
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
                text_result, extra = result
                payload = {"result": text_result, "error": False, **extra}
                return json.dumps(payload)
            return json.dumps({"result": result, "error": False})
        except Exception as exc:
            logger.error("Tool call %s failed: %s", tool_name, S.redact_secrets(str(exc)))
            return json.dumps({
                "result": S.redact_secrets(f"Tool error: {exc}"),
                "error": True,
            })

    def _store_entry(self, entry: S.BrainEntry) -> None:
        """Store a normalized entry in the appropriate database.

        Raises ``RuntimeError`` when the destination database is missing
        so that callers surface a real error instead of silently dropping
        the write.
        """
        database_key = S.database_for_domain(entry.domain)
        database_id = self._db_ids.get(database_key)

        if not database_id:
            raise RuntimeError(
                f"No database available for domain '{entry.domain}' "
                f"(via '{database_key}'). Run `python -m notion_brain reset` to bootstrap."
            )

        self._write_entry_raw(database_id, entry)

    def _write_entry_raw(
        self,
        database_id: str | None = None,
        entry: S.BrainEntry | None = None,
        *,
        domain: str = "memory",
        title: str = "Untitled",
        content: str = "",
        kind: str = "note",
        status: str = "active",
        confidence: str = "medium",
        tags: list[str] | None = None,
        entities: list[str] | None = None,
        db_id: str | None = None,
    ) -> None:
        """Write entry to Notion database, updating an existing page when one
        matches the title. Accepts either a BrainEntry object or keyword arguments.
        Raises ``RuntimeError`` on failure so callers can surface real errors.
        """
        # Resolve target database ID
        target_db_id = database_id or db_id
        if not target_db_id:
            db_key = S.database_for_domain(domain)
            target_db_id = self._db_ids.get(db_key) or ""

        # Build normalized entry from either source
        if entry is None:
            entry = S.BrainEntry(
                domain=domain,
                title=title,
                content=content,
                kind=kind,
                status=status,
                confidence=confidence,
                tags=tags or [],
                entities=entities or [],
                source_session_id=self._session_id,
            ).normalized()

        properties = self._database_properties(target_db_id, entry)

        # Avoid duplicate pages: if an entry with the same normalized title
        # already exists in this database, PATCH it instead of POSTing a new
        # page. Notion search-by-title is case-insensitive on the title field.
        existing_id = ""
        if entry.title and target_db_id:
            try:
                existing = store.search_page_by_title(
                    entry.title, object_type="page"
                )
            except Exception:
                existing = None
            if existing and existing.get("parent", {}).get("database_id") == target_db_id:
                existing_id = existing["id"]

        try:
            if existing_id:
                store.update_page(existing_id, properties)
                logger.debug(
                    "Updated entry in %s: %s", target_db_id, entry.title
                )
            else:
                store.create_database_page(database_id=target_db_id, properties=properties)
                logger.debug(
                    "Stored entry in %s: %s", target_db_id, entry.title
                )
        except Exception:
            # Never echo the failure detail or entry fields back into log
            # streams — the exception may carry the full user payload.
            logger.error("Failed to store entry to Notion")
            raise RuntimeError("Failed to save entry to Notion") from None

    def _database_properties(self, database_id: str, entry: S.BrainEntry) -> dict[str, Any]:
        """Build Notion properties from a BrainEntry."""
        props: dict[str, Any] = {
            "title": store.title_property(entry.title),
        }

        # Get database schema to know available properties
        try:
            db = store.get_database(database_id)
            schema_props = db.get("properties", {})
        except Exception as exc:
            logger.warning("Could not get database schema for %s: %s", database_id, S.redact_secrets(str(exc)))
            raise

        if "Domain" in schema_props:
            props["Domain"] = store.select_property(entry.domain)
        if "Status" in schema_props:
            status_payload = self._status_property(entry.status, schema_props)
            if status_payload:
                props["Status"] = status_payload
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

        return props

    def _status_property(
        self,
        status: str,
        schema_props: dict[str, Any],
        *,
        strict: bool = False,
    ) -> dict[str, Any]:
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
            target = min(valid_names)
        else:
            # No options at all — nothing safe to write; omit the property.
            return {}

        if use_select:
            return store.select_property(target)
        return store.status_property(target)

    def _tool_search(self, args: dict[str, Any]) -> str | tuple[str, dict[str, Any]]:
        """Search across brain databases, honoring the query when provided."""
        query = S.redact_secrets((args.get("query") or "").strip())
        database = args.get("database")
        max_results = min(args.get("max_results", 8), 20)

        # Merge disk context
        disk_text = ""
        if self._hermes_home:
            disk_text = bootstrap.read_memory_from_disk(self._hermes_home)

        # Build a Notion rich_text "contains" filter so the query is actually
        # applied server-side instead of being silently dropped.
        query_filter: dict[str, Any] | None = None
        if query:
            query_filter = {
                "property": "title",
                "rich_text": {"contains": query},
            }

        if database:
            # Search specific database
            db_id = self._db_ids.get(database)
            if not db_id:
                return f"No database found for: {database}"

            entries = store.query_database(db_id, page_size=max_results, filter_obj=query_filter)
            entries = _merge_disk_only(entries, disk_text)
        else:
            # Search all databases
            all_entries: list[dict] = []
            for db_id in self._db_ids.values():
                try:
                    results = store.query_database(db_id, page_size=max_results, filter_obj=query_filter)
                    all_entries.extend(results)
                except Exception:
                    pass
            all_entries = _merge_disk_only(all_entries, disk_text)
            entries = all_entries[:max_results]

        # Client-side title refinement when a query is present — Notion's
        # "contains" is case-sensitive and only matches the title property,
        # so we keep results whose displayed title actually mentions the query.
        if query:
            needle = query.lower()
            entries = [e for e in entries if needle in (e.get("title") or "").lower()]

        # Format results
        if not entries:
            return ("No results found.", {"items": []})

        lines: list[str] = []
        structured_items: list[dict[str, Any]] = []
        for entry in entries:
            title = entry.get("title", "Untitled")
            content = entry.get("properties", {}).get("Content", "")[:200]
            kind = entry.get("properties", {}).get("Kind", "note")
            lines.append(f"- [{kind}] {title}: {content}")
            structured_items.append({
                "title": title,
                "content": content,
                "kind": kind,
                "id": entry.get("id"),
                "properties": entry.get("properties", {}),
            })

        return ("\n".join(lines), {"items": structured_items})

    def _tool_remember(self, args: dict[str, Any]) -> str:
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

        # Scrub user-supplied fields before they reach the BrainEntry so the
        # secret policy applies even when callers bypass BrainEntry.normalized().
        entry = S.BrainEntry(
            domain=domain,
            title=S.clean_title(title),
            content=S.redact_secrets(content),
            kind=S.redact_secrets(kind),
            status=S.redact_secrets(status),
            tags=[S.redact_secrets(t) for t in tags],
            entities=[S.redact_secrets(e) for e in entities],
            source_session_id=self._session_id,
        ).normalized()

        try:
            self._store_entry(entry)
        except RuntimeError as exc:
            return f"Error: {S.redact_secrets(str(exc))}"
        return f"Saved: {entry.title}"

    def _tool_task(self, args: dict[str, Any]) -> str:
        """Manage tasks."""
        action = args.get("action", "list")

        if action == "create":
            title = args.get("title", "").strip()
            if not title:
                return "Error: task title is required"

            entry = S.BrainEntry(
                domain="daily_work",
                title=S.clean_title(title),
                content=S.redact_secrets(args.get("content", "")),
                kind="task",
                status=S.redact_secrets(args.get("status", "active")),
                tags=[S.redact_secrets(t) for t in args.get("tags", [])],
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Task created: {entry.title}"

        elif action == "list":
            db_id = self._db_ids.get("tasks")
            if not db_id:
                return "No Tasks database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No tasks found."

            lines: list[str] = []
            for item in entries:
                title = item.get("title", "Untitled")
                status = item.get("properties", {}).get("Status", "")
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

        return S.redact_secrets(f"Unknown task action: {action}")

    def _validated_status(
        self, status: str, db_key: str
    ) -> tuple[dict[str, Any], str | None]:
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

    def _tool_content(self, args: dict[str, Any]) -> str:
        """Manage social content."""
        action = args.get("action", "list")

        if action == "create":
            title = args.get("title", "").strip()
            body = args.get("body", "").strip()
            if not title:
                return "Error: content title is required"

            entry = S.BrainEntry(
                domain="social_content",
                title=S.clean_title(title),
                content=S.redact_secrets(body),
                kind="draft",
                status=S.redact_secrets(args.get("status", "draft")),
                tags=[S.redact_secrets(t) for t in args.get("tags", [])],
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Content saved: {entry.title}"

        elif action == "update":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"

            updates: dict[str, Any] = {}

            if "title" in args:
                updates["title"] = store.title_property(S.clean_title(args["title"]))
            if "body" in args:
                updates["Content"] = store.rich_text_property(args["body"])
            if "tags" in args:
                updates["Tags"] = store.multi_select_property(args["tags"])

            if not updates:
                return "Error: No fields provided for update."

            try:
                store.update_page(page_id, updates)
                return f"Content updated for page ID: {page_id}"
            except Exception as exc:
                return f"Error updating content: {S.redact_secrets(str(exc))}"

        elif action == "publish":
            # For social content, changing status to published requires updating the status field
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"

            try:
                # Attempt to complete the status field change
                status_payload, status_err = self._validated_status("published", "content")
                if status_err:
                    return status_err

                properties = {"Status": status_payload} if status_payload else {}
                store.update_page(page_id, properties)
                return "Content successfully marked as published."
            except Exception as exc:
                return f"Error publishing content: {S.redact_secrets(str(exc))}"

        elif action == "archive":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"

            try:
                # Archive/cleanup status field (assuming 'archived' is a valid status option)
                status_payload, status_err = self._validated_status("archived", "content")
                if status_err:
                    return status_err

                properties = {"Status": status_payload} if status_payload else {}
                store.update_page(page_id, properties)
                return "Content successfully marked as archived."
            except Exception as exc:
                return f"Error archiving content: {S.redact_secrets(str(exc))}"

        elif action == "list":
            db_id = self._db_ids.get("content")
            if not db_id:
                return "No Content database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No content found."

            lines: list[str] = []
            for item in entries:
                title = item.get("title", "Untitled")
                status = item.get("properties", {}).get("Status", "")
                lines.append(f"- [{status}] {title}")

            return "\n".join(lines)

        return S.redact_secrets(f"Unknown content action: {action}")

    def _tool_research(self, args: dict[str, Any]) -> str:
        """Manage research findings."""
        action = args.get("action", "save")

        if action == "save":
            title = args.get("title", "").strip()
            content = args.get("content", "").strip()
            if not title:
                return "Error: research title is required"

            entry = S.BrainEntry(
                domain="research",
                title=S.clean_title(title),
                content=S.redact_secrets(content),
                kind="reference",
                status=S.redact_secrets(args.get("status", "active")),
                tags=[S.redact_secrets(t) for t in args.get("tags", [])],
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Research saved: {entry.title}"

        elif action == "list":
            db_id = self._db_ids.get("research")
            if not db_id:
                return "No Research database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No research findings found."

            lines: list[str] = []
            for item in entries:
                title = item.get("title", "Untitled")
                lines.append(f"- {title}")

            return "\n".join(lines)

        return S.redact_secrets(f"Unknown research action: {action}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(context: Any) -> None:
    """Register the NotionBrainProvider with Hermes."""
    context.register_memory_provider(NotionBrainProvider())
